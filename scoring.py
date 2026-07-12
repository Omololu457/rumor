"""
All the tunable numbers live here. If a round feels too swingy or too flat,
this is the file to adjust -- nothing else needs to change.
"""

SPREAD_INFLUENCE_GAIN = 2
DEBUNK_INFLUENCE_GAIN = 3
DEBUNK_REPUTATION_GAIN = 3

# Base chance an investigation "connects," before influence is factored in.
INVESTIGATE_BASE_CHANCE = 0.35
# Each point of Influence adds this much to the investigator's odds (capped).
INVESTIGATE_INFLUENCE_FACTOR = 0.02
INVESTIGATE_MAX_CHANCE = 0.9

# How many points a voter can award in each category, per ballot line.
MAX_VOTE_POINTS = 3

# How votes translate into Reputation at the end of a round.
REPUTATION_PER_VOTE_POINT = 0.5


def investigate_success_chance(influence: int) -> float:
    chance = INVESTIGATE_BASE_CHANCE + influence * INVESTIGATE_INFLUENCE_FACTOR
    return min(chance, INVESTIGATE_MAX_CHANCE)


def tally_round_votes(ballots: dict, players: dict):
    """ballots: {voter_id: {target_id: {"snake": int, "honesty": int}}}
    Mutates players in place, adding Snake/Honesty/Reputation for the round."""
    snake_totals = {pid: 0 for pid in players}
    honesty_totals = {pid: 0 for pid in players}

    for voter_id, ballot in ballots.items():
        for target_id, points in ballot.items():
            if target_id not in players or target_id == voter_id:
                continue
            snake_totals[target_id] += max(0, min(MAX_VOTE_POINTS, points.get("snake", 0)))
            honesty_totals[target_id] += max(0, min(MAX_VOTE_POINTS, points.get("honesty", 0)))

    for pid, player in players.items():
        s = snake_totals.get(pid, 0)
        h = honesty_totals.get(pid, 0)
        player["snake_score"] += s
        player["honesty_score"] += h
        player["reputation"] += round((s + h) * REPUTATION_PER_VOTE_POINT)
