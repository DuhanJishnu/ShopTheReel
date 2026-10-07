"""Google sign-in tests (verify_oauth2_token mocked; no network)."""

import pytest

from app.core.config import settings


def _claims(**over):
    base = {"sub": "google-123", "email": "g@example.com", "email_verified": True, "aud": "web-id"}
    base.update(over)
    return base


def _mock_verify(monkeypatch, claims=None, exc=None):
    import app.api.v1.auth as auth_router

    def fake(token, request):
        if exc is not None:
            raise exc
        return claims if claims is not None else _claims()

    monkeypatch.setattr(auth_router.google_id_token, "verify_oauth2_token", fake)
    monkeypatch.setattr(settings, "google_allowed_client_ids", "web-id")


async def test_google_unconfigured_returns_501(client):
    r = await client.post("/v1/auth/google", json={"id_token": "x"})
    assert r.status_code == 501


async def test_google_create_link_and_login(client, monkeypatch):
    _mock_verify(monkeypatch)
    r1 = await client.post("/v1/auth/google", json={"id_token": "tok"})
    assert r1.status_code == 200, r1.text
    uid = r1.json()["user"]["id"]

    r2 = await client.post("/v1/auth/google", json={"id_token": "tok2"})
    assert r2.json()["user"]["id"] == uid  # same sub → same user

    # Google-only account rejects password login
    bad = await client.post("/v1/auth/login", json={"email": "g@example.com", "password": "whatever12"})
    assert bad.status_code == 401


async def test_google_links_existing_email(client, monkeypatch):
    reg = await client.post("/v1/auth/register", json={"email": "both@example.com", "password": "supersecret1"})
    assert reg.status_code == 201
    _mock_verify(monkeypatch, _claims(sub="google-999", email="both@example.com"))
    r = await client.post("/v1/auth/google", json={"id_token": "tok"})
    assert r.status_code == 200
    assert r.json()["user"]["id"] == reg.json()["user"]["id"]
    # password login still works after linking
    ok = await client.post("/v1/auth/login", json={"email": "both@example.com", "password": "supersecret1"})
    assert ok.status_code == 200


@pytest.mark.parametrize("claims,exc", [
    (_claims(aud="evil"), None),
    (_claims(email_verified=False), None),
    (_claims(email=""), None),
    (None, ValueError("bad signature")),
])
async def test_google_rejects_bad_tokens(client, monkeypatch, claims, exc):
    _mock_verify(monkeypatch, claims, exc)
    r = await client.post("/v1/auth/google", json={"id_token": "tok"})
    assert r.status_code == 401
