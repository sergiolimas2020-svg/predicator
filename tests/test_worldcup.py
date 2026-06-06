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


def test_betplay_fields_no_emite_cuotas():
    """PREDIKTOR no publica cuotas: _betplay_fields ya NO inyecta ningún campo
    de cuota/EV/mercado de referencia en los picks (no-op)."""
    import scrapers.generate_predictions as g
    assert g._betplay_fields(None, 75.6, None) == {}
    assert g._betplay_fields(1.85, 62.5, 8.5) == {}


def test_goals_section_defined_and_safe():
    """Regresión: goals_section debe existir (antes era un NameError latente que
    reventaba la generación de HTML de cualquier pick de fútbol)."""
    import scrapers.generate_predictions as g
    assert callable(getattr(g, "goals_section", None))
    hd = {"position": {"goles_favor": 20, "goles_contra": 8, "partidos": 12}}
    ad = {"position": {"goles_favor": 10, "goles_contra": 14, "partidos": 12}}
    html = g.goals_section(hd, ad)
    assert isinstance(html, str) and "Over/Under" in html
    # robusto ante datos vacíos
    assert isinstance(g.goals_section({}, {}), str)


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


def test_is_senior_national_filters_youth_and_women():
    assert wc.is_senior_national("Argentina")
    assert wc.is_senior_national("Costa Rica")
    assert not wc.is_senior_national("Azerbaijan U21")
    assert not wc.is_senior_national("Qatar U23")
    assert not wc.is_senior_national("Spain Women")
    assert not wc.is_senior_national("Brazil U20")


def test_select_upcoming_friendlies_filters():
    def fx(fid, date, home, away, status="NS"):
        return {"fixture": {"id": fid, "date": date, "status": {"short": status}},
                "teams": {"home": {"id": fid*10, "name": home},
                          "away": {"id": fid*10+1, "name": away}}}
    raw = [
        fx(1, "2026-06-06T18:00:00+00:00", "Argentina", "Honduras"),   # ok: Argentina mundialista
        fx(2, "2026-06-06T18:00:00+00:00", "Argentina U23", "Chile"),  # juvenil → fuera
        fx(3, "2026-06-30T18:00:00+00:00", "Spain", "France"),         # fuera de ventana
        fx(4, "2026-06-06T18:00:00+00:00", "Argentina", "Honduras", status="FT"),  # jugado
        fx(5, "2026-06-06T18:00:00+00:00", "Atlantis", "Wakanda"),     # sin Elo → fuera
        fx(6, "2026-06-06T18:00:00+00:00", "Vanuatu", "Fiji"),         # minnows (Elo bajo) → fuera
    ]
    wc_teams = {"Argentina", "Spain", "France"}  # mundialistas
    sel = wc.select_upcoming_friendlies(raw, today="2026-06-05", window_days=12, wc_teams=wc_teams)
    pairs = {(s["home"], s["away"]) for s in sel}
    assert ("Argentina", "Honduras") in pairs     # relevante: Argentina es mundialista
    assert all("U23" not in s["home"] and "U23" not in s["away"] for s in sel)
    assert ("Spain", "France") not in pairs        # fuera de ventana
    assert ("Atlantis", "Wakanda") not in pairs    # sin Elo
    assert ("Vanuatu", "Fiji") not in pairs        # minnows: no relevante → descartado
    assert len(sel) == 1


def test_friendlies_keep_two_strong_non_wc_teams():
    """Dos selecciones fuertes que no van al Mundial (Elo >= 1700) deben pasar."""
    def fx(fid, home, away):
        return {"fixture": {"id": fid, "date": "2026-06-06T18:00:00+00:00", "status": {"short": "NS"}},
                "teams": {"home": {"id": fid*10, "name": home}, "away": {"id": fid*10+1, "name": away}}}
    # Italy (1856) y Greece (1752): ninguna en el Mundial, pero ambas fuertes
    sel = wc.select_upcoming_friendlies([fx(1, "Italy", "Greece")],
                                        today="2026-06-05", window_days=12, wc_teams=set())
    assert {(s["home"], s["away"]) for s in sel} == {("Italy", "Greece")}


