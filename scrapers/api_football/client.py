"""
Cliente HTTP para API-Football v3 (api-sports.io).

Autenticación: header `x-apisports-key`.
Lee la API key desde la variable de entorno API_FOOTBALL_KEY.

Manejo de errores:
- 429 (rate limit) → APIFootballRateLimitError (sin retry).
- 5xx → retry exponencial (2s, 4s, 8s) hasta MAX_RETRIES.
- Errores semánticos (HTTP 200 con campo `errors` no vacío) → APIFootballError.
- Timeouts/desconexión → retry exponencial.

Rate limits visibles vía headers:
- x-ratelimit-requests-remaining: cupo diario.
- x-ratelimit-remaining: cupo por minuto.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

import requests


API_FOOTBALL_BASE = "https://v3.football.api-sports.io"
DEFAULT_TIMEOUT = 10
MAX_RETRIES = 3
BACKOFF_BASE = 2.0  # segundos: 2, 4, 8


class APIFootballError(Exception):
    """Error genérico de API-Football."""


class APIFootballRateLimitError(APIFootballError):
    """Rate limit alcanzado (429 o errors.requests)."""


class APIFootballClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = API_FOOTBALL_BASE,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        logger: Optional[logging.Logger] = None,
        session: Optional[requests.Session] = None,
    ):
        self.api_key = api_key or os.environ.get("API_FOOTBALL_KEY")
        if not self.api_key:
            raise APIFootballError(
                "API_FOOTBALL_KEY no configurada (env var o argumento)."
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logger or logging.getLogger("api_football")
        self.session = session or requests.Session()
        self.session.headers.update({"x-apisports-key": self.api_key})

        # rate-limit state (poblado al recibir headers)
        self.requests_remaining: Optional[int] = None  # diario
        self.minute_remaining: Optional[int] = None    # por minuto

    # ---------------------------------------------------------------- internals
    def _update_rate_limits(self, headers) -> None:
        try:
            r = headers.get("x-ratelimit-requests-remaining")
            if r is not None:
                self.requests_remaining = int(r)
            m = headers.get("x-ratelimit-remaining")
            if m is not None:
                self.minute_remaining = int(m)
        except (TypeError, ValueError):
            pass

    def _request(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        params = params or {}
        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries):
            t0 = time.time()
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as e:
                last_exc = e
                self.logger.warning(
                    "[API-Football] %s attempt=%d connection error: %s",
                    path, attempt + 1, e,
                )
                if attempt < self.max_retries - 1:
                    time.sleep(BACKOFF_BASE * (2 ** attempt))
                continue

            elapsed = time.time() - t0
            self._update_rate_limits(resp.headers)

            if resp.status_code == 429:
                self.logger.error(
                    "[API-Football] %s 429 rate-limited (daily=%s, minute=%s)",
                    path, self.requests_remaining, self.minute_remaining,
                )
                raise APIFootballRateLimitError(f"429 rate-limited: {resp.text[:200]}")

            if 500 <= resp.status_code < 600:
                self.logger.warning(
                    "[API-Football] %s %d attempt=%d elapsed=%.2fs",
                    path, resp.status_code, attempt + 1, elapsed,
                )
                last_exc = APIFootballError(
                    f"HTTP {resp.status_code}: {resp.text[:200]}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(BACKOFF_BASE * (2 ** attempt))
                continue

            if resp.status_code != 200:
                self.logger.error(
                    "[API-Football] %s %d: %s",
                    path, resp.status_code, resp.text[:200],
                )
                raise APIFootballError(
                    f"HTTP {resp.status_code}: {resp.text[:200]}"
                )

            try:
                data = resp.json()
            except ValueError as e:
                raise APIFootballError(f"Respuesta no-JSON en {path}: {e}") from e

            errors = data.get("errors")
            if isinstance(errors, dict) and errors:
                # API-Football devuelve {"requests": "..."} cuando excedés el plan
                if "requests" in errors or "rateLimit" in errors:
                    raise APIFootballRateLimitError(f"errors={errors}")
                self.logger.error(
                    "[API-Football] %s errores semánticos: %s", path, errors,
                )
                raise APIFootballError(f"errors={errors}")
            if isinstance(errors, list) and errors:
                raise APIFootballError(f"errors={errors}")

            self.logger.info(
                "[API-Football] %s 200 elapsed=%.2fs results=%s daily_remaining=%s",
                path,
                elapsed,
                data.get("results"),
                self.requests_remaining,
            )
            return data

        raise APIFootballError(
            f"Reintentos agotados en {path}: {last_exc}"
        )

    # ------------------------------------------------------------------ public
    def get_status(self) -> Dict[str, Any]:
        """Verifica la API key y reporta cupo restante del plan."""
        return self._request("/status")

    def get_leagues(self, **params) -> Dict[str, Any]:
        """
        Listado de ligas. Filtros típicos:
        - id=int, name=str, country=str, season=int, current=true|false
        """
        return self._request("/leagues", params)

    def get_teams(self, league: int, season: int) -> Dict[str, Any]:
        """Equipos de una liga/temporada."""
        return self._request("/teams", {"league": league, "season": season})

    def get_fixtures_by_date(
        self,
        date: str,
        league: Optional[int] = None,
        season: Optional[int] = None,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fixtures de una fecha (YYYY-MM-DD), opcionalmente filtrado por liga."""
        params: Dict[str, Any] = {"date": date}
        if league is not None:
            params["league"] = league
        if season is not None:
            params["season"] = season
        if timezone:
            params["timezone"] = timezone
        return self._request("/fixtures", params)

    def get_h2h(
        self, team1: int, team2: int, last: int = 10
    ) -> Dict[str, Any]:
        """Historial directo entre dos equipos (últimos N partidos)."""
        return self._request(
            "/fixtures/headtohead",
            {"h2h": f"{team1}-{team2}", "last": last},
        )

    def get_team_statistics(
        self, team: int, league: int, season: int
    ) -> Dict[str, Any]:
        """Estadísticas de un equipo en una liga/temporada (forma, goles local/visita)."""
        return self._request(
            "/teams/statistics",
            {"team": team, "league": league, "season": season},
        )

    def get_team_last_fixtures(
        self, team: int, last: int = 5
    ) -> Dict[str, Any]:
        """Últimos N fixtures de un equipo (para racha reciente)."""
        return self._request("/fixtures", {"team": team, "last": last})

    def get_fixture_statistics(
        self, fixture: int, team: Optional[int] = None
    ) -> Dict[str, Any]:
        """Estadísticas de un partido (tiros a puerta, corners, posesión, …).

        Devuelve `response` con un bloque por equipo; cada bloque trae una
        lista `statistics` de pares {type, value}. Filtrable por equipo.
        """
        params: Dict[str, Any] = {"fixture": fixture}
        if team is not None:
            params["team"] = team
        return self._request("/fixtures/statistics", params)
