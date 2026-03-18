"""
Tests de endpoints de salud y metadatos de la aplicación.
"""


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "app" in data
    assert "version" in data


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert "endpoints" in data
    assert "features" in data


def test_info(client):
    resp = client.get("/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    assert data["features"]["csv_upload"] is True
    assert data["features"]["analytics"] is True
    assert data["datasources"]["ventas"] is True


def test_docs_accesibles(client):
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_openapi_schema(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "paths" in schema
    assert "/api/ventas/upload-csv" in schema["paths"]
    assert "/api/analytics/stats" in schema["paths"]
