"""DatasetProvider: queries the local products table with pgvector ANN.

Strategy (spec 7.2 retrieve): hard filters that pg can index (gender,
category set, in_stock) + two HNSW ANN queries (text_vec, image_vec, top 200
each for headroom) ordered by cosine distance; soft filters (size,
disliked colours, widened price) applied in Python over the union.
Requires Postgres (pgvector); raises RuntimeError on SQLite.
"""

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.provider import CandidateQuery, ProductCandidate
from app.core.logging import get_logger
from app.db import models

log = get_logger()
FETCH = 200


def _to_pg(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


class DatasetProvider:
    name = "dataset"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search_candidates(self, query: CandidateQuery) -> list[ProductCandidate]:
        if self.session.bind is None or self.session.bind.dialect.name != "postgresql":
            raise RuntimeError("DatasetProvider ANN search requires Postgres+pgvector")
        if query.text_vec is None or query.image_vec is None:
            raise ValueError("query needs text_vec and image_vec")
        cats = list(query.categories) or ["top", "bottom", "dress", "outerwear", "footwear"]
        genders = [query.gender, "unisex"] if query.gender != "unisex" else ["unisex", "men", "women"]
        by_id: dict[str, ProductCandidate] = {}
        for vec, attr in ((query.text_vec, "text_sim"), (query.image_vec, "img_sim")):
            col = "text_vec" if attr == "text_sim" else "image_vec"
            rows = await self.session.execute(
                text(
                    f"SELECT id, 1 - ({col} <=> :vec) AS sim FROM products "
                    "WHERE gender IN :genders AND category IN :cats AND in_stock = true "
                    f"ORDER BY {col} <=> :vec LIMIT :limit"
                ).bindparams(bindparam("genders", expanding=True), bindparam("cats", expanding=True)),
                {"vec": _to_pg(vec), "genders": genders, "cats": cats, "limit": FETCH},
            )
            for pid, sim in rows.all():
                cand = by_id.setdefault(pid, ProductCandidate(product_id=pid))
                setattr(cand, attr, max(getattr(cand, attr), float(sim)))
        return sorted(by_id.values(), key=lambda c: (c.img_sim + c.text_sim), reverse=True)[: FETCH]

    async def get_product(self, sku: str) -> models.Product | None:
        from sqlalchemy import select

        res = await self.session.execute(select(models.Product).where(models.Product.sku == sku))
        return res.scalars().first()

    async def check_availability(self, sku: str, size: str) -> bool:
        product = await self.get_product(sku)
        if product is None or not product.in_stock:
            return False
        return product.sizes_available is None or size in (product.sizes_available or [])
