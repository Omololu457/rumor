import json
import os
import random

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "objective_pool.json")


def load_objective_templates():
    with open(DATA_PATH) as f:
        return json.load(f)


def assign_objectives(player_ids):
    templates = load_objective_templates()
    objectives = {}
    for pid in player_ids:
        tpl = random.choice(templates)
        obj = {"type": tpl["type"]}

        if tpl["type"] in ("reach_influence", "reach_reputation"):
            obj["threshold"] = random.randint(*tpl["threshold_range"])
            obj["description"] = tpl["description"].format(threshold=obj["threshold"])
        elif tpl["type"] in ("beat_snake", "beat_honesty", "tank_reputation"):
            others = [p for p in player_ids if p != pid]
            obj["target"] = random.choice(others) if others else None
            obj["description"] = tpl["description"]  # target name filled in at render time
        else:
            obj["description"] = tpl["description"]

        objectives[pid] = obj
    return objectives


def render_objective_text(obj, players):
    text = obj["description"]
    target = obj.get("target")
    if target and target in players:
        text = text.replace("{target}", players[target]["name"])
    return text


def check_objective(pid, obj, players):
    me = players.get(pid)
    if not me:
        return False
    t = obj["type"]

    if t == "reach_influence":
        return me["influence"] >= obj["threshold"]
    if t == "reach_reputation":
        return me["reputation"] >= obj["threshold"]
    if t == "expose_false":
        return me.get("debunks", 0) >= 1
    if t == "beat_snake":
        target = players.get(obj.get("target"))
        return target is not None and me["snake_score"] > target["snake_score"]
    if t == "beat_honesty":
        target = players.get(obj.get("target"))
        return target is not None and me["honesty_score"] > target["honesty_score"]
    if t == "tank_reputation":
        target = players.get(obj.get("target"))
        return target is not None and target["reputation"] < target.get("starting_reputation", 0)
    return False
