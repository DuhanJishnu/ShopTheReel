"""Auth tests: register/login/refresh rotation/logout + problem+json shape."""

EMAIL = "user@example.com"
PW = "supersecret1"


async def _register(client, email=EMAIL, password=PW):
    return await client.post("/v1/auth/register", json={"email": email, "password": password})


async def test_register_login_refresh_flow(client):
    r = await _register(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["access_token"] and body["refresh_token"]

    # duplicate -> 409 problem+json
    dup = await _register(client)
    assert dup.status_code == 409
    assert dup.json()["title"] == "Conflict"
    assert "X-Request-ID" in dup.headers

    login = await client.post("/v1/auth/login", json={"email": EMAIL, "password": PW})
    assert login.status_code == 200
    tokens = login.json()

    bad = await client.post("/v1/auth/login", json={"email": EMAIL, "password": "wrongpass1"})
    assert bad.status_code == 401

    refreshed = await client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()

    # old refresh token is rotated -> revoked
    reuse = await client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401

    out = await client.post("/v1/auth/logout", json={"refresh_token": new_tokens["refresh_token"]})
    assert out.status_code == 204
    after_logout = await client.post("/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
    assert after_logout.status_code == 401


async def test_request_id_passthrough(client):
    r = await client.get("/healthz", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"


async def test_healthz(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
