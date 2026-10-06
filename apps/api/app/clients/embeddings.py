"""Image embeddings (Phase 2: deterministic hashed placeholder).

The spec mandates FashionCLIP (transformers, 512-d) in the worker; per human
decision Phase 2 uses a hashed embedder behind the same interface so the
pipeline, clustering and tests run without torch. Properties: deterministic,
L2-normalised, cosine == 1.0 for byte-identical images (dedupes exact
duplicates), near-0 otherwise. Swap for FashionCLIP in Phase 3.
"""

import hashlib
import math
import random
from typing import Protocol


class ImageEmbedder(Protocol):
    dim: int

    def embed(self, image_bytes: bytes) -> list[float]: ...


class HashedImageEmbedder:
    dim = 512

    def embed(self, image_bytes: bytes) -> list[float]:
        seed = int.from_bytes(hashlib.sha512(image_bytes).digest()[:8], "big")
        rng = random.Random(seed)
        vec = [rng.gauss(0.0, 1.0) for _ in range(self.dim)]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
