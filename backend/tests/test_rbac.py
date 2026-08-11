"""
RBAC security tests — verifies that authorization is enforced server-side
regardless of UI state, per soc-triager-security skill:

  "POST /api/incidents/:id/approve with an analyst JWT → 403"
  "Forged-signature JWT → 401"
  "Expired JWT → 401"  
  "Approver JWT calling approve → 200"

These tests call the FastAPI app directly via httpx TestClient.
"""

import pytest
import jwt as pyjwt
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, UTC


@pytest.fixture(scope="module")
def app():
    """Import and return the FastAPI app (seeded with mock data)."""
    from backend.api.main import app
    return app


@pytest.fixture(scope="module")
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def analyst_token():
    """Issue a valid analyst JWT."""
    from backend.api.auth_middleware import create_access_token
    return create_access_token("analyst@test.com", "analyst")


@pytest.fixture(scope="module")
def senior_analyst_token():
    from backend.api.auth_middleware import create_access_token
    return create_access_token("senior@test.com", "senior_analyst")


@pytest.fixture(scope="module")
def approver_token():
    from backend.api.auth_middleware import create_access_token
    return create_access_token("approver@test.com", "approver")


# ─── Authentication Tests ─────────────────────────────────────────────────────

def test_no_token_returns_401(client):
    """All protected endpoints must return 401 without a token."""
    res = client.get("/api/alerts")
    assert res.status_code == 401


def test_forged_signature_returns_401(client):
    """A JWT signed with a different secret must be rejected."""
    forged = pyjwt.encode(
        {"sub": "hacker@evil.com", "role": "approver", "exp": datetime.now(UTC) + timedelta(hours=1)},
        key="wrong-secret",
        algorithm="HS256",
    )
    res = client.get("/api/alerts", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 401


def test_expired_token_returns_401(client):
    """An expired JWT must be rejected."""
    from backend.api.auth_middleware import SECRET_KEY, ALGORITHM
    expired = pyjwt.encode(
        {"sub": "expired@test.com", "role": "analyst", "exp": datetime.now(UTC) - timedelta(hours=1)},
        key=SECRET_KEY,
        algorithm=ALGORITHM,
    )
    res = client.get("/api/alerts", headers={"Authorization": f"Bearer {expired}"})
    assert res.status_code == 401


def test_valid_analyst_token_can_read_alerts(client, analyst_token):
    """Valid analyst JWT must be able to read alerts."""
    res = client.get("/api/alerts", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res.status_code == 200
    assert "items" in res.json()


# ─── RBAC Authorization Tests ─────────────────────────────────────────────────

def test_analyst_cannot_approve_playbook(client, analyst_token):
    """
    CRITICAL: Analyst JWT calling POST /api/incidents/:id/approve → 403.
    This is the real security control — UI gate is cosmetic only.
    """
    res = client.post(
        "/api/incidents/inc_a001/approve",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert res.status_code == 403
    assert "role" in res.json().get("detail", "").lower() or "insufficient" in res.json().get("detail", "").lower()


def test_senior_analyst_cannot_approve_playbook(client, senior_analyst_token):
    """Senior Analyst should also be blocked from approving playbooks."""
    res = client.post(
        "/api/incidents/inc_a001/approve",
        headers={"Authorization": f"Bearer {senior_analyst_token}"},
    )
    assert res.status_code == 403


def test_approver_can_approve_playbook(client, approver_token):
    """Approver JWT calling approve → 200."""
    res = client.post(
        "/api/incidents/inc_a001/approve",
        headers={"Authorization": f"Bearer {approver_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["approved"] is True
    assert data["incident_id"] == "inc_a001"


def test_analyst_can_update_alert_status(client, analyst_token):
    """Analyst should be able to ack/close their own alerts."""
    res = client.post(
        "/api/alerts/a001/status",
        json={"status": "ack"},
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ack"


def test_invalid_status_rejected(client, analyst_token):
    """Invalid status values must be rejected with 400."""
    res = client.post(
        "/api/alerts/a001/status",
        json={"status": "hacked"},
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert res.status_code == 400


def test_login_endpoint_is_public(client):
    """POST /api/auth/login must be accessible without a JWT."""
    res = client.post(
        "/api/auth/login",
        json={"email": "test@test.com", "role": "analyst"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_health_is_public(client):
    """GET /health must be accessible without auth."""
    res = client.get("/health")
    assert res.status_code == 200


def test_invalid_role_in_login_rejected(client):
    """Login with an invalid role must return 400."""
    res = client.post(
        "/api/auth/login",
        json={"email": "test@test.com", "role": "superadmin"},
    )
    assert res.status_code == 400
