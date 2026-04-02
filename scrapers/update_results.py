"""
Actualiza automáticamente los resultados en predictions_log.json
usando la API de ESPN para partidos ya terminados.
"""
import json, requests
from datetime import date, timedelta
from pathlib import Path

LOG_PATH = Path("static/predictions_log.json")
HISTORIAL_PATH = Path("static/historial.json")

ESPN_SPORT_MAP = {
    "Liga Colombiana":  "soccer/col.1",
    "Liga Argentina":   "soccer/arg.1",
    "Premier League":   "soccer/eng.1",
    "La Liga":          "soccer/esp.1",
    "Serie A":          "soccer/ita.1",
    "Bundesliga":       "soccer/ger.1",
    "Ligue 1":          "soccer/fra.1",
    "Brasileirao":      "soccer/bra.1",
    "Super Lig":        "soccer/tur.1",
    "Champions League": "soccer/uefa.champions",
    "NBA":              "basketball/nba",
    "NBA 2025-26":      "basketball/nba",
}

FINAL_STATUSES = {"Full Time", "Final", "FT", "Finalizado", "AET", "Pen"}

def norm(s):
    import unicodedata
    return unicodedata.normalize('NFKD', str(s)).encode('ascii','ignore').decode().lower().strip()

def fetch_results(sport_code, fecha):
    """Obtiene todos los resultados terminados de ESPN para una liga y fecha."""
    date_str = fecha.replace("-", "")
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_code}/scoreboard?dates={date_str}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        results = {}
        for e in r.json().get("events", []):
            comp = e["competitions"][0]
            status = comp["status"]["type"]["description"]
            if status not in FINAL_STATUSES:
                continue
            teams = comp["competitors"]
            home = next((t for t in teams if t["homeAway"] == "home"), None)
            away = next((t for t in teams if t["homeAway"] == "away"), None)
            if not home or not away:
                continue
            h_name = home["team"]["displayName"]
            a_name = away["team"]["displayName"]
            h_score = home.get("score", "?")
            a_score = away.get("score", "?")
            results[(norm(h_name), norm(a_name))] = {
                "score": f"{h_score}-{a_score}",
                "home_score": int(h_score) if str(h_score).isdigit() else 0,
                "away_score": int(a_score) if str(a_score).isdigit() else 0,
                "home_name": h_name,
                "away_name": a_name,
            }
        return results
    except Exception as ex:
        print(f"   ESPN error ({sport_code}): {ex}")
        return {}

def check_acerto(pred, result, nba):
    """Determina si la predicción fue correcta según el resultado."""
    h = result["home_score"]
    a = result["away_score"]
    p = pred.strip()

    if "Over 1.5" in p:
        return (h + a) > 1
    if "Over 2.5" in p:
        return (h + a) > 2
    if "EMPATE" in p:
        return h == a

    if "Apuesta sin empate:" in p:
        team = p.replace("Apuesta sin empate:", "").strip()
        if h == a:
            return None  # empate → apuesta nula (devuelven la apuesta, no cuenta como acierto ni fallo)
        winner = result["home_name"] if h > a else result["away_name"]
        return norm(team) in norm(winner) or norm(winner) in norm(team)

    if "Doble oportunidad:" in p:
        team = p.replace("Doble oportunidad:", "").strip()
        if h == a:
            return True  # empate → doble oportunidad siempre acierta
        winner = result["home_name"] if h > a else result["away_name"]
        return norm(team) in norm(winner) or norm(winner) in norm(team)

    # Ganador: comparar nombre
    if nba:
        winner = result["home_name"] if h > a else result["away_name"]
    else:
        if h > a:   winner = result["home_name"]
        elif a > h: winner = result["away_name"]
        else:       return False  # empate pero se predijo ganador

    return norm(p) in norm(winner) or norm(winner) in norm(p)

def update_historial(log):
    """Recalcula historial.json desde el log completo."""
    completados = [e for e in log if e.get("acerto") is not None]
    if not completados:
        return
    total    = len(completados)
    aciertos = sum(1 for e in completados if e["acerto"])
    pct      = round(aciertos / total * 100) if total > 0 else 0
    ultimos  = list(reversed(completados))[:20]
    HISTORIAL_PATH.write_text(json.dumps({
        "total": total, "aciertos": aciertos, "porcentaje": pct,
        "ultimos": ultimos
    }, ensure_ascii=False, indent=2))
    print(f"   Historial: {aciertos}/{total} = {pct}%")

def main():
    log = json.loads(LOG_PATH.read_text()) if LOG_PATH.exists() else []
    pendientes = [e for e in log if e.get("acerto") is None and e.get("resultado_real") is None]

    if not pendientes:
        print("No hay predicciones pendientes de resultado.")
        return

    print(f"Buscando resultados para {len(pendientes)} predicciones pendientes...")

    # Agrupar por fecha+liga para minimizar requests a ESPN
    queries = {}
    for e in pendientes:
        key = (e["fecha"], e["league"])
        queries.setdefault(key, []).append(e)

    actualizados = 0
    for (fecha, league), entries in queries.items():
        sport_code = ESPN_SPORT_MAP.get(league)
        if not sport_code:
            print(f"   Sin código ESPN para {league}, saltando")
            continue

        results = fetch_results(sport_code, fecha)
        if not results:
            print(f"   Sin resultados aún para {league} {fecha}")
            continue

        nba = "basketball" in sport_code
        for e in entries:
            key = (norm(e["home"]), norm(e["away"]))
            if key not in results:
                print(f"   Pendiente: {e['home']} vs {e['away']} ({fecha})")
                continue

            res = results[key]
            acerto = check_acerto(e["prediccion"], res, nba)
            e["resultado_real"] = res["score"]
            e["acerto"] = acerto
            marca = "✅" if acerto else "❌"
            print(f"   {marca} {e['home']} vs {e['away']}: {res['score']} | pred={e['prediccion']}")
            actualizados += 1

    if actualizados > 0:
        LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2))
        update_historial(log)
        print(f"\n{actualizados} resultado(s) actualizados.")
    else:
        print("Ningún partido ha terminado todavía.")

if __name__ == "__main__":
    main()
