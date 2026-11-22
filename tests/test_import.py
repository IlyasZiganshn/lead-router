def test_import_creates_rows(client):
    csv_body = (
        "external_id,source,name,email\n"
        "c1,site,Ann,ann@company.com\n"
        "c2,partner,Bob,bob@x.io\n"
    )
    response = client.post("/import", files={"file": ("leads.csv", csv_body, "text/csv")})
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 2
    assert body["duplicates"] == 0
    assert client.get("/stats").json()["total"] == 2


def test_repeated_import_creates_zero_duplicates(client):
    csv_body = "external_id,source,name,email\nc1,site,Ann,ann@company.com\n"
    for _ in range(5):
        body = client.post("/import", files={"file": ("leads.csv", csv_body, "text/csv")}).json()
    assert body["created"] == 0
    assert body["duplicates"] == 1
    assert client.get("/stats").json()["total"] == 1


def test_import_counts_invalid_rows(client):
    csv_body = "external_id,source,email\n,site,a@company.com\nc2,,b@x.io\nc3,site,bad\n"
    body = client.post("/import", files={"file": ("leads.csv", csv_body, "text/csv")}).json()
    assert body["created"] == 0
    assert body["invalid"] == 3
    assert len(body["errors"]) == 3


def test_import_requires_external_id_column(client):
    csv_body = "source,email\nsite,a@company.com\n"
    response = client.post("/import", files={"file": ("leads.csv", csv_body, "text/csv")})
    assert response.status_code == 422


def test_import_applies_rules(client):
    csv_body = "external_id,source,email\nc9,site,a@company.com\n"
    client.post("/import", files={"file": ("leads.csv", csv_body, "text/csv")})
    lead = client.get("/leads").json()["items"][0]
    assert lead["status"] == "hot"
    assert lead["score"] == 80
