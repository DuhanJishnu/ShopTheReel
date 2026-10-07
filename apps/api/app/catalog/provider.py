"""CatalogProvider interface (the B2B story) + shared query/candidate types.

A real Myntra/Flipkart adapter implements this protocol against their search
API or feed; see DatasetProvider (local pgvector) and MockPartnerProvider
(simulated remote retailer) for the two reference implementations.
"""

from dataclasses import dataclass, field
from typing import Protocol

from app.db import models


@dataclass
class CandidateQuery:
    categories: set[str] = field(default_factory=set)
    gender: str = "unisex"
    colours: list[str] = field(default_factory=list)
    pattern: str | None = None
    size: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    disliked_colours: list[str] = field(default_factory=list)
    text_vec: list[float] | None = None
    image_vec: list[float] | None = None
    limit: int = 50


@dataclass
class ProductCandidate:
    product_id: str
    img_sim: float = 0.0
    text_sim: float = 0.0
    attr_match: float = 0.0

    @property
    def fused(self) -> float:
        return 0.5 * self.img_sim + 0.35 * self.text_sim + 0.15 * self.attr_match


class CatalogProvider(Protocol):
    name: str

    async def search_candidates(self, query: CandidateQuery) -> list[ProductCandidate]: ...
    async def get_product(self, sku: str) -> models.Product | None: ...
    async def check_availability(self, sku: str, size: str) -> bool: ...
