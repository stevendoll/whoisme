"""Shared step helpers for behave tests."""
import json
import time
import uuid
from unittest.mock import MagicMock


def make_event(method, path, body=None, headers=None):
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {
            "content-type": "application/json",
            **(headers or {}),
        },
        "requestContext": {
            "http": {"method": method, "path": path},
            "accountId": "123456789012",
            "stage": "$default",
        },
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }


def call_handler(event):
    from api.app import handler
    return handler(event, MagicMock())


def seed_interview_session(ddb, phase="interviewing", questions_asked=0, questions_total=20,
                           skipped_sections=None, draft_files=None):
    session_id = str(uuid.uuid4())
    ddb.Table("interview-sessions").put_item(Item={
        "session_id": session_id,
        "phase": phase,
        "questions_asked": questions_asked,
        "questions_total": questions_total,
        "section_density": {},
        "skipped_sections": skipped_sections or [],
        "approved_files": {},
        "approved_files_at": {},
        "draft_files": draft_files or {},
        "history": [
            {"role": "user", "content": "Please begin the interview."},
            {"role": "assistant", "content": "Tell me about yourself."},
        ],
        "created_at": "2026-01-01T00:00:00+00:00",
        "ttl": int(time.time()) + 86400 * 30,
    })
    return session_id
