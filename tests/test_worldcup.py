"""
Tests de las funciones puras del scraper del Mundial 2026 (scrapers/worldcup.py).

No tocan la red: usan fixtures mock con la forma real de la respuesta de
API-Football v3 (/fixtures, /teams). Validan:
  - extracción/normalización de partidos
  - cálculo de forma (goles favor/contra, récord) por selección
  - Elo cronológico con dedup por fixture_id
  - compatibilidad del dict de salida con el modelo (position.goles_*)

Uso:
    python3 -m pytest tests/test_worldcup.py -v
"""
import math

from scrapers import worldcup as wc
from scrapers.generate_predictions import prob_futbol, _compute_lambdas


def _fx(fid, ts, home_id, home, away_id, away, gh, ga, status="FT"):
    """Construye un fixture con la forma de API-Football v3."""
    return {
        "fixture": {"id": fid, "timestamp": ts, "status": {"short": status}},
        "teams": {"home": {"id": home_id, "name": home},
                  "away": {"id": away_id, "name": away}},
        "goals": {"home": gh, "away": ga},
    }


# IDs ficticios pero estables
ARG, BRA, COL, TON = 1, 2, 3, 99


def test_is_finished():
    assert wc.is_finished(_fx(1, 0, ARG, "Argentina", BRA, "Brazil", 1, 0))
    assert not wc.is_finished(_fx(1, 0, ARG, "Argentina", BRA, "Brazil", 0, 0, status="NS"))


def test_extract_match_valid_and_invalid():
    m = wc.extract_match(_fx(10, 1000, ARG, "Argentina", BRA, "Brazil", 2, 1))
    assert m["home"] == "Argentina" and m["away"] == "Brazil"
    assert m["gh"] == 2 and m["ga"] == 1 and m["fixture_id"] == 10
    # goles None → inválido
    bad = _fx(11, 1000, ARG, "Argentina", BRA, "Brazil", None, None)
    assert wc.extract_match(bad) is None


def test_compute_team_form_counts_goals_and_record():
    # Argentina: gana 3-0 (local), pierde 0-2 (visitante), empata 1-1 (local)
    matches = [
        wc.extract_match(_fx(1, 300, ARG, "Argentina", TON, "Tonga", 3, 0)),
        wc.extract_match(_fx(2, 200, BRA, "Brazil", ARG, "Argentina", 2, 0)),
        wc.extract_match(_fx(3, 100, ARG, "Argentina", COL, "Colombia", 1, 1)),
    ]
    form = wc.compute_team_form(matches, ARG, "Argentina", max_matches=10)
    pos = form["position"]
    assert pos["partidos"] == 3
    assert pos["goles_favor"] == 3 + 0 + 1   # 4
    assert pos["goles_contra"] == 0 + 2 + 1  # 3
    assert pos["ganados"] == 1 and pos["empatados"] == 1 and pos["perdidos"] == 1
    assert pos["puntos"] == 1 * 3 + 1


def test_compute_team_form_respects_window_and_recency():
    # 3 partidos; ventana=2 debe tomar los 2 más recientes (ts mayores)
    matches = [
        wc.extract_match(_fx(1, 100, ARG, "Argentina", TON, "Tonga", 5, 0)),  # viejo, fuera
        wc.extract_match(_fx(2, 200, ARG, "Argentina", COL, "Colombia", 1, 0)),
        wc.extract_match(_fx(3, 300, ARG, "Argentina", BRA, "Brazil", 0, 2)),
    ]
    form = wc.compute_team_form(matches, ARG, "Argentina", max_matches=2)
    pos = form["position"]
    assert pos["partidos"] == 2
    assert pos["goles_favor"] == 1 + 0      # excluye el 5-0 viejo
    assert pos["goles_contra"] == 0 + 2


def test_compute_team_form_ignores_other_teams():
    matches = [wc.extract_match(_fx(1, 100, BRA, "Brazil", COL, "Colombia", 2, 2))]
    form = wc.compute_team_form(matches, ARG, "Argentina", max_matches=10)
    assert form["position"]["partidos"] == 0


def test_elo_pool_dedups_by_fixture_id():
    # El mismo partido aparece dos veces (histórico de ambos equipos)
    m1 = wc.extract_match(_fx(1, 100, ARG, "Argentina", BRA, "Brazil", 1, 0))
    pool = [m1, dict(m1)]  # duplicado exacto, mismo fixture_id
    elos = wc.compute_elo_pool(pool)
    # Un solo update: ganador sube por encima de la base, perdedor baja
    assert elos["Argentina"] > wc.ELO_BASE
    assert elos["Brazil"] < wc.ELO_BASE
    # Simétrico alrededor de la base (ambos parten de 1500)
    assert math.isclose((elos["Argentina"] - wc.ELO_BASE),
                        (wc.ELO_BASE - elos["Brazil"]), rel_tol=1e-6)


def test_elo_pool_stronger_team_emerges():
    # Argentina gana repetidamente → su Elo debe quedar el más alto
    pool = []
    for i in range(6):
        pool.append(wc.extract_match(_fx(i, i * 100, ARG, "Argentina", TON, "Tonga", 3, 0)))
    elos = wc.compute_elo_pool(pool)
    assert elos["Argentina"] > elos["Tonga"]


def test_is_neutral_venue():
    assert wc.is_neutral_venue("Argentina") is True
    assert wc.is_neutral_venue("Brazil") is True
    # anfitriones juegan con localía real
    assert wc.is_neutral_venue("Mexico") is False
    assert wc.is_neutral_venue("USA") is False
    assert wc.is_neutral_venue("Canada") is False


