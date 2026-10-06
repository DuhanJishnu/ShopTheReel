"""Upload presign tests (FakeStore, no network)."""


async def _auth(client, email="u@example.com"):
    r = await client.post("/v1/auth/register", json={"email": email, "password": "supersecret1"})
    assert r.status_code == 201
    return r.json()


async def test_presign_ok_and_validation(client):
    tokens = await _auth(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    ok = await client.post(
        "/v1/uploads/presign", headers=headers, json={"content_type": "video/mp4", "size_bytes": 1024, "kind": "video"}
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["storage_key"].startswith("videos/")
    assert body["upload_url"]

    bad_type = await client.post(
        "/v1/uploads/presign", headers=headers, json={"content_type": "video/avi", "size_bytes": 10, "kind": "video"}
    )
    assert bad_type.status_code == 415

    too_big = await client.post(
        "/v1/uploads/presign",
        headers=headers,
        json={"content_type": "video/mp4", "size_bytes": 1024 * 1024 * 1024, "kind": "video"},
    )
    assert too_big.status_code == 413

    anon = await client.post("/v1/uploads/presign", json={"content_type": "video/mp4", "size_bytes": 10, "kind": "video"})
    assert anon.status_code in (401, 403)
