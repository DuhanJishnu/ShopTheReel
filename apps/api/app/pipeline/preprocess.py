"""preprocess: ffmpeg normalise + scene detect + frame pick + phash cache check.

CLI: python -m app.pipeline.preprocess --help
Requires the ffmpeg binary (installed in the worker image; apt ffmpeg locally).
"""

import argparse
import asyncio
import subprocess
import tempfile
from pathlib import Path

import cv2
import imagehash
import PIL.Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db import models
from app.db.session import SessionLocal
from app.services import reels as reel_service

log = get_logger()
MAX_FRAMES = 8
MAX_CANDIDATES = 24


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def probe_duration(path: Path) -> float:
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], 30)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def normalise(src: Path, dst: Path) -> None:
    # Comma inside min() must be backslash-escaped for the filter parser.
    _run(["ffmpeg", "-y", "-i", str(src), "-vf", "scale=-2:min(720\\,ih)", "-an", str(dst)], 300).check_returncode()


def scene_times(path: Path, duration: float) -> list[float]:
    try:
        from scenedetect import ContentDetector, detect

        scenes = detect(str(path), ContentDetector())
        times = [(s[0].get_seconds() + s[1].get_seconds()) / 2 for s in scenes]
    except Exception as exc:
        log.warning("scene detect failed, using uniform sampling", error=str(exc))
        times = []
    uniform = [round(t, 2) for t in _frange(0, duration, 2.0)]
    merged = sorted(set([round(t, 2) for t in times] + uniform))
    return merged[:MAX_CANDIDATES]


def _frange(start: float, stop: float, step: float) -> list[float]:
    out, t = [], start
    while t < stop:
        out.append(t)
        t += step
    return out


def grab_frame(video: Path, at: float, dst: Path) -> bool:
    r = _run(["ffmpeg", "-y", "-ss", str(at), "-i", str(video), "-frames:v", "1", str(dst)], 60)
    return r.returncode == 0 and dst.exists()


def sharpness(path: Path) -> float:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def phash_hex(path: Path) -> str:
    with PIL.Image.open(path) as im:
        return str(imagehash.phash(im))


async def run_preprocess(session: AsyncSession, reel: models.Reel, raw: bytes, store) -> bool:  # type: ignore[no-untyped-def]
    """Sample/select/upload frames. Returns True on perceptual-hash cache hit."""
    await reel_service.write_stage(session, reel.id, "preprocess", "running")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        src = tmpdir / "input.bin"
        src.write_bytes(raw)
        duration = probe_duration(src) if reel.kind == "video" else 0.0
        if duration > settings.max_video_seconds:
            raise ValueError(f"video {duration:.1f}s exceeds {settings.max_video_seconds}s cap")
        reel.duration_s = duration
        norm = tmpdir / "norm.mp4"
        if reel.kind == "video":
            normalise(src, norm)
        else:
            norm = src
        times = scene_times(norm, duration) if reel.kind == "video" else [0.0]
        cands: list[tuple[float, Path, float, str]] = []
        for i, t in enumerate(times):
            fp = tmpdir / f"cand_{i:02d}.jpg"
            if not grab_frame(norm, t, fp):
                continue
            h = phash_hex(fp)
            if any((imagehash.hex_to_hash(h) - imagehash.hex_to_hash(p[3])) <= 6 for p in cands):
                continue  # near-duplicate frame
            cands.append((sharpness(fp), fp, t, h))
        cands.sort(key=lambda c: c[0], reverse=True)
        picked = cands[:MAX_FRAMES]
        if not picked:
            raise ValueError("no usable frames sampled")
        video_phash = "".join(p[3] for p in picked)
        reel.phash = video_phash
        hit = await _phash_cache_check(session, reel, video_phash)
        if hit:
            await reel_service.write_stage(
                session, reel.id, "preprocess", "done", metrics={"cache_hit": True})
            return True
        for idx, (score, fp, _t, _h) in enumerate(sorted(picked, key=lambda c: c[1].name)):
            key = f"frames/{reel.id}/{idx}.jpg"
            await store.put_bytes(key, fp.read_bytes(), "image/jpeg")
            session.add(models.Frame(reel_id=reel.id, idx=idx, storage_key=key, sharpness=score))
        await session.flush()
        await reel_service.write_stage(
            session, reel.id, "preprocess", "done",
            metrics={"frames": len(picked), "candidates": len(times), "cache_hit": False},
        )
        return False


async def _phash_cache_check(session: AsyncSession, reel: models.Reel, video_phash: str) -> bool:
    res = await session.execute(
        select(models.Reel).where(models.Reel.status == "done", models.Reel.id != reel.id)
    )
    mine = [video_phash[i:i + 16] for i in range(0, len(video_phash), 16)]
    for other in res.scalars().all():
        if not other.phash or len(other.phash) != len(video_phash):
            continue
        theirs = [other.phash[i:i + 16] for i in range(0, len(other.phash), 16)]
        dist = sum((imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b)) for a, b in zip(mine, theirs))
        if dist <= 6:
            n = await reel_service.copy_results(session, other, reel)
            log.info("preprocess phash cache hit", reel_id=reel.id, src=other.id, dist=dist, items=n)
            return True
    return False


async def _cli(reel_id: str) -> None:
    from app.core.deps import get_store

    async with SessionLocal() as session:
        reel = await session.get(models.Reel, reel_id)
        if reel is None or not reel.storage_key:
            raise SystemExit(f"reel {reel_id} not found or has no storage_key")
        raw = await get_store().download_bytes(reel.storage_key)
        hit = await run_preprocess(session, reel, raw, get_store())
        await session.commit()
        print(f"cache_hit={hit} frames_done")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Normalise video and sample the best 8 frames.")
    parser.add_argument("--reel-id", required=True, help="Reel id to preprocess")
    args = parser.parse_args(argv)
    asyncio.run(_cli(args.reel_id))


if __name__ == "__main__":
    main()
