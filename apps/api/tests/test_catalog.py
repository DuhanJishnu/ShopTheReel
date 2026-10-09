"""Catalog tests: fusion math, mock-partner resilience, pg-gated retrieve+outfit."""

import random

import pytest
from sqlalchemy import select

from app.catalog.provider import CandidateQuery, ProductCandidate
from app.catalog.providers.dataset import DatasetProvider
from app.catalog.providers.mock_partner import CircuitOpen, MockPartnerProvider
from app.clients.embeddings import HashedTextEmbedder
from app.db import models
from app.pipeline import retrieve as rt
from tests.conftest import needs_pg


def test_fused_score_ordering():
    a = ProductCandidate(product_id="a", img_sim=0.9, text_sim=0.9, attr_match=1.0)
    b = ProductCandidate(product_id="b", img_sim=0.5, text_sim=0.5, attr_match=0.0)
    assert a.fused > b.fused
    assert a.fused == pytest.approx(0.5 * 0.9 + 0.35 * 0.9 + 0.15 * 1.0)


async def test_dataset_provider_needs_postgres(session_factory):
    import os

    async with session_factory() as s:
        provider = DatasetProvider(s)
        if os.environ.get("DATABASE_URL_TEST"):
            res = await provider.search_candidates(CandidateQuery(text_vec=[0.1] * 768, image_vec=[0.1] * 512))
            assert res == []
        else:
            with pytest.raises(RuntimeError):
                await provider.search_candidates(CandidateQuery(text_vec=[0.1], image_vec=[0.1]))


async def test_mock_partner_retries_then_raises(session_factory):
    async with session_factory() as s:
        inner = DatasetProvider(s)
        partner = MockPartnerProvider(inner, latency_ms=(0, 1), fail_rate=1.0, breaker_threshold=100,
                                      rng=random.Random(0))
        with pytest.raises(RuntimeError):
            await partner.search_candidates(CandidateQuery(text_vec=[0.1], image_vec=[0.1]))


async def test_mock_partner_breaker(session_factory):
    async with session_factory() as s:
        inner = DatasetProvider(s)
        partner = MockPartnerProvider(inner, latency_ms=(0, 1), fail_rate=1.0, breaker_threshold=1,
                                      breaker_cooldown_s=30.0, rng=random.Random(0))
        # Attempt 1 fails and opens the breaker; attempts 2-3 hit the open circuit.
        with pytest.raises(CircuitOpen):
            await partner.search_candidates(CandidateQuery(text_vec=[0.1], image_vec=[0.1]))
        with pytest.raises(CircuitOpen):
            await partner.search_candidates(CandidateQuery(text_vec=[0.1], image_vec=[0.1]))

        # Fast-forward past the cooldown: half-open attempt runs, fails, re-opens.
        import time

        partner._opened_at = time.monotonic() - 31.0
        with pytest.raises(CircuitOpen):
            await partner.search_candidates(CandidateQuery(text_vec=[0.1], image_vec=[0.1]))
        assert partner._opened_at is not None


async def test_mock_partner_rate_limit(session_factory):
    async with session_factory() as s:
        inner = DatasetProvider(s)
        limited = MockPartnerProvider(inner, latency_ms=(0, 1), rate_limit_per_min=1, rng=random.Random(0))
        limited._check_rate_limit()
        with pytest.raises(RuntimeError):
            limited._check_rate_limit()


@needs_pg
async def test_retrieve_and_outfit_end_to_end(client, session_factory, monkeypatch):
    import app.workers.queue as queue_mod

    async def noop(reel_id: str) -> None:
        return None

    monkeypatch.setattr(queue_mod, "enqueue_process", noop)
    reg = await client.post("/v1/auth/register", json={"email": "cat@example.com", "password": "supersecret1"})
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    emb = HashedTextEmbedder()
    async with session_factory() as s:
        vec = emb.embed_text("olive green solid oversized t-shirt")
        for i, price in enumerate([999.0, 1499.0, 499.0]):
            s.add(models.Product(
                provider="dataset", sku=f"sku-{i}", title=f"Product {i}", brand="Demo",
                category="top", subcategory="t-shirt", gender="unisex", colours=["olive green"],
                pattern="solid", fit="oversized", price=price, currency="INR",
                sizes_available=["S", "M", "L"], in_stock=True, buy_url=f"https://partner.example/p/sku-{i}",
                attribute_text="olive green solid oversized t-shirt",
                text_vec=vec, image_vec=vec[:512] + [0.0] * (512 - len(vec[:512])),
            ))
        user = (await s.execute(select(models.User).where(models.User.email == "cat@example.com"))).scalars().first()
        assert user is not None
        profile = await s.get(models.Profile, user.id)  # register() already created it
        assert profile is not None
        profile.gender = "unisex"
        await s.commit()
    created = await client.post("/v1/reels", json={"kind": "images", "storage_keys": ["images/x.jpg"]}, headers=headers)
    rid = created.json()["id"]
    async with session_factory() as s:
        reel = await s.get(models.Reel, rid)
        assert reel is not None
        s.add(models.DetectedItem(
            reel_id=rid, category="top", subcategory="t-shirt", colours=["olive green"],
            pattern="solid", fit="oversized", confidence=0.9, attribute_text="olive green solid oversized t-shirt",
            text_vec=emb.embed_text("olive green solid oversized t-shirt"),
            embedding=emb.embed_text("olive green solid oversized t-shirt")[:512]
            + [0.0] * (512 - len(emb.embed_text("olive green solid oversized t-shirt")[:512])),
        ))
        await s.commit()
        n = await rt.run_retrieve(s, reel)
        assert n >= 1
        await s.commit()
    out = await client.get(f"/v1/reels/{rid}/outfit?tier=exact", headers=headers)
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["tier"] == "exact"
    assert body["items"][0]["match"]["product"]["price_display"].startswith("₹")
    assert body["total_price"] > 0
    bad_tier = await client.get(f"/v1/reels/{rid}/outfit?tier=gold", headers=headers)
    assert bad_tier.status_code == 422
