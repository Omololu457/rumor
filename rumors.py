import json
import os
import random
import uuid

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "rumor_pool.json")


def load_rumor_templates():
    with open(DATA_PATH) as f:
        return json.load(f)


def assign_rumors(player_ids, count=None):
    """Pull a fresh, randomized set of rumors from the pool and assign
    real players as their subjects."""
    templates = load_rumor_templates()
    random.shuffle(templates)

    usable = [t for t in templates if t.get("subjects_needed", 1) <= len(player_ids)]
    if count is None:
        count = min(len(usable), max(6, len(player_ids) * 2))
    chosen = usable[:count]

    rumors = {}
    for tpl in chosen:
        rid = str(uuid.uuid4())[:8]
        needed = tpl.get("subjects_needed", 1)
        subjects = random.sample(player_ids, needed)
        rumors[rid] = {
            "id": rid,
            "text_template": tpl["text"],
            "subject_ids": subjects,
            "truth_status": tpl["truth_status"],  # True / Semi-True / False
            "severity": tpl.get("base_severity", "Low"),
            "popularity": 0,
            "category": tpl.get("category", "general"),
            "active": True,
        }
    return rumors


def render_rumor_text(rumor, players):
    """Fill {subject}/{subject2} placeholders with real player names."""
    names = [players[pid]["name"] for pid in rumor["subject_ids"] if pid in players]
    text = rumor["text_template"]
    if len(names) >= 1:
        text = text.replace("{subject}", names[0])
    if len(names) >= 2:
        text = text.replace("{subject2}", names[1])
    return text


def escalate_severity(rumor):
    pop = rumor["popularity"]
    if pop >= 9:
        rumor["severity"] = "Severe"
    elif pop >= 6:
        rumor["severity"] = "High"
    elif pop >= 3:
        rumor["severity"] = "Medium"
    else:
        rumor["severity"] = "Low"
