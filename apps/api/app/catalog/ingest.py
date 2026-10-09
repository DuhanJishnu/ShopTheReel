"""Catalog seed: Kaggle styles.csv + images -> products (resumable, deterministic).

Usage:
  python -m app.catalog.ingest --csv ../../data/raw/styles.csv --images ../../data/raw/images
  python -m app.catalog.ingest --demo 200 --skip-images   # no dataset needed (tests/CI smoke)
  make seed

Fills spec section 8 gaps with a seeded RNG: price bands per articleType,
brand parse, size sets with random drops, 90% in-stock, mock-partner buy URLs.
Embeddings are hashed (768-d text, 512-d image) per project decision; swap the
two embedder lines for Gemini/FashionCLIP without touching anything else.
"""

import argparse
import asyncio
import csv
import json
import random
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select

from app.clients.embeddings import HashedImageEmbedder, HashedTextEmbedder
from app.core.config import REPO_ROOT
from app.core.logging import get_logger
from app.db import models
from app.db.session import SessionLocal

log = get_logger()
PROGRESS = REPO_ROOT / "data/seed-progress.json"
BUY_TEMPLATE = "https://partner.example/p/{sku}"  # Demo partner: never a real purchase link.

PRICE_BANDS = [
    (("t-shirt", "tee"), (399, 1299)),
    (("shirt",), (499, 1499)),
    (("jean", "denim"), (799, 2499)),
    (("trouser", "pant", "short", "skirt"), (699, 1999)),
    (("dress", "gown", "kurta", "saree"), (899, 2999)),
    (("sneaker", "shoe", "loafer"), (1299, 5999)),
    (("sandal", "flip", "heel"), (499, 1999)),
    (("handbag", "bag", "backpack", "wallet"), (999, 4999)),
    (("watch",), (1499, 9999)),
    (("sunglass", "eyewear", "frame"), (799, 2999)),
    (("jewellery", "jewelry", "necklace", "earring", "bracelet", "ring"), (299, 1999)),
    (("jacket", "coat", "blazer"), (1499, 4999)),
]
DEFAULT_BAND = (499, 1999)
SIZE_SETS = {
    "top": ["XS", "S", "M", "L", "XL", "XXL"],
    "dress": ["XS", "S", "M", "L", "XL", "XXL"],
    "outerwear": ["S", "M", "L", "XL", "XXL"],
    "bottom": ["28", "30", "32", "34", "36", "38"],
    "footwear": ["UK 5", "UK 6", "UK 7", "UK 8", "UK 9", "UK 10", "UK 11"],
}


def map_category(master: str, article: str) -> str:
    a = (article or "").lower()
    m = (master or "").lower()
    if any(k in a for k in ("shoe", "sneaker", "loafer", "sandal", "flip", "heel", "boot")) or m == "footwear":
        return "footwear"
    if any(k in a for k in ("handbag", "bag", "backpack", "wallet", "clutch", "tote")):
        return "bag"
    if "watch" in a:
        return "watch"
    if any(k in a for k in ("sunglass", "eyewear", "spectacle")):
        return "eyewear"
    if any(k in a for k in ("jewell", "necklace", "earring", "bracelet", "bangle", "ring", "pendant")):
        return "jewellery"
    if "belt" in a:
        return "belt"
    if any(k in a for k in ("scarf", "stole", "shawl")):
        return "scarf"
    if any(k in a for k in ("cap", "hat", "beanie")):
        return "headwear"
    if any(k in a for k in ("dress", "gown", "saree")):
        return "dress"
    if any(k in a for k in ("jacket", "coat", "blazer", "shrug")):
        return "outerwear"
    if any(k in a for k in ("jean", "trouser", "pant", "short", "skirt", "legging", "cargo")):
        return "bottom"
    if m == "apparel":
        return "top"
    return "other"


def map_gender(g: str) -> str:
    g = (g or "").lower()
    if g == "men":
        return "men"
    if g == "women":
        return "women"
    return "unisex"


def price_for(article: str, brand: str, rng: random.Random) -> float:
    a = (article or "").lower()
    lo, hi = DEFAULT_BAND
    for keys, band in PRICE_BANDS:
        if any(k in a for k in keys):
            lo, hi = band
            break
    return round(rng.uniform(lo, hi) * rng.uniform(0.8, 1.6), 2)


