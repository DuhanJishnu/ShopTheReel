"""Phase 4 tests: taste EMA, feedback flow, tier composition, looks/boards."""

import uuid

import pytest
from sqlalchemy import select

from app.clients.embeddings import HashedTextEmbedder
from app.db import models
from app.db.vectors import as_list, cosine, ema_step
from app.pipeline import compose as co
from app.pipeline import rerank as rr
from app.services import personalisation as perso
from tests.conftest import needs_pg


def test_vector_math():
    assert as_list(None) is None
    assert as_list([1, 2]) == [1.0, 2.0]
    assert as_list("[0.5, -0.5]") == [0.5, -0.5]
    assert as_list("nope") is None
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine([1.0], [1.0, 0.0]) == 0.0
    v = ema_step(None, [3.0, 4.0], 0.2)
    assert v == [3.0, 4.0]
    toward = ema_step([1.0, 0.0], [1.0, 0.0], 0.2)
    assert toward[0] > 0.99
    away = ema_step([1.0, 0.0], [1.0, 0.0], 0.5, away=True)
    assert away[0] < 1.0


async def _user(client, email=None):
    email = email or f"{uuid.uuid4().hex}@example.com"
    r = await client.post("/v1/auth/register", json={"email": email, "password": "supersecret1"})
    assert r.status_code == 201
    return r.json()


async def test_feedback_flow(client, session_factory, monkeypatch):
    import app.workers.queue as queue_mod

    enqueued: list[str] = []

    async def fake_taste(fid: str) -> None:
        enqueued.append(fid)

    monkeypatch.setattr(queue_mod, "enqueue_taste", fake_taste)
    tokens = await _user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    async with session_factory() as s:
        reel = models.Reel(user_id=tokens["user"]["id"], kind="link", source_url="x", status="done")
        s.add(reel)
        await s.flush()
        item = models.DetectedItem(reel_id=reel.id, category="top", confidence=0.9)
        s.add(item)
        await s.flush()
        prod = models.Product(provider="dataset", sku="fb-1", title="T", brand="B", category="top",
                              price=100, sizes_available=["M"],
                              text_vec=HashedTextEmbedder().embed_text("red top"))
        s.add(prod)
        await s.flush()
        match = models.Match(item_id=item.id, product_id=prod.id, tier="exact", score=0.8, rank=0)
        s.add(match)
        await s.commit()
        mid = match.id
    ok = await client.post(f"/v1/matches/{mid}/feedback", json={"signal": "like"}, headers=headers)
    assert ok.status_code == 200
    assert enqueued == [ok.json()["feedback_id"]]
    bad = await client.post(f"/v1/matches/{mid}/feedback", json={"signal": "meh"}, headers=headers)
    assert bad.status_code == 422
    missing = await client.post("/v1/matches/nope/feedback", json={"signal": "like"}, headers=headers)
    assert missing.status_code == 404
    # Another user cannot touch this match.
    other = await _user(client)
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    forbidden = await client.post(f"/v1/matches/{mid}/feedback", json={"signal": "like"}, headers=other_headers)
    assert forbidden.status_code == 404
    # Worker body applies the taste update.
    async with session_factory() as s:
        await perso.apply_taste_update(s, ok.json()["feedback_id"])
        profile = await s.get(models.Profile, tokens["user"]["id"])
        assert profile is not None and as_list(profile.taste_vec) is not None


async def test_looks_boards_share(client):
    tokens = await _user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    look = await client.post("/v1/looks", json={"title": "Evening", "match_ids": []}, headers=headers)
    assert look.status_code == 201
    lid = look.json()["id"]
    mine = await client.get("/v1/looks", headers=headers)
    assert len(mine.json()["items"]) == 1
    shared = await client.post(f"/v1/looks/{lid}/share", headers=headers)
    slug = shared.json()["share_url"].rsplit("/", 1)[-1]
    public = await client.get(f"/v1/public/looks/{slug}")
    assert public.status_code == 200
    assert public.json()["id"] == lid
    board = await client.post("/v1/boards", json={"name": "Festive"}, headers=headers)
    attach = await client.post(f"/v1/boards/{board.json()['id']}/looks", json={"look_id": lid}, headers=headers)
    assert attach.json()["look_ids"] == [lid]
    boards = await client.get("/v1/boards", headers=headers)
    assert boards.json()["items"][0]["look_ids"] == [lid]


async def test_style_dna_endpoint(client, session_factory):
    tokens = await _user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    dna = await client.get("/v1/me/style-dna", headers=headers)
    assert dna.status_code == 200
    assert dna.json()["taste_trained"] is False


