import json
from collections import defaultdict

def load_data():
    with open('static/predictions_log.json', 'r') as f:
        return json.load(f)

def calc_stats(data):
    total = len(data)
    wins = sum(1 for d in data if d.get("acerto") == True)
    losses = sum(1 for d in data if d.get("acerto") == False)

    winrate = round((wins / total) * 100, 1) if total else 0

    # racha actual
    streak = 0
    for d in reversed(data):
        if d.get("acerto"):
            streak += 1
        else:
            break

    # rendimiento por tipo
    by_type = defaultdict(lambda: {"wins": 0, "total": 0})

    for d in data:
        pred = d.get("prediccion", "").lower()
        acierto = d.get("acerto")

        if "over" in pred:
            t = "over"
        elif "doble oportunidad" in pred:
            t = "dc"
        else:
            t = "win"

        by_type[t]["total"] += 1
        if acierto:
            by_type[t]["wins"] += 1

    for t in by_type:
        w = by_type[t]["wins"]
        tot = by_type[t]["total"]
        by_type[t]["rate"] = round((w / tot) * 100, 1) if tot else 0

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "streak": streak,
        "by_type": by_type
    }

def save(stats):
    with open('static/stats.json', 'w') as f:
        json.dump(stats, f, indent=2)

if __name__ == "__main__":
    data = load_data()
    stats = calc_stats(data)
    save(stats)
    print("Stats generadas:", stats)