def test_selecciones_excluidas_de_mercados_over_y_corners():
    """Las ligas de selección NO deben producir picks de Over de goles ni de
    córners (no calibrados, cuota muy baja). Solo el camino curado (1X2/DNB/DC)."""
    import scrapers.generate_predictions as g
    assert g.WORLD_CUP_LEAGUE in g.SELECCION_LEAGUES
    assert g.FRIENDLY_LEAGUE in g.SELECCION_LEAGUES
    strong = {"position": {"goles_favor": 30, "goles_contra": 8, "partidos": 12}, "elo": 1950}
    weak = {"position": {"goles_favor": 9, "goles_contra": 22, "partidos": 12}, "elo": 1450}
    # danger data abundante para forzar evaluación de Over/córners
    danger = {(g._norm("A"), g._norm("B")): {
        "home_danger": {"shots_on_target_avg": 8, "corners_avg": 9},
        "away_danger": {"shots_on_target_avg": 7, "corners_avg": 8},
        "home_corners": 9, "away_corners": 8,
    }}
    matches = [(g.FRIENDLY_LEAGUE, "A", "B", strong, weak, False)]
    assert g._select_over25_picks(matches, danger) == []
    assert g._select_corners_picks(matches, danger) == []
    # Una liga normal (no excluida) SÍ podría producir (no aserción de contenido,
    # solo que no se rompe y que el filtro es específico de selecciones)
    normal = [("Liga Colombiana", "A", "B", strong, weak, False)]
    assert isinstance(g._select_over25_picks(normal, danger), list)


def test_worldcup_market_selection_by_statistical_support():
    from scrapers.generate_predictions import _worldcup_stat_pick
    # Favorito holgado → "gana" directo
    strong = {"favorite": "home", "win_home": 0.66, "win_away": 0.12,
              "dnb_home": 0.85, "dnb_away": 0.15, "dc_home": 0.88, "dc_away": 0.34}
    lbl, p, tipo = _worldcup_stat_pick(strong, "Argentina", "Curacao")
    assert tipo == "gana" and "Argentina" in lbl and p >= 60

    # Gana <60 pero DNB alto → "sin empate (DNB)"
    dnb_case = {"favorite": "home", "win_home": 0.55, "win_away": 0.12,
                "dnb_home": 0.82, "dnb_away": 0.18, "dc_home": 0.83, "dc_away": 0.45}
    lbl, p, tipo = _worldcup_stat_pick(dnb_case, "England", "Haiti")
    assert tipo == "dnb" and p >= 70

    # Gana y DNB por debajo, pero DC alto → "doble oportunidad"
    dc_case = {"favorite": "home", "win_home": 0.52, "win_away": 0.18,
               "dnb_home": 0.66, "dnb_away": 0.34, "dc_home": 0.82, "dc_away": 0.48}
    lbl, p, tipo = _worldcup_stat_pick(dc_case, "Brazil", "Panama")
    assert tipo == "doble_oportunidad" and p >= 80

    # Partido parejo → sin respaldo → None
    even = {"favorite": "home", "win_home": 0.40, "win_away": 0.33,
            "dnb_home": 0.55, "dnb_away": 0.45, "dc_home": 0.67, "dc_away": 0.60}
    assert _worldcup_stat_pick(even, "Colombia", "Senegal") is None


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


def test_dixon_coles_sube_empate_vs_poisson_independiente():
    """Dixon-Coles (rho<0) debe AUMENTAR la prob de empate y reducir la del
    favorito frente al Poisson independiente — corrección de goles bajos."""
    import math
    import scrapers.generate_predictions as g
    assert g.DIXON_COLES_RHO < 0
    hd = {"position": {"goles_favor": 28, "goles_contra": 12, "partidos": 15}, "elo": 1850}
    ad = {"position": {"goles_favor": 15, "goles_contra": 20, "partidos": 15}, "elo": 1650}
    w, d, l = g.prob_futbol_3way(hd, ad)               # con DC
    lh, la = g._compute_lambdas(hd, ad)
    ph = [(lh**x * math.exp(-lh)) / math.factorial(x) for x in range(11)]
    pa = [(la**y * math.exp(-la)) / math.factorial(y) for y in range(11)]
    pw = pd = pl = 0.0
    for x in range(11):
        for y in range(11):
            p = ph[x] * pa[y]
            pw += p if x > y else 0; pd += p if x == y else 0; pl += p if x < y else 0
    t = pw + pd + pl; pd_indep = pd / t * 100; pw_indep = pw / t * 100
    assert d > pd_indep        # DC sube el empate
    assert w < pw_indep        # DC baja la sobre-confianza del favorito
