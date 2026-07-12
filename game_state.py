import random
import time
import uuid

from app import db, scoring
from app.objectives import assign_objectives, check_objective, render_objective_text
from app.rumors import assign_rumors, escalate_severity, render_rumor_text

DEFAULT_ACTION_SECONDS = 75
DEFAULT_VOTE_SECONDS = 45


def new_state():
    return {
        "phase": "lobby",  # lobby | action | vote | gameover
        "round_number": 0,
        "phase_end_time": None,
        "settings": {
            "action_seconds": DEFAULT_ACTION_SECONDS,
            "vote_seconds": DEFAULT_VOTE_SECONDS,
        },
        "players": {},   # pid -> player dict
        "rumors": {},    # rid -> rumor dict
        "ballots": {},   # this round's in-progress ballots: voter_id -> {target_id: {snake, honesty}}
        "host_id": None,
        "final_results": None,
    }


class Game:
    def __init__(self):
        loaded = db.load_state()
        self.state = loaded if loaded else new_state()
        self._save()

    def _save(self):
        db.save_state(self.state)

    # ---------- Lobby ----------

    def add_player(self, name, descriptor, photo_filename):
        if self.state["phase"] != "lobby":
            return None, "Game already started -- ask the host to reset the lobby first."
        name = (name or "").strip()[:30] or "Anonymous"
        pid = str(uuid.uuid4())[:8]
        is_first = len(self.state["players"]) == 0
        self.state["players"][pid] = {
            "id": pid,
            "name": name,
            "descriptor": (descriptor or "").strip()[:60],
            "photo": photo_filename,
            "reputation": 0,
            "starting_reputation": 0,
            "influence": 0,
            "snake_score": 0,
            "honesty_score": 0,
            "debunks": 0,
            "objective": None,
            "acted_this_round": False,
            "connected": True,
        }
        if is_first:
            self.state["host_id"] = pid
        self._save()
        return pid, None

    def start_game(self, pid):
        if pid != self.state["host_id"]:
            return False, "Only the host can start the game."
        if len(self.state["players"]) < 2:
            return False, "Need at least 2 players to start."
        if self.state["phase"] != "lobby":
            return False, "Game already started."

        player_ids = list(self.state["players"].keys())
        self.state["rumors"] = assign_rumors(player_ids)
        objectives = assign_objectives(player_ids)
        for pid_, obj in objectives.items():
            self.state["players"][pid_]["objective"] = obj
            self.state["players"][pid_]["starting_reputation"] = self.state["players"][pid_]["reputation"]

        self.state["round_number"] = 1
        self._begin_action_phase()
        return True, None

    def reset_lobby(self, pid):
        if pid != self.state["host_id"]:
            return False, "Only the host can reset the lobby."
        self.state = new_state()
        self._save()
        return True, None

    # ---------- Phase transitions ----------

    def _begin_action_phase(self):
        self.state["phase"] = "action"
        self.state["ballots"] = {}
        for p in self.state["players"].values():
            p["acted_this_round"] = False
        seconds = self.state["settings"]["action_seconds"]
        self.state["phase_end_time"] = time.time() + seconds
        self._save()

    def _begin_vote_phase(self):
        self.state["phase"] = "vote"
        seconds = self.state["settings"]["vote_seconds"]
        self.state["phase_end_time"] = time.time() + seconds
        self._save()

    def _resolve_round(self):
        scoring.tally_round_votes(self.state["ballots"], self.state["players"])
        self.state["ballots"] = {}
        self.state["round_number"] += 1
        self._save()

    def tick(self):
        """Called roughly once a second by the background loop. Advances
        the phase automatically when its timer runs out."""
        if self.state["phase"] not in ("action", "vote"):
            return
        if self.state["phase_end_time"] is None:
            return
        if time.time() >= self.state["phase_end_time"]:
            self.force_advance()

    def force_advance(self):
        """Moves straight to the next phase, regardless of the timer.
        Used both by the timer running out and by the host's
        'end round early' control."""
        if self.state["phase"] == "action":
            self._begin_vote_phase()
        elif self.state["phase"] == "vote":
            self._resolve_round()
            self._begin_action_phase()

    def host_end_round_early(self, pid):
        if pid != self.state["host_id"]:
            return False, "Only the host can do that."
        if self.state["phase"] not in ("action", "vote"):
            return False, "No round in progress."
        self.force_advance()
        return True, None

    def host_end_game(self, pid):
        if pid != self.state["host_id"]:
            return False, "Only the host can end the game."
        if self.state["phase"] == "gameover":
            return False, "Game already over."

        # If a vote is currently in-flight, count it before finishing up.
        if self.state["phase"] == "vote":
            self._resolve_round()

        players = self.state["players"]
        results = []
        for pid_, p in players.items():
            obj = p.get("objective")
            completed = check_objective(pid_, obj, players) if obj else False
            if completed:
                p["reputation"] += 4  # quiet bonus for a completed objective
            results.append({
                "player_id": pid_,
                "name": p["name"],
                "reputation": p["reputation"],
                "snake_score": p["snake_score"],
                "honesty_score": p["honesty_score"],
                "objective_text": render_objective_text(obj, players) if obj else None,
                "objective_completed": completed,
            })

        results.sort(key=lambda r: r["reputation"], reverse=True)
        self.state["final_results"] = results
        self.state["phase"] = "gameover"
        self._save()
        return True, None

    # ---------- Actions ----------

    def submit_action(self, pid, action, rumor_id):
        if self.state["phase"] != "action":
            return False, "Not in the action phase."
        player = self.state["players"].get(pid)
        if not player:
            return False, "Unknown player."
        if player["acted_this_round"]:
            return False, "You've already acted this round."
        rumor = self.state["rumors"].get(rumor_id)
        if not rumor or not rumor["active"]:
            return False, "That rumor isn't in play."

        if action == "spread":
            rumor["popularity"] += 1
            escalate_severity(rumor)
            player["influence"] += scoring.SPREAD_INFLUENCE_GAIN
        elif action == "investigate":
            chance = scoring.investigate_success_chance(player["influence"])
            succeeded = random.random() < chance
            if succeeded and rumor["truth_status"] == "False":
                rumor["active"] = False
                player["influence"] += scoring.DEBUNK_INFLUENCE_GAIN
                player["reputation"] += scoring.DEBUNK_REPUTATION_GAIN
                player["debunks"] += 1
            # True / Semi-True rumors never disappear, and a failed
            # investigation of a False rumor produces no visible result --
            # that ambiguity is the point.
        else:
            return False, "Unknown action."

        player["acted_this_round"] = True
        self._save()
        return True, None

    def submit_vote(self, pid, ballot):
        """ballot: {target_id: {"snake": int, "honesty": int}}"""
        if self.state["phase"] != "vote":
            return False, "Not in the vote phase."
        if pid not in self.state["players"]:
            return False, "Unknown player."
        clean = {}
        for target_id, points in (ballot or {}).items():
            if target_id == pid or target_id not in self.state["players"]:
                continue
            clean[target_id] = {
                "snake": max(0, min(scoring.MAX_VOTE_POINTS, int(points.get("snake", 0)))),
                "honesty": max(0, min(scoring.MAX_VOTE_POINTS, int(points.get("honesty", 0)))),
            }
        self.state["ballots"][pid] = clean
        self._save()
        return True, None

    # ---------- Views ----------

    def public_view_for(self, viewer_pid):
        """A personalized snapshot: everyone's public stats, but only the
        viewer's own secret objective and action-locked status."""
        players = self.state["players"]
        rumors = self.state["rumors"]

        player_views = []
        for pid_, p in players.items():
            player_views.append({
                "id": pid_,
                "name": p["name"],
                "descriptor": p["descriptor"],
                "photo": p["photo"],
                "reputation": p["reputation"],
                "influence": p["influence"],
                "snake_score": p["snake_score"],
                "honesty_score": p["honesty_score"],
                "is_host": pid_ == self.state["host_id"],
                "is_you": pid_ == viewer_pid,
                "acted_this_round": p["acted_this_round"],
            })

        rumor_views = []
        for rid, r in rumors.items():
            if not r["active"]:
                continue
            rumor_views.append({
                "id": rid,
                "text": render_rumor_text(r, players),
                "severity": r["severity"],
                "popularity": r["popularity"],
                "category": r["category"],
            })

        me = players.get(viewer_pid)
        my_objective = None
        if me and me.get("objective"):
            my_objective = render_objective_text(me["objective"], players)

        time_remaining = None
        if self.state["phase_end_time"]:
            time_remaining = max(0, round(self.state["phase_end_time"] - time.time()))

        return {
            "phase": self.state["phase"],
            "round_number": self.state["round_number"],
            "time_remaining": time_remaining,
            "host_id": self.state["host_id"],
            "you": viewer_pid,
            "you_are_host": viewer_pid == self.state["host_id"],
            "players": player_views,
            "rumors": rumor_views,
            "my_objective": my_objective,
            "i_have_acted": me["acted_this_round"] if me else False,
            "i_have_voted": viewer_pid in self.state["ballots"],
            "final_results": self.state["final_results"],
        }


game = Game()
