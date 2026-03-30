import json, requests, certifi
from pathlib import Path
from datetime import date, timedelta

LOG_PATH = Path("static/predictions_log.json")
HIST_PATH = Path("static/historial.json")

# Ligas ESPN: id ESPN -> nombre en predictions_log
LEAGUES = {
    "col.1":     "Colombia",
    "eng.1":     "Premier League",
    "esp.1":     "La Liga",
    "ger.1":     "Bundesliga",
    "ita.1":     "Serie A",
    "fra.1":     "Ligue 1",
    "uefa.champions": "Champions League",
    "mls":       "MLS",
}

def get_espn_results(league_id):
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard?dates={yesterday}"
    try:
        r = requests.get(url, verify=certifi.where(), timeout=10)
        events = r.json().get("events", [])
        results = []
        for e in events:
            comp = e["competitions"][0]
            if comp["status"]["type"]["completed"]:
                teams = {c["homeAway"]: c for c in comp["competitors"]}
                home = teams.get("home", {})
                away = teams.get("away", {})
                h_score = int(home.get("score", 0))
                a_score = int(away.get("score", 0))
                if h_score > a_score:
                    winner = home["team"]["displayName"]
                elif a_score > h_score:
                    winner = away["team"]["displayName"]
                else:
                    winner = "EMPATE"
                results.append({
                    "home": home["team"]["displayName"],
                    "away": away["team"]["displayName"],
                    "score": f"{h_score}-{a_score}",
                    "winner": winner
                })
        return results
    except Exception as ex:
        print(f"  Error ESPN {league_id}: {ex}")
        return []

def normalize(name):
    import unicodedata
    name = unicodedata.normalize('NFKD', name).encode('ascii','ignore').decode('ascii')
    return name.lower().strip()

def match_teams(log_home, log_away, espn_home, espn_away):
    return (normalize(log_home) in normalize(espn_home) or normalize(espn_home) in normalize(log_home)) and \
           (normalize(log_away) in normalize(espn_away) or normalize(espn_away) in normalize(log_away))

if not LOG_PATH.exists():
    print("No hay log de predicciones.")
    exit()

log = json.loads(LOG_PATH.read_text())
yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
pendientes = [e for e in log if e["fecha"] == yesterday and e["resultado_real"] is None]

if not pendientes:
    print("No hay predicciones pendientes de verificar.")
else:
    print(f"Verificando {len(pendientes)} predicciones del {yesterday}...")
    all_results = {}
    for lid, lname in LEAGUES.items():
        all_results[lname] = get_espn_results(lid)

    for entry in log:
        if entry["fecha"] != yesterday or entry["resultado_real"] is not None:
            continue
        league_results = all_results.get(entry["league"], [])
        for r in league_results:
            if match_teams(entry["home"], entry["away"], r["home"], r["away"]):
                entry["resultado_real"] = r["winner"]
                entry["score"] = r["score"]
                pred = entry.get("prediccion") or ""
                if pred:
                    entry["acerto"] = normalize(pred) == normalize(r["winner"]) or \
                                      (pred == "EMPATE" and r["winner"] == "EMPATE")
                print(f"  ✓ {entry['home']} vs {entry['away']}: {r['score']} | pred={pred} | acerto={entry['acerto']}")
                break

LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2))

# Generar historial.json resumido
total = [e for e in log if e["acerto"] is not None]
aciertos = [e for e in total if e["acerto"]]
pct = round(len(aciertos)/len(total)*100, 1) if total else 0

historial = {
    "total": len(total),
    "aciertos": len(aciertos),
    "porcentaje": pct,
    "ultimos": sorted(
        [e for e in log if e["resultado_real"] is not None],
        key=lambda x: x["fecha"], reverse=True
    )[:20]
}
HIST_PATH.write_text(json.dumps(historial, ensure_ascii=False, indent=2))
print(f"\nHistorial actualizado: {len(aciertos)}/{len(total)} aciertos ({pct}%)")
