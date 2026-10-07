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


class TextEmbedder(Protocol):
    dim: int

    def embed_text(self, text: str) -> list[float]: ...


class HashedImageEmbedder:
    dim = 512

    def embed(self, image_bytes: bytes) -> list[float]:
        return _hash_vec(image_bytes, self.dim)


class HashedTextEmbedder:
    """Deterministic 768-d text vectors (same space convention as Gemini
    output_dimensionality=768). Swap for the Gemini embedder in Phase 5+."""

    dim = 768

    def embed_text(self, text: str) -> list[float]:
        return _hash_vec(text.encode(), self.dim)


def _hash_vec(data: bytes, dim: int) -> list[float]:
    seed = int.from_bytes(hashlib.sha512(data).digest()[:8], "big")
    rng = random.Random(seed)
    vec = [rng.gauss(0.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
