"""
Post-deploy smoke tests for WhoIsMe API.
Usage: SMOKE_BASE_URL=https://api.whoisme.io pipenv run python scripts/smoke_test.py
"""

import os
import sys
import requests

BASE_URL = os.environ.get("SMOKE_BASE_URL", "https://api.whoisme.io").rstrip("/")


def test_create_interview() -> str:
    url = f"{BASE_URL}/interview"
    print(f"POST {url} ...", end=" ")
    r = requests.post(url, timeout=30)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "session_id" in body or "sessionId" in body, f"Missing session_id: {body}"
    assert "message" in body, f"Missing message: {body}"
    session_id = body.get("session_id") or body.get("sessionId")
    elapsed = r.elapsed.total_seconds()
    print(f"OK ({elapsed:.2f}s) — session {session_id[:8]}...")
    return session_id


def test_respond(session_id: str):
    url = f"{BASE_URL}/interview/{session_id}/respond"
    print(f"POST {url} ...", end=" ")
    r = requests.post(url, json={"text": "I work as a software engineer building developer tools."}, timeout=30)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "message" in body, f"Missing message: {body}"
    elapsed = r.elapsed.total_seconds()
    print(f"OK ({elapsed:.2f}s)")


def test_get_session(session_id: str):
    url = f"{BASE_URL}/interview/{session_id}"
    print(f"GET {url} ...", end=" ")
    r = requests.get(url, timeout=10)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "phase" in body or "session_id" in body or "sessionId" in body, f"Unexpected body: {body}"
    elapsed = r.elapsed.total_seconds()
    print(f"OK ({elapsed:.2f}s)")


def main():
    print(f"\nSmoke tests → {BASE_URL}\n{'─' * 60}")
    errors = []

    session_id = None
    try:
        session_id = test_create_interview()
    except Exception as e:
        errors.append(f"POST /interview: {e}")

    if session_id:
        try:
            test_respond(session_id)
        except Exception as e:
            errors.append(f"POST /interview/{{id}}/respond: {e}")

        try:
            test_get_session(session_id)
        except Exception as e:
            errors.append(f"GET /interview/{{id}}: {e}")

    print(f"\n{'─' * 60}")
    if errors:
        print(f"FAILED ({len(errors)} error(s)):")
        for err in errors:
            print(f"  ✗ {err}")
        sys.exit(1)
    else:
        print("All smoke tests passed.")


if __name__ == "__main__":
    main()
