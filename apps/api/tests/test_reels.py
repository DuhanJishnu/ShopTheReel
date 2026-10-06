"""Reels API tests: idempotent create, status/items/history/retry, SSE snapshot."""

EMAIL = "reels@example.com"
PW = "supersecret1"


async def _register(client, email=EMAIL):
    r = await client.post("/v1/auth/register", json={"email": email, "password": PW})
    assert r.status_code == 201, r.text
    return r.json()


async def _no_enqueue(monkeypatch):
    calls: list[str] = []

    async def fake_enqueue(reel_id: str) -> None:
        calls.append(reel_id)

    monkeypatch.setattr("app.workers.queue.enqueue_process", fake_enqueue)
    return calls


async def test_create_idempotent_and_link(client, monkeypatch):
    tokens = await _register(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    calls = await _no_enqueue(monkeypatch)

    body = {"kind": "video", "storage_keys": ["videos/a.mp4"]}
    r1 = await client.post("/v1/reels", json=body, headers={**headers, "Idempotency-Key": "k-1"})
    assert r1.status_code == 202, r1.text
    r2 = await client.post("/v1/reels", json=body, headers={**headers, "Idempotency-Key": "k-1"})
    assert r2.json()["id"] == r1.json()["id"]
    assert calls == [r1.json()["id"]]  # second call did not re-enqueue

    link = await client.post("/v1/reels", json={"kind": "link", "source_url": "https://instagram.com/reel/x"}, headers=headers)
    assert link.json()["status"] == "needs_media"
    assert len(calls) == 1  # link-only enqueues nothing

    bad = await client.post("/v1/reels", json={"kind": "video", "storage_keys": []}, headers=headers)
    assert bad.status_code == 422
    assert bad.json()["title"] == "Unprocessable"

    anon = await client.post("/v1/reels", json=body)
    assert anon.status_code in (401, 403)


async def test_status_items_history_retry(client, monkeypatch):
    tokens = await _register(client, email="r2@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await _no_enqueue(monkeypatch)

    created = await client.post("/v1/reels", json={"kind": "video", "storage_keys": ["videos/b.mp4"]}, headers=headers)
    rid = created.json()["id"]

    status = await client.get(f"/v1/reels/{rid}", headers=headers)
    assert status.status_code == 200
    assert status.json()["status"] == "queued"
    assert status.json()["stages"][0]["stage"] == "ingest"

    items = await client.get(f"/v1/reels/{rid}/items", headers=headers)
    assert items.json() == []

    hist = await client.get("/v1/reels", headers=headers)
    assert hist.json()["items"][0]["id"] == rid
    assert hist.json()["next_cursor"] is None

    retry = await client.post(f"/v1/reels/{rid}/retry", headers=headers)
    assert retry.status_code == 409  # queued reels have nothing to retry

    missing = await client.get("/v1/reels/does-not-exist", headers=headers)
    assert missing.status_code == 404


async def test_events_missing_reel(client):
    tokens = await _register(client, email="r3@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    events = await client.get("/v1/reels/does-not-exist/events", headers=headers)
    assert events.status_code == 404
    assert "not found" in events.text
