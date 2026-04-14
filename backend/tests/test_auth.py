"""
Tests del módulo de autenticación.
Cubre: register, login, /me, /config y que los endpoints existentes
siguen funcionando sin token (soft auth).
"""

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _register(client, email="test@auth.com", password="password123", display_name=None):
    body = {"email": email, "password": password}
    if display_name:
        body["display_name"] = display_name
    return client.post("/api/auth/register", json=body)


def _login(client, email="test@auth.com", password="password123"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Register ──────────────────────────────────────────────────────────────────

def test_register_success(auth_client):
    res = _register(auth_client)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "test@auth.com"
    assert data["user"]["config"]["language"] == "es"
    assert data["user"]["config"]["theme"] == "light"


def test_register_with_display_name(auth_client):
    res = _register(auth_client, display_name="Juan García")
    assert res.status_code == 200
    assert res.json()["user"]["display_name"] == "Juan García"


def test_register_duplicate_email(auth_client):
    _register(auth_client)
    res = _register(auth_client)
    assert res.status_code == 409


def test_register_password_too_short(auth_client):
    res = auth_client.post("/api/auth/register", json={"email": "x@x.com", "password": "short"})
    assert res.status_code == 422  # pydantic validation


# ── Login ─────────────────────────────────────────────────────────────────────

def test_login_success(auth_client):
    _register(auth_client)
    res = _login(auth_client)
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password(auth_client):
    _register(auth_client)
    res = _login(auth_client, password="wrongpassword")
    assert res.status_code == 401


def test_login_nonexistent_user(auth_client):
    res = _login(auth_client, email="noexiste@test.com")
    assert res.status_code == 401


# ── /me ───────────────────────────────────────────────────────────────────────

def test_get_me_authenticated(auth_client):
    token = _register(auth_client).json()["access_token"]
    res = auth_client.get("/api/auth/me", headers=_auth_header(token))
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "test@auth.com"
    assert "config" in data


def test_get_me_no_token(auth_client):
    res = auth_client.get("/api/auth/me")
    assert res.status_code == 401


def test_get_me_invalid_token(auth_client):
    res = auth_client.get("/api/auth/me", headers=_auth_header("token.invalido.xd"))
    assert res.status_code == 401


# ── /config ───────────────────────────────────────────────────────────────────

def test_update_config_language(auth_client):
    token = _register(auth_client).json()["access_token"]
    res = auth_client.patch(
        "/api/auth/config",
        json={"language": "en"},
        headers=_auth_header(token),
    )
    assert res.status_code == 200
    assert res.json()["language"] == "en"


def test_update_config_theme(auth_client):
    token = _register(auth_client).json()["access_token"]
    res = auth_client.patch(
        "/api/auth/config",
        json={"theme": "dark"},
        headers=_auth_header(token),
    )
    assert res.status_code == 200
    assert res.json()["theme"] == "dark"


def test_update_config_persisted(auth_client):
    """El cambio de config persiste: verificarlo con /me."""
    token = _register(auth_client).json()["access_token"]
    auth_client.patch("/api/auth/config", json={"language": "en"}, headers=_auth_header(token))
    me = auth_client.get("/api/auth/me", headers=_auth_header(token)).json()
    assert me["config"]["language"] == "en"


def test_update_config_invalid_language(auth_client):
    token = _register(auth_client).json()["access_token"]
    res = auth_client.patch(
        "/api/auth/config",
        json={"language": "fr"},
        headers=_auth_header(token),
    )
    assert res.status_code == 400


def test_update_config_no_token(auth_client):
    res = auth_client.patch("/api/auth/config", json={"language": "en"})
    assert res.status_code == 401


# ── Logout ────────────────────────────────────────────────────────────────────

def test_logout(auth_client):
    token = _register(auth_client).json()["access_token"]
    res = auth_client.post("/api/auth/logout", headers=_auth_header(token))
    assert res.status_code == 204


# ── Soft auth: endpoints existentes funcionan sin token ───────────────────────

def test_ventas_no_auth_required(client):
    """Los endpoints existentes siguen funcionando sin autenticación."""
    res = client.get("/api/ventas/stats/count")
    assert res.status_code == 200


def test_analytics_no_auth_required(client):
    res = client.get("/api/analytics/alertas")
    assert res.status_code == 200


def test_health_no_auth_required(client):
    res = client.get("/health")
    assert res.status_code == 200
