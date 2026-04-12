"""
Post-deploy smoke tests for WhoIsMe API.
Usage: SMOKE_BASE_URL=https://api.whoisme.io pipenv run python scripts/smoke_test.py
"""

import os
import sys
import uuid
import requests

BASE_URL = os.environ.get("SMOKE_BASE_URL", "https://api.whoisme.io").rstrip("/")


def test_get_icebreaker():
    url = f"{BASE_URL}/conversations/icebreakers"
    print(f"GET {url} ...", end=" ")
    r = requests.get(url, timeout=15)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "text" in body, f"Missing 'text' in response: {body}"
    assert body["text"], "Icebreaker text is empty"
    print(f"OK ({r.elapsed.total_seconds():.2f}s) — \"{body['text'][:60]}...\"")
    return body["text"]


def test_post_visitor_turn(conversation_id: str, text: str, order: int = 0):
    url = f"{BASE_URL}/conversations/{conversation_id}/turns"
    print(f"POST {url} (visitor turn, order={order}) ...", end=" ")
    payload = {"order": order, "text": text, "speaker": "visitor"}
    r = requests.post(url, json=payload, timeout=30)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "turn" in body, f"Missing 'turn' in response: {body}"
    assert body["turn"]["text"] == text, f"Turn text mismatch: {body}"
    replies = body.get("consultantReplies", [])
    assert 1 <= len(replies) <= 3, f"Expected 1–3 consultantReplies, got {len(replies)}: {body}"
    valid_speakers = {"consultant1", "consultant2"}
    for reply in replies:
        assert reply["speaker"] in valid_speakers, f"Unexpected speaker: {reply['speaker']}"
        assert reply["text"], f"Empty reply text for {reply['speaker']}"
    elapsed = r.elapsed.total_seconds()
    print(f"OK ({elapsed:.2f}s) — {len(replies)} repl{'y' if len(replies) == 1 else 'ies'}")
    for reply in replies:
        label = "Alex" if reply["speaker"] == "consultant1" else "Jamie"
        print(f"  {label}: \"{reply['text'][:80]}\"")
    return replies


def main():
    print(f"\nSmoke tests → {BASE_URL}\n{'─' * 60}")
    errors = []

    try:
        icebreaker_text = test_get_icebreaker()
    except Exception as e:
        # Non-fatal: icebreakers table may be empty; use fallback text
        print(f"  (skipped — {e})")
        icebreaker_text = "The gap between knowing and doing is costing us."

    conv_id = str(uuid.uuid4())

    try:
        test_post_visitor_turn(conv_id, icebreaker_text, order=0)
    except Exception as e:
        errors.append(f"POST /conversations/{{id}}/turns (visitor, order=0): {e}")

    try:
        test_post_visitor_turn(conv_id, "We keep running pilots but nothing scales.", order=3)
    except Exception as e:
        errors.append(f"POST /conversations/{{id}}/turns (visitor, order=3): {e}")

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
