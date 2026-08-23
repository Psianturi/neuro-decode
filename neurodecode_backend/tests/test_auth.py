"""
Verifies the auth/ownership fix on the caregiver-facing routers: no token ->
401, a token that doesn't own the resource -> 403, and profile access is
correctly isolated by the verified uid rather than a client-supplied query
param. Runs fully in-memory (Firestore disabled via conftest.py) and stubs
token verification at app.auth._verify_token_sync, so it needs no real
Firebase project or network access.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import auth as auth_module
from app import state
from app.routers import notifications as notifications_router
from app.routers import profiles as profiles_router
from app.routers import sessions as sessions_router


@pytest.fixture
def client() -> TestClient:
    test_app = FastAPI()
    test_app.include_router(sessions_router.router, prefix="/sessions")
    test_app.include_router(notifications_router.router, prefix="/notifications")
    test_app.include_router(profiles_router.router, prefix="/profiles")
    return TestClient(test_app)


@pytest.fixture(autouse=True)
def seeded_state():
    """Reset the shared in-memory stores and seed one owned-by-alice resource
    of each kind before every test."""
    state.session_store._memory.clear()
    state.notification_store._memory.clear()
    state.profile_store._profiles.clear()

    state.session_store._memory.appendleft(
        {"session_id": "sess-1", "user_id": "uid-alice", "caregiver_rating": None}
    )
    state.notification_store._memory.appendleft(
        {"notification_id": "notif-1", "user_id": "uid-alice", "status": "unread"}
    )
    key = state.profile_store._scope_key(user_id="uid-alice", profile_id="joy1")
    state.profile_store._profiles[key] = {"profile_id": "joy1", "child_name": "Joy"}
    yield


def _fake_verifier(monkeypatch: pytest.MonkeyPatch, valid_tokens: dict[str, str]) -> None:
    def fake(token: str) -> str:
        if token not in valid_tokens:
            raise ValueError("invalid token")
        return valid_tokens[token]

    monkeypatch.setattr(auth_module, "_verify_token_sync", fake)


def test_sessions_requires_auth_header(client: TestClient) -> None:
    assert client.get("/sessions").status_code == 401


def test_sessions_rejects_invalid_token(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_verifier(monkeypatch, {})
    resp = client.get("/sessions", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


def test_rate_session_forbidden_for_non_owner(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_verifier(monkeypatch, {"valid-mallory": "uid-mallory"})
    resp = client.patch(
        "/sessions/sess-1/rate",
        params={"rating": 5},
        headers={"Authorization": "Bearer valid-mallory"},
    )
    assert resp.status_code == 403


def test_rate_session_succeeds_for_owner(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_verifier(monkeypatch, {"valid-alice": "uid-alice"})
    resp = client.patch(
        "/sessions/sess-1/rate",
        params={"rating": 5},
        headers={"Authorization": "Bearer valid-alice"},
    )
    assert resp.status_code == 200
    assert resp.json()["caregiver_rating"] == 5


def test_notification_mark_read_forbidden_for_non_owner(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_verifier(monkeypatch, {"valid-mallory": "uid-mallory"})
    resp = client.post(
        "/notifications/notif-1/read",
        headers={"Authorization": "Bearer valid-mallory"},
    )
    assert resp.status_code == 403


def test_notification_mark_read_succeeds_for_owner(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_verifier(monkeypatch, {"valid-alice": "uid-alice"})
    resp = client.post(
        "/notifications/notif-1/read",
        headers={"Authorization": "Bearer valid-alice"},
    )
    assert resp.status_code == 200


def test_profile_invisible_to_non_owner(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_verifier(monkeypatch, {"valid-mallory": "uid-mallory"})
    resp = client.get("/profiles/joy1", headers={"Authorization": "Bearer valid-mallory"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "empty"


def test_profile_visible_to_owner(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_verifier(monkeypatch, {"valid-alice": "uid-alice"})
    resp = client.get("/profiles/joy1", headers={"Authorization": "Bearer valid-alice"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
