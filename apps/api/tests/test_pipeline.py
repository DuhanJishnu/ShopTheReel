"""Pipeline unit tests: ingest cache, hashed embeddings, crop/merge, extract(fake).

preprocess/orchestrator need the ffmpeg binary; they run in CI (apt ffmpeg)
and skip locally when ffmpeg is absent.
"""

import io
import shutil

import PIL.Image
import pytest

from app.clients.embeddings import HashedImageEmbedder, cosine
from app.clients.vision import FakeVision
from app.db import models
from app.pipeline import crop_merge as cm
from app.pipeline import extract as ex
from app.pipeline import ingest as ing

FFMPEG = shutil.which("ffmpeg") is not None
needs_ffmpeg = pytest.mark.skipif(not FFMPEG, reason="ffmpeg binary not installed")


def _jpeg(color: str, size: tuple[int, int] = (200, 200)) -> bytes:
    buf = io.BytesIO()
    PIL.Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


async def _user_reel(session_factory, kind="video", storage_key="videos/t.mp4", status="queued"):
    import uuid

    factory = session_factory
    async with factory() as s:
        user = models.User(email=f"pipe-{uuid.uuid4().hex}@example.com", password_hash="x")
        s.add(user)
        await s.flush()
        reel = models.Reel(user_id=user.id, kind=kind, storage_key=storage_key, status=status)
        s.add(reel)
        await s.commit()
        await s.refresh(reel)
        return reel.id


async def test_ingest_exact_cache(session_factory):
    rid1 = await _user_reel(session_factory, storage_key="videos/dup.mp4", status="done")
    async with session_factory() as s:
        reel1 = await s.get(models.Reel, rid1)
        assert reel1 is not None
        s.add(models.DetectedItem(reel_id=rid1, category="top", confidence=0.9))
        await s.commit()
    rid2 = await _user_reel(session_factory, storage_key="videos/dup2.mp4")

    raw = b"same-bytes"
    async with session_factory() as s:
        r1 = await s.get(models.Reel, rid1)
        assert r1 is not None
        assert await ing.run_ingest(s, r1, raw) is False
        r1.status = "done"
        await s.commit()
    async with session_factory() as s:
        r2 = await s.get(models.Reel, rid2)
        assert r2 is not None
        assert await ing.run_ingest(s, r2, raw) is True
        assert r2.cache_hit is True and r2.status == "done"


async def test_hashed_embedder_properties():
    emb = HashedImageEmbedder()
    a, b = _jpeg("red"), _jpeg("blue")
    assert emb.dim == 512
    assert cosine(emb.embed(a), emb.embed(a)) == pytest.approx(1.0)
    assert cosine(emb.embed(a), emb.embed(b)) < 0.5
    import math

    assert math.sqrt(sum(v * v for v in emb.embed(a))) == pytest.approx(1.0)


async def test_crop_merge_persists(session_factory):
    from app.clients.storage import FakeStore

    store = FakeStore()
    rid = await _user_reel(session_factory)
    vision = FakeVision()
    blobs = [_jpeg("olive"), _jpeg("navy")]
    result = await vision.extract(blobs)
    async with session_factory() as s:
        reel = await s.get(models.Reel, rid)
        assert reel is not None
        n = await cm.run_crop_merge(s, reel, result, blobs, store, HashedImageEmbedder())
        assert n == 2
        assert len(store.blobs) == 2
        await s.commit()
    async with session_factory() as s:
        from sqlalchemy import select

        rows = (await s.execute(select(models.DetectedItem).where(models.DetectedItem.reel_id == rid))).scalars().all()
        assert len(rows) == 2
        assert all(r.crop_key and r.embedding and len(r.embedding) == 512 for r in rows)
        assert rows[0].attribute_text and "oversized" in rows[0].attribute_text


async def test_extract_fake_logs_costs(session_factory):
    rid = await _user_reel(session_factory)
    async with session_factory() as s:
        reel = await s.get(models.Reel, rid)
        assert reel is not None
        result = await ex.run_extract(s, reel, FakeVision(), frame_blobs=[_jpeg("red")])
        assert len(result.items) == 2
        assert reel.overall_style == ["casual"]
        from sqlalchemy import select

        costs = (await s.execute(select(models.ReelCost).where(models.ReelCost.reel_id == rid))).scalars().all()
        assert len(costs) == 1 and costs[0].model == "fake"
        await s.commit()


async def test_crop_blob_rejects_small():
    assert cm.crop_blob(_jpeg("red", (200, 200)), [0, 0, 1000, 1000]) is not None
    assert cm.crop_blob(_jpeg("red", (40, 40)), [0, 0, 1000, 1000]) is None
    assert cm.crop_blob(_jpeg("red"), [500, 500, 100, 100]) is None


@needs_ffmpeg
async def test_preprocess_samples_frames(session_factory):
    import subprocess
    import tempfile
    from pathlib import Path

    from app.clients.storage import FakeStore
    from app.pipeline import preprocess as pp

    store = FakeStore()
    out = str(Path(tempfile.gettempdir()) / "synth.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=6:size=640x480:rate=10",
         "-pix_fmt", "yuv420p", out],
        check=True, capture_output=True,
    )
    with open(out, "rb") as f:
        raw = f.read()
    rid = await _user_reel(session_factory)
    async with session_factory() as s:
        reel = await s.get(models.Reel, rid)
        assert reel is not None
        hit = await pp.run_preprocess(s, reel, raw, store)
        assert hit is False
        from sqlalchemy import select

        frames = (await s.execute(select(models.Frame).where(models.Frame.reel_id == rid))).scalars().all()
        assert 1 <= len(frames) <= 8
        await s.commit()


@needs_ffmpeg
async def test_orchestrator_fake_end_to_end(session_factory):
    import subprocess
    import tempfile
    from pathlib import Path

    from app.clients.storage import FakeStore
    from app.pipeline.orchestrator import run_pipeline

    store = FakeStore()
    out = str(Path(tempfile.gettempdir()) / "synth2.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=4:size=640x480:rate=10",
         "-pix_fmt", "yuv420p", out],
        check=True, capture_output=True,
    )
    with open(out, "rb") as f:
        raw = f.read()
    key = "videos/e2e.mp4"
    await store.put_bytes(key, raw, "video/mp4")
    rid = await _user_reel(session_factory, storage_key=key)
    async with session_factory() as s:
        reel = await run_pipeline(s, rid, vision=FakeVision(), store=store)
        assert reel.status == "done"