def test_parse_schedule_includes_future_matches_and_neutral_flag():
    fixtures = [
        # partido futuro (sin goles) en sede neutral
        {"fixture": {"id": 1, "date": "2026-06-11T19:00:00+00:00",
                     "venue": {"name": "MetLife Stadium"}, "status": {"short": "NS"}},
         "teams": {"home": {"name": "Argentina"}, "away": {"name": "Brazil"}},
         "league": {"round": "Group Stage - 1"}},
        # anfitrión local → no neutral
        {"fixture": {"id": 2, "date": "2026-06-11T22:00:00+00:00",
                     "venue": {"name": "Estadio Azteca"}, "status": {"short": "NS"}},
         "teams": {"home": {"name": "Mexico"}, "away": {"name": "Croatia"}},
         "league": {"round": "Group Stage - 1"}},
        # inválido (sin away) → descartado
        {"fixture": {"id": 3, "date": "2026-06-12T19:00:00+00:00"},
         "teams": {"home": {"name": "Spain"}, "away": {}}},
    ]
    sched = wc.parse_schedule(fixtures)
    assert len(sched) == 2
    arg = next(s for s in sched if s["home"] == "Argentina")
    mex = next(s for s in sched if s["home"] == "Mexico")
    assert arg["neutral"] is True and arg["away"] == "Brazil"
    assert mex["neutral"] is False
    assert arg["round"] == "Group Stage - 1"


def test_seed_elo_real_values_and_ordering():
    # Valores reales (World Football Elo, 2026-06-01) y orden esperado
    assert wc.seed_elo_for("Spain") == 2165
    assert wc.seed_elo_for("Argentina") == 2113
    assert wc.seed_elo_for("Brazil") == 1988
    assert wc.seed_elo_for("Spain") > wc.seed_elo_for("France") > wc.seed_elo_for("Brazil")
    # Cubre las 48 selecciones del Mundial (+ alguna referencia extra como Italia)
    assert len(wc.ELO_SEED) >= 48
    assert all(v >= 1400 for v in wc.ELO_SEED.values())


def test_seed_elo_alias_and_normalization():
    # Grafías alternativas de API-Football / fuentes
    assert wc.seed_elo_for("Turkey") == wc.seed_elo_for("Türkiye")
    assert wc.seed_elo_for("United States") == wc.seed_elo_for("USA")
    assert wc.seed_elo_for("DR Congo") == wc.seed_elo_for("Congo DR")
    assert wc.seed_elo_for("Cape Verde") == wc.seed_elo_for("Cape Verde Islands")
    assert wc.seed_elo_for("Curacao") == wc.seed_elo_for("Curaçao")
    # Desconocida → None (cae al respaldo en build)
    assert wc.seed_elo_for("Atlantis") is None


def test_temperature_preserves_argmax_and_reduces_confidence():
    from scrapers.generate_predictions import _apply_temperature_3way
    pw, pd, pl = 0.90, 0.07, 0.03
    cw, cd, cl = _apply_temperature_3way(pw, pd, pl, T=2.3)
    # suma 1, mismo favorito, menos confianza, renormalizado
    assert abs(cw + cd + cl - 1.0) < 1e-9
    assert cw == max(cw, cd, cl)        # sigue siendo el favorito
    assert cw < pw                       # menos sobre-confiado
    # T=1 no cambia nada
    assert _apply_temperature_3way(pw, pd, pl, T=1.0) == (pw, pd, pl)


def test_intl_calibration_softens_but_keeps_pick():
    """Con calibrador intl activo, el favorito baja su prob pero sigue siendo
    el favorito; clubes (intl=False) no se tocan."""
    import scrapers.generate_predictions as g
    strong = wc.compute_team_form(
        [wc.extract_match(_fx(1, 100, ARG, "Argentina", TON, "Tonga", 4, 0))], ARG, "Argentina", 10)
    weak = wc.compute_team_form(
        [wc.extract_match(_fx(2, 100, TON, "Tonga", ARG, "Argentina", 0, 4))], TON, "Tonga", 10)
    strong["elo"], weak["elo"] = 2100, 1430
    raw = g.prob_futbol_3way_raw(strong, weak, neutral=True, intl=False)
    cal = g.prob_futbol_3way_raw(strong, weak, neutral=True, intl=True)
    # si hay calibrador cargado (T>1), la prob del favorito intl <= cruda
    if g._load_intl_calibrator():
        assert cal[0] <= raw[0] + 1e-9
    # el favorito se mantiene en ambos
    assert raw[0] == max(raw) and cal[0] == max(cal)


def test_form_output_feeds_model_with_intl_neutral():
    """El dict de forma debe ser consumible por el modelo Poisson internacional."""
    strong = wc.compute_team_form(
        [wc.extract_match(_fx(1, 100, ARG, "Argentina", TON, "Tonga", 4, 0))],
        ARG, "Argentina", 10)
    weak = wc.compute_team_form(
        [wc.extract_match(_fx(2, 100, TON, "Tonga", ARG, "Argentina", 0, 4))],
        TON, "Tonga", 10)
    strong["elo"] = 1900
    weak["elo"] = 1400
    hp, ap = prob_futbol(strong, weak, neutral=True, intl=True)
    assert hp > ap  # el fuerte es favorito
    lh, la = _compute_lambdas(strong, weak, neutral=True, intl=True)
    assert lh > 0 and la > 0
