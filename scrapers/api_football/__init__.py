"""
Integración API-Football v3 (api-sports.io) para PREDIKTOR.
Fase 1: cliente + recolección en paralelo, sin afectar el motor de producción.
"""
from .client import (
    APIFootballClient,
    APIFootballError,
    APIFootballRateLimitError,
)

__all__ = [
    "APIFootballClient",
    "APIFootballError",
    "APIFootballRateLimitError",
]
