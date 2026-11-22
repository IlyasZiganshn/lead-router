def test_create_lead_returns_201(client, lead):
    response = client.post("/leads", json=lead)
    assert response.status_code == 201
    body = response.json()
    assert body["lead"]["external_id"] == "amo-1042"
    assert body["duplicate"] is False


def test_repeated_post_is_idempotent(client, lead):
    first = client.post("/leads", json=lead)
    second = client.post("/leads", json=lead)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["lead"]["id"] == first.json()["lead"]["id"]
    assert client.get("/stats").json()["total"] == 1


def test_same_external_id_from_another_source_is_still_duplicate(client, lead):
    client.post("/leads", json=lead)
    second = client.post("/leads", json={**lead, "source": "partner"})
    assert second.status_code == 200
    assert client.get("/stats").json()["total"] == 1


def test_missing_external_id_is_rejected(client):
    response = client.post("/leads", json={"source": "site"})
    assert response.status_code == 422


def test_invalid_email_is_rejected(client, lead):
    response = client.post("/leads", json={**lead, "email": "not-an-email"})
    assert response.status_code == 422
    assert response.json()["detail"] == "invalid email"


def test_get_lead_by_id(client, lead):
    created = client.post("/leads", json=lead).json()["lead"]
    response = client.get(f"/leads/{created['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "Ilyas"


def test_get_missing_lead_returns_404(client):
    assert client.get("/leads/999").status_code == 404


def test_list_filters_by_status_and_source(client):
    client.post("/leads", json={"external_id": "a1", "source": "site", "email": "a@company.com"})
    client.post("/leads", json={"external_id": "a2", "source": "partner", "email": "b@x.io"})
    hot = client.get("/leads", params={"status": "hot"}).json()
    partner = client.get("/leads", params={"source": "partner"}).json()
    assert hot["count"] == 1
    assert partner["count"] == 1
    assert partner["items"][0]["external_id"] == "a2"


def test_list_pagination(client):
    for i in range(5):
        client.post(
            "/leads",
            json={"external_id": f"p{i}", "source": "site", "email": "a@company.com"},
        )
    page = client.get("/leads", params={"limit": 2, "offset": 2}).json()
    assert page["count"] == 2
    assert len(page["items"]) == 2


def test_patch_status_writes_event(client, lead):
    lead_id = client.post("/leads", json=lead).json()["lead"]["id"]
    response = client.patch(f"/leads/{lead_id}", json={"status": "won"})
    assert response.status_code == 200
    assert response.json()["status"] == "won"


def test_patch_unknown_status_is_rejected(client, lead):
    lead_id = client.post("/leads", json=lead).json()["lead"]["id"]
    response = client.patch(f"/leads/{lead_id}", json={"status": "banana"})
    assert response.status_code == 422


def test_patch_missing_lead_returns_404(client):
    assert client.patch("/leads/999", json={"status": "won"}).status_code == 404


def test_stats_counts_by_source_and_status(client):
    client.post("/leads", json={"external_id": "s1", "source": "site", "email": "a@company.com"})
    client.post("/leads", json={"external_id": "s2", "source": "partner", "email": "b@x.io"})
    stats = client.get("/stats").json()
    assert stats["total"] == 2
    assert stats["by_source"] == {"partner": 1, "site": 1}
    assert stats["by_status"]["hot"] == 1
    assert stats["by_status"]["warm"] == 1


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
