"""Vector helpers: pgvector returns strings over asyncpg (no codec registered),
lists on SQLite/JSON. Normalize at the boundary; keep math dependency-free."""

import json
import math


def as_list(vec: object) -> list[float] | None:
    if vec is None:
        return None
    if isinstance(vec, str):
        try:
            parsed = json.loads(vec)
        except ValueError:
            return None
        return [float(v) for v in parsed] if isinstance(parsed, list) else None
    if isinstance(vec, (list, tuple)):
        return [float(v) for v in vec]
    return None


def normed(vec: list[float]) -> list[float]:
    n = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / n for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def ema_step(taste: list[float] | None, vec: list[float], lr: float, away: bool = False) -> list[float]:
    """Exponential moving average toward (or away from) vec. Dim-agnostic."""
    if taste is None or len(taste) != len(vec):
        return list(vec) if not away else [0.0] * len(vec)
    sign = -1.0 if away else 1.0
    return normed([(1 - lr) * t + sign * lr * v for t, v in zip(taste, vec)])