def sizes_for(category: str, rng: random.Random) -> list[str]:
    full = SIZE_SETS.get(category, ["One Size"])
    kept = [s for s in full if rng.random() > 0.25]
    return kept or [full[len(full) // 2]]


def brand_of(display: str) -> str:
    token = (display or "").strip().split(" ")[0]
    return token if token and len(token) > 1 else "Generic"


def attribute_text(row: dict) -> str:
    colour = row.get("baseColour", "unknown")
    return f"{colour} {row.get('subCategory', '')} {row.get('articleType', '')}".strip()


async def seed_rows(
    rows: list[dict[str, Any]], provider: str, images_dir: Path | None, skip_images: bool,
    batch: int, rng_seed: int, buy_template: str, limit: int, workers: int = 32,
) -> dict:
    from concurrent.futures import ThreadPoolExecutor

    from app.core.deps import get_store

    rng = random.Random(rng_seed)
    text_emb, img_emb = HashedTextEmbedder(), HashedImageEmbedder()
    store = get_store()
    done: set[str] = set(json.loads(PROGRESS.read_text())) if PROGRESS.exists() else set()
    stats: dict[str, Any] = {"inserted": 0, "updated": 0, "skipped": 0, "unmapped": {}}
    todo = [r for r in rows[:limit] if str(r.get("id", r.get("sku"))) not in done]

    # Phase 1: deterministic row prep (sequential RNG — order matters).
    prepped: list[tuple[str, dict, bytes | None]] = []
    for row in todo:
        sku = str(row.get("id", row.get("sku")))
        category = map_category(row.get("masterCategory", ""), row.get("articleType", ""))
        if category == "other":
            stats["unmapped"][row.get("articleType", "?")] = stats["unmapped"].get(row.get("articleType", "?"), 0) + 1
        brand = brand_of(row.get("productDisplayName", ""))
        attr = attribute_text(row)
        img_bytes: bytes | None = None
        if not skip_images and images_dir is not None:
            fp = images_dir / f"{sku}.jpg"
            if fp.exists():
                img_bytes = fp.read_bytes()
        crop_key = f"catalog/{provider}/{sku}.jpg" if img_bytes is not None else None
        values = dict(
            title=row.get("productDisplayName", sku) or sku, brand=brand, category=category,
            subcategory=row.get("articleType", "") or "", gender=map_gender(row.get("gender", "")),
            colours=[row["baseColour"]] if row.get("baseColour") else [], pattern="unknown",
            fit="regular", price=price_for(row.get("articleType", ""), brand, rng), currency="INR",
            sizes_available=sizes_for(category, rng), in_stock=rng.random() < 0.90,
            image_url=crop_key, buy_url=buy_template.format(sku=sku), attribute_text=attr,
            text_vec=text_emb.embed_text(attr),
            image_vec=img_emb.embed(img_bytes) if img_bytes else img_emb.embed(sku.encode()),
        )
        prepped.append((sku, values, img_bytes))

    # Phase 2: image uploads, concurrent (boto3 clients are thread-safe).
    def _upload(item: tuple[str, bytes | None]) -> None:
        import asyncio as _asyncio

        sku, data = item
        if data is None:
            return
        _asyncio.run(store.put_bytes(f"catalog/{provider}/{sku}.jpg", data, "image/jpeg"))

    payloads = [(sku, img) for sku, _, img in prepped if img is not None]
    if payloads:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(_upload, payloads))

    # Phase 3: resumable upserts.
    async with SessionLocal() as session:
        for i, (sku, values, _) in enumerate(prepped):
            res = await session.execute(
                select(models.Product).where(models.Product.provider == provider, models.Product.sku == sku))
            product = res.scalars().first()
            if product is None:
                session.add(models.Product(provider=provider, sku=sku, **values))
                stats["inserted"] += 1
            else:
                for k, v in values.items():
                    setattr(product, k, v)
                stats["updated"] += 1
            done.add(sku)
            if (i + 1) % batch == 0:
                await session.commit()
                PROGRESS.parent.mkdir(parents=True, exist_ok=True)
                PROGRESS.write_text(json.dumps(sorted(done)))
                log.info("seed progress", done=len(done), **{k: v for k, v in stats.items() if k != "unmapped"})
        await session.commit()
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(sorted(done)))
    return stats


def demo_rows(n: int) -> list[dict[str, Any]]:
    rng = random.Random(7)
    colours = ["olive green", "off-white", "blue", "black", "beige", "maroon"]
    rows = []
    for i in range(n):
        rows.append({
            "sku": f"demo-{i:05d}", "masterCategory": "Apparel",
            "articleType": rng.choice(["Tshirts", "Jeans", "Dresses", "Jackets", "Sneakers", "Handbags"]),
            "subCategory": "demo", "baseColour": rng.choice(colours),
            "gender": rng.choice(["Men", "Women"]), "productDisplayName": f"Demo Brand product {i}",
        })
    # Categories derive from articleType via map_category (top/bottom/dress/outerwear/footwear/bag).
    return rows


def load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as f:
        return cast("list[dict[str, Any]]", list(csv.DictReader(f)))


async def _run(args) -> None:  # type: ignore[no-untyped-def]
    if args.demo:
        rows: list[dict] = demo_rows(args.demo)
        images = None
    else:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            raise SystemExit(f"styles.csv not found at {csv_path} (see README catalog section)")
        rows = load_csv(csv_path)
        # Seeded shuffle before the limit cut so the demo slice stays balanced
        # across categories instead of taking the CSV's (grouped) head.
        if len(rows) > (args.limit or len(rows)):
            random.Random(args.seed).shuffle(rows)
        images = Path(args.images) if args.images else None
    stats = await seed_rows(rows, args.provider, images, args.skip_images, args.batch,
                            args.seed, args.buy_url_template, args.limit or len(rows),
                            workers=args.workers)
    print(f"inserted={stats['inserted']} updated={stats['updated']} unmapped_articleTypes={len(stats['unmapped'])}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Seed the product catalog (resumable).")
    parser.add_argument("--csv", default=str(REPO_ROOT / "data/raw/styles.csv"))
    parser.add_argument("--images", default=str(REPO_ROOT / "data/raw/images"))
    parser.add_argument("--provider", default="dataset")
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--batch", type=int, default=500)
    parser.add_argument("--workers", type=int, default=32, help="Concurrent image-upload threads")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--demo", type=int, default=0, help="Seed N synthetic products instead of the CSV")
    parser.add_argument("--skip-images", action="store_true")
    parser.add_argument("--buy-url-template", default=BUY_TEMPLATE)
    args = parser.parse_args(argv)
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