@needs_pg
async def test_likes_shift_rankings(client, session_factory, monkeypatch):
    import app.workers.queue as queue_mod

    async def noop(fid: str) -> None:
        return None

    monkeypatch.setattr(queue_mod, "enqueue_taste", noop)
    tokens = await _user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    style_a = "style-a shared attribute text for taste"
    style_b = "style-b totally different attribute text here"
    from app.clients.embeddings import HashedTextEmbedder

    emb = HashedTextEmbedder()
    vec_a, vec_b = emb.embed_text(style_a), emb.embed_text(style_b)
    async with session_factory() as s:
        user_id = tokens["user"]["id"]
        reel = models.Reel(user_id=user_id, kind="images", storage_key="images/s.jpg", status="done")
        s.add(reel)
        await s.flush()
        item = models.DetectedItem(reel_id=reel.id, category="top", colours=["red"], pattern="solid",
                                   fit="regular", confidence=0.9, attribute_text=style_a,
                                   text_vec=vec_a, embedding=vec_a[:512])
        s.add(item)
        await s.flush()
        prods = []
        for i, (text, vec) in enumerate([("other one", vec_b), ("other two", emb.embed_text("other two"))]):
            p = models.Product(provider="dataset", sku=f"taste-{i}", title=text, brand="X",
                               category="top", colours=["blue"], pattern="striped", fit="slim",
                               price=1000, sizes_available=["M"], text_vec=vec,
                               image_vec=(vec[:512] if len(vec) >= 512 else vec + [0.0] * (512 - len(vec))))
            s.add(p)
            prods.append(p)
        pa = models.Product(provider="dataset", sku="taste-a", title=style_a, brand="X", category="top",
                            colours=["red"], pattern="solid", fit="regular", price=1000,
                            sizes_available=["M"], text_vec=vec_a,
                            image_vec=vec_a[:512] if len(vec_a) >= 512 else vec_a + [0.0] * (512 - len(vec_a)))
        s.add(pa)
        await s.flush()
        matches = []
        for p in prods + [pa]:
            m = models.Match(item_id=item.id, product_id=p.id, tier="exact", score=0.5, rank=0)
            s.add(m)
            matches.append(m)
        await s.commit()
        target = next(m for m in matches if m.product_id == pa.id)
        for _ in range(5):
            fb = await perso.record_feedback(s, await s.get(models.User, user_id), target.id, "like")
            await perso.apply_taste_update(s, fb.id)
        n = await rr.run_rerank(s, reel)
        assert n == 3
        await s.commit()
        rows = (await s.execute(select(models.Match).where(models.Match.item_id == item.id))).scalars().all()
        by_product = {m.product_id: m for m in rows}
        assert by_product[pa.id].rank == 0
        assert by_product[pa.id].score > 0.5
        assert by_product[pa.id].reason
    out = await client.get(f"/v1/reels/{reel.id}/outfit?tier=exact", headers=headers)
    assert out.json()["items"][0]["match"]["product"]["sku"] == "taste-a"


@needs_pg
async def test_tier_price_ordering(client, session_factory, monkeypatch):
    import app.workers.queue as queue_mod

    async def noop(fid: str) -> None:
        return None

    monkeypatch.setattr(queue_mod, "enqueue_taste", noop)
    tokens = await _user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    async with session_factory() as s:
        user_id = tokens["user"]["id"]
        reel = models.Reel(user_id=user_id, kind="images", storage_key="images/t.jpg", status="done")
        s.add(reel)
        await s.flush()
        item = models.DetectedItem(reel_id=reel.id, category="top", confidence=0.9)
        s.add(item)
        await s.flush()
        specs = [("A", 2000.0, 0.90), ("B", 1500.0, 0.80), ("C", 500.0, 0.70)]
        for rank, (brand, price, score) in enumerate(specs):
            p = models.Product(provider="dataset", sku=f"tier-{brand}", title=brand, brand=brand,
                               category="top", price=price, sizes_available=["M"])
            s.add(p)
            await s.flush()
            s.add(models.Match(item_id=item.id, product_id=p.id, tier="exact", score=score, rank=rank))
        await s.commit()
        out = await co.run_compose(s, reel)
        await s.commit()
        totals = out["totals"]
        assert totals["budget"] <= totals["similar"] <= totals["exact"]
        assert totals == {"exact": 2000.0, "similar": 1500.0, "budget": 500.0}
    for tier, price in (("exact", 2000.0), ("similar", 1500.0), ("budget", 500.0)):
        res = await client.get(f"/v1/reels/{reel.id}/outfit?tier={tier}", headers=headers)
        assert res.status_code == 200, res.text
        assert res.json()["total_price"] == price
