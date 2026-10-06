"""Profile CRUD + delete-my-data tests."""


async def _auth(client):
    r = await client.post("/v1/auth/register", json={"email": "p@example.com", "password": "supersecret1"})
    assert r.status_code == 201
    return r.json()


async def test_profile_crud_and_delete(client):
    tokens = await _auth(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    got = await client.get("/v1/me/profile", headers=headers)
    assert got.status_code == 200
    assert got.json()["style_tags"] == []

    put = await client.put(
        "/v1/me/profile",
        headers=headers,
        json={
            "gender": "women",
            "sizes": {"top": "M", "system": "IN"},
            "height_cm": 165,
            "budget_min": 1000,
            "budget_max": 7500,
            "style_tags": ["Quiet Luxury", "Minimalist Linen"],
            "disliked_colours": ["neon green"],
            "preferred_brands": ["Zara", "H&M"],
        },
    )
    assert put.status_code == 200, put.text
    assert put.json()["gender"] == "women"
    assert put.json()["budget_max"] == 7500

    unauth = await client.get("/v1/me/profile")
    assert unauth.status_code in (401, 403)

    delete = await client.delete("/v1/me", headers=headers)
    assert delete.status_code == 204
    after = await client.get("/v1/me/profile", headers=headers)
    assert after.status_code == 401
