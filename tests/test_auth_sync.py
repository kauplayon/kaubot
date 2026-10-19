import os

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-change-this")
os.environ.pop("DATABASE_URL", None)

import pytest

from app import app
from cosmo_storage import configure_storage


@pytest.fixture()
def client():
    assert configure_storage("sqlite:///:memory:")
    app.config.update(TESTING=True, SECRET_KEY="test-only-secret-key-change-this", SESSION_COOKIE_SECURE=False)
    with app.test_client() as client:
        yield client


def csrf(client):
    response = client.get("/api/auth/status")
    assert response.status_code == 200
    return response.get_json()["csrf_token"]


def register(client, email="test@example.com", password="safe-password-123"):
    token = csrf(client)
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": token},
    )


def test_registration_and_password_is_not_returned(client):
    response = register(client)
    assert response.status_code == 201
    assert response.get_json()["email"] == "test@example.com"
    assert "password" not in response.get_json()
    assert client.get("/api/sync").status_code == 200


def test_sync_round_trip_and_isolation(client):
    assert register(client).status_code == 201
    token = csrf(client)
    payload = {
        "memory": "Prefere respostas objetivas.",
        "conversations": [{"id": "conv-1", "title": "Teste", "messages": [], "updatedAt": 1}],
        "tasks": [{"text": "Estudar Python", "done": False}],
        "notes": [{"title": "Ideia", "text": "Criar um HUD"}],
        "preferences": {"jarvisMode": True},
    }
    saved = client.put("/api/sync", json=payload, headers={"X-CSRF-Token": token})
    assert saved.status_code == 200
    loaded = client.get("/api/sync").get_json()
    assert loaded["memory"] == payload["memory"]
    assert loaded["conversations"][0]["id"] == "conv-1"
    assert loaded["tasks"][0]["text"] == "Estudar Python"
    assert loaded["notes"][0]["title"] == "Ideia"
    assert loaded["preferences"]["jarvisMode"] is True


def test_sync_rejects_missing_csrf(client):
    assert register(client).status_code == 201
    response = client.put("/api/sync", json={"memory": "x"})
    assert response.status_code == 400


def test_login_and_logout(client):
    assert register(client).status_code == 201
    logout = client.post(
        "/api/auth/logout",
        json={},
        headers={"X-CSRF-Token": csrf(client)},
    )
    assert logout.status_code == 200
    assert client.get("/api/sync").status_code == 401
    login = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "safe-password-123"},
        headers={"X-CSRF-Token": csrf(client)},
    )
    assert login.status_code == 200
    assert client.get("/api/sync").status_code == 200


def test_account_delete_requires_password(client):
    assert register(client).status_code == 201
    bad = client.delete(
        "/api/account",
        json={"password": "wrong-password"},
        headers={"X-CSRF-Token": csrf(client)},
    )
    assert bad.status_code == 403
    good = client.delete(
        "/api/account",
        json={"password": "safe-password-123"},
        headers={"X-CSRF-Token": csrf(client)},
    )
    assert good.status_code == 200
    assert client.get("/api/sync").status_code == 401


def test_password_policy_and_payload_limits(client):
    token = csrf(client)
    short = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "123"},
        headers={"X-CSRF-Token": token},
    )
    assert short.status_code == 400
    assert register(client, email="long@example.com").status_code == 201
    response = client.put(
        "/api/sync",
        json={"memory": "x" * 1501},
        headers={"X-CSRF-Token": csrf(client)},
    )
    assert response.status_code == 400
