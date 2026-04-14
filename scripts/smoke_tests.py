"""
Post-deploy smoke tests for WhoIsMe API.

Run against live environment:
  SMOKE_BASE_URL=https://api.whoisme.io pipenv run python -m pytest scripts/smoke_tests.py -v

Optional: set SMOKE_TEST_USERNAME to test public profile retrieval.
"""
import os

import pytest
import requests

pytestmark = pytest.mark.smoke

BASE_URL     = os.environ.get("SMOKE_BASE_URL", "https://api.whoisme.io").rstrip("/")
TIMEOUT_SLOW = 30   # Bedrock-backed endpoints
TIMEOUT_FAST = 10   # DynamoDB-only endpoints


# ── Session fixture ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def interview_session():
    """Create one session shared across all session-dependent smoke tests."""
    r = requests.post(f"{BASE_URL}/interview", timeout=TIMEOUT_SLOW)
    assert r.status_code == 200, f"POST /interview failed: {r.status_code} {r.text}"
    body = r.json()
    sid = body.get("session_id") or body.get("sessionId")
    assert sid, f"No session_id in response: {body}"
    return sid


# ── Interview smoke tests ─────────────────────────────────────────────────────

@pytest.mark.flaky(retries=3, delay=15)
def test_create_interview(interview_session):
    """POST /interview returns a session_id and first question."""
    assert interview_session is not None


@pytest.mark.flaky(retries=2, delay=5)
def test_respond_to_question(interview_session):
    """POST /interview/{id}/respond returns next question."""
    r = requests.post(
        f"{BASE_URL}/interview/{interview_session}/respond",
        json={"text": "I work as a software engineer building developer tools."},
        timeout=TIMEOUT_SLOW,
    )
    assert r.status_code == 200, f"Unexpected {r.status_code}: {r.text}"
    assert "message" in r.json()


def test_get_session_state(interview_session):
    """GET /interview/{id} returns session metadata."""
    r = requests.get(f"{BASE_URL}/interview/{interview_session}", timeout=TIMEOUT_FAST)
    assert r.status_code == 200, f"Unexpected {r.status_code}: {r.text}"
    body = r.json()
    assert "phase" in body
    assert "questions_remaining" in body


def test_get_nonexistent_session_returns_404():
    """GET /interview/{id} with unknown ID returns 404."""
    r = requests.get(
        f"{BASE_URL}/interview/00000000-0000-0000-0000-000000000000",
        timeout=TIMEOUT_FAST,
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"


# ── User / profile smoke tests ────────────────────────────────────────────────

def test_public_profile_known_user():
    """GET /users/profile/{username} returns profile for a known published user."""
    username = os.environ.get("SMOKE_TEST_USERNAME")
    if not username:
        pytest.skip("SMOKE_TEST_USERNAME not set")
    r = requests.get(f"{BASE_URL}/users/profile/{username}", timeout=TIMEOUT_FAST)
    assert r.status_code == 200, f"Unexpected {r.status_code}: {r.text}"
    body = r.json()
    assert "files" in body
    assert "visibility" in body


def test_public_profile_unknown_user_returns_404():
    """GET /users/profile/{username} with unknown username returns 404."""
    r = requests.get(
        f"{BASE_URL}/users/profile/definitely-does-not-exist-xyz987abc",
        timeout=TIMEOUT_FAST,
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"


# ── Auth / admin smoke tests ──────────────────────────────────────────────────

def test_admin_login_always_returns_ok():
    """POST /admin/login always returns ok (never reveals whether email is authorized)."""
    r = requests.post(
        f"{BASE_URL}/admin/login",
        json={"email": "smoke-test@example.com"},
        timeout=TIMEOUT_FAST,
    )
    assert r.status_code == 200, f"Unexpected {r.status_code}: {r.text}"
    assert r.json().get("ok") is True


# ── Error reporting smoke test ────────────────────────────────────────────────

def test_error_reporting_endpoint():
    """POST /errors accepts client error reports."""
    r = requests.post(
        f"{BASE_URL}/errors",
        json={"error_type": "smoke_test", "message": "Smoke test connectivity ping"},
        timeout=TIMEOUT_FAST,
    )
    assert r.status_code == 200, f"Unexpected {r.status_code}: {r.text}"
    assert r.json().get("ok") is True
