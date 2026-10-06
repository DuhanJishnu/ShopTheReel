"""crop_merge: crop bboxes, hash-embed, merge cross-frame duplicates.

CLI: python -m app.pipeline.crop_merge --help
Rules (spec 7.2): 8% padding, skip crops <64px on short side, same-category
cosine > 0.88 merges, representative = highest confidence then largest area.
"""

import argparse
import asyncio
import io
import uuid

import PIL.Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.embeddings import ImageEmbedder, cosine
from app.clients.vision import ExtractionResult
from app.core.logging import get_logger
from app.db import models
from app.db.session import SessionLocal
from app.services import reels as reel_service

log = get_logger()
SIM_THRESHOLD = 0.88
MIN_SIDE_PX = 64


def crop_blob(frame: bytes, bbox_1000: list[int], pad_ratio: float = 0.08) -> bytes | None:
    """Crop [ymin,xmin,ymax,xmax] (0-1000) with padding. None if too small/invalid."""
    try:
        ymin, xmin, ymax, xmax = [max(0, min(1000, int(v))) for v in bbox_1000]
    except (ValueError, TypeError):
        return None
    if ymax <= ymin or xmax <= xmin:
        return None
    with PIL.Image.open(io.BytesIO(frame)).convert("RGB") as im:
        w, h = im.size
        pad_x = int((xmax - xmin) / 1000 * w * pad_ratio)
        pad_y = int((ymax - ymin) / 1000 * h * pad_ratio)
        box = (
            max(0, xmin / 1000 * w - pad_x), max(0, ymin / 1000 * h - pad_y),
            min(w, xmax / 1000 * w + pad_x), min(h, ymax / 1000 * h + pad_y),
        )
        box = (int(box[0]), int(box[1]), int(box[2]), int(box[3]))
        cw, ch = box[2] - box[0], box[3] - box[1]
        if min(cw, ch) < MIN_SIDE_PX:
            return None
        crop = im.crop(box)
        buf = io.BytesIO()
        crop.save(buf, format="JPEG", quality=88)
        return buf.getvalue()


def attribute_text(category: str, colours: list[str], pattern: str, fit: str, sub: str, mat: str | None) -> str:
    colour = colours[0] if colours else "unknown"
    base = f"{colour} {pattern} {fit} {sub or category}".strip()
    return f"{base}, {mat}" if mat else base


async def run_crop_merge(
    session: AsyncSession, reel: models.Reel, result: ExtractionResult,
    frame_blobs: list[bytes], store, embedder: ImageEmbedder,  # type: ignore[no-untyped-def]
) -> int:
    """Crop + embed + merge + persist detected_items. Returns persisted count."""
    await reel_service.write_stage(session, reel.id, "crop_merge", "running")
    groups: list[dict] = []  # {category, vec, best, members}
    skipped = 0
    for item in result.items:
        if item.frame_index >= len(frame_blobs):
            skipped += 1
            continue
        crop = crop_blob(frame_blobs[item.frame_index], item.bbox)
        if crop is None:
            skipped += 1
            continue
        vec = embedder.embed(crop)
        placed = False
        for g in groups:
            if g["category"] == item.category and cosine(g["vec"], vec) > SIM_THRESHOLD:
                g["members"].append((item, crop, vec))
                placed = True
                break
        if not placed:
            groups.append({"category": item.category, "vec": vec, "members": [(item, crop, vec)]})
    count = 0
    for g in groups:
        members = sorted(g["members"], key=lambda m: (m[0].confidence, len(m[1])), reverse=True)
        rep, crop, vec = members[0]
        crop_key = f"crops/{reel.id}/{uuid.uuid4().hex}.jpg"
        await store.put_bytes(crop_key, crop, "image/jpeg")
        session.add(models.DetectedItem(
            reel_id=reel.id, category=rep.category, subcategory=rep.subcategory,
            colours=rep.colours, pattern=rep.pattern, fit=rep.fit,
            material_guess=rep.material_guess, gender_hint=rep.gender_hint,
            style_tags=rep.style_tags,
            bbox={"ymin": rep.bbox[0], "xmin": rep.bbox[1], "ymax": rep.bbox[2], "xmax": rep.bbox[3]},
            crop_key=crop_key, confidence=rep.confidence,
            attribute_text=attribute_text(rep.category, rep.colours, rep.pattern, rep.fit, rep.subcategory, rep.material_guess),
            embedding=vec, suggested=False,
        ))
        count += 1
    await session.flush()
    await reel_service.write_stage(
        session, reel.id, "crop_merge", "done",
        metrics={"items": count, "groups": len(groups), "skipped": skipped},
    )
    return count


async def _cli(reel_id: str, fake: bool) -> None:
    from sqlalchemy import select as _select

    from app.clients.embeddings import HashedImageEmbedder
    from app.clients.vision import FakeVision, get_vision_client
    from app.core.deps import get_store
    from app.pipeline.extract import run_extract

    vision = FakeVision() if fake else get_vision_client()
    store = get_store()
    async with SessionLocal() as session:
        reel = await session.get(models.Reel, reel_id)
        if reel is None:
            raise SystemExit(f"reel {reel_id} not found")
        res = await session.execute(_select(models.Frame).where(models.Frame.reel_id == reel_id).order_by(models.Frame.idx))
        blobs = [await store.download_bytes(f.storage_key) for f in res.scalars().all()]
        result = await run_extract(session, reel, vision, frame_blobs=blobs)
        n = await run_crop_merge(session, reel, result, blobs, store, HashedImageEmbedder())
        await session.commit()
        print(f"items={n} backend={vision.name}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Crop detections, merge duplicates, persist items.")
    parser.add_argument("--reel-id", required=True, help="Reel id to crop/merge")
    parser.add_argument("--fake", action="store_true", help="Use FakeVision (no Gemini call)")
    args = parser.parse_args(argv)
    asyncio.run(_cli(args.reel_id, args.fake))


if __name__ == "__main__":
    main()
