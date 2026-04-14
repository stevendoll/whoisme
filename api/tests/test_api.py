"""
Unit tests for WhoIsMe API.
Uses moto to mock DynamoDB — no real AWS calls.
"""

import hashlib
import json
import os
import sys
import time
import unittest
import uuid
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("CONTACTS_TABLE",                 "contacts")
os.environ.setdefault("ADMIN_TOKENS_TABLE",             "admin-tokens")
os.environ.setdefault("USERS_TABLE",                    "users")
os.environ.setdefault("USER_TOKENS_TABLE",              "user-tokens")
os.environ.setdefault("INTERVIEW_SESSIONS_TABLE",       "interview-sessions")
os.environ.setdefault("AWS_DEFAULT_REGION",             "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID",              "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY",          "test")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME",        "whoisme-api")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE",   "WhoIsMeApi")

import boto3
from moto import mock_aws


def _make_event(method, path, body=None, headers=None):
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


def _create_tables(ddb):
    ddb.create_table(
        TableName="contacts",
        KeySchema=[{"AttributeName": "contact_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "contact_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    ddb.create_table(
        TableName="admin-tokens",
        KeySchema=[{"AttributeName": "token_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "token_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    ddb.create_table(
        TableName="users",
        KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "email",   "AttributeType": "S"},
            {"AttributeName": "username","AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "email-index",
                "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "username-index",
                "KeySchema": [{"AttributeName": "username", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    ddb.create_table(
        TableName="user-tokens",
        KeySchema=[{"AttributeName": "token_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "token_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    ddb.create_table(
        TableName="interview-sessions",
        KeySchema=[{"AttributeName": "session_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "session_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seed_published_user(ddb, username="testuser", bearer_token=None):
    """Insert a published user + interview session with approved files."""
    user_id = str(uuid.uuid4())
    token_hash = hashlib.sha256(bearer_token.encode()).hexdigest() if bearer_token else None
    user = {
        "user_id": user_id,
        "email": f"{username}@example.com",
        "username": username,
        "published": True,
        "visibility": {
            "identity": "public",
            "role-and-responsibilities": "public",
            "communication-style": "private",
            "goals-and-priorities": "private",
        },
    }
    if token_hash:
        user["token_hash"] = token_hash
    ddb.Table("users").put_item(Item=user)

    session_id = str(uuid.uuid4())
    ddb.Table("interview-sessions").put_item(Item={
        "session_id": session_id,
        "user_id": user_id,
        "phase": "reviewing",
        "approved_files": {
            "identity": "I am a software engineer.",
            "role-and-responsibilities": "I build developer tools.",
            "communication-style": "I prefer async communication.",
            "goals-and-priorities": "Ship fast and learn.",
        },
    })
    return user_id, session_id


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestWarmup(unittest.TestCase):

    def test_warmup_event_returns_200(self):
        from api.app import handler
        result = handler({"source": "warmup"}, MagicMock())
        self.assertEqual(result["statusCode"], 200)


@mock_aws
class TestPublicProfile(unittest.TestCase):
    """GET /users/profile/:username — public card / public JSON for MCP."""

    def setUp(self):
        import importlib
        import db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        # Reload db module so tables point to moto tables
        importlib.reload(db_module)

    def _call(self, username, bearer_token=None):
        from api.app import handler
        headers = {}
        if bearer_token:
            headers["authorization"] = f"Bearer {bearer_token}"
        event = _make_event("GET", f"/users/profile/{username}", headers=headers)
        result = handler(event, MagicMock())
        body = json.loads(result["body"])
        return result["statusCode"], body

    def test_returns_public_files_only(self):
        _seed_published_user(self.ddb)
        status, body = self._call("testuser")
        self.assertEqual(status, 200)
        self.assertIn("identity", body["files"])
        self.assertIn("role-and-responsibilities", body["files"])
        self.assertNotIn("communication-style", body["files"])
        self.assertNotIn("goals-and-priorities", body["files"])

    def test_returns_all_files_with_valid_bearer_token(self):
        """Private MCP: bearer token unlocks private files."""
        token = "my-secret-bearer-token"
        _seed_published_user(self.ddb, bearer_token=token)
        status, body = self._call("testuser", bearer_token=token)
        self.assertEqual(status, 200)
        self.assertTrue(body.get("authed"))
        self.assertIn("identity", body["files"])
        self.assertIn("communication-style", body["files"])
        self.assertIn("goals-and-priorities", body["files"])

    def test_wrong_bearer_token_returns_public_only(self):
        _seed_published_user(self.ddb, bearer_token="correct-token")
        status, body = self._call("testuser", bearer_token="wrong-token")
        self.assertEqual(status, 200)
        self.assertFalse(body.get("authed"))
        self.assertNotIn("communication-style", body["files"])

    def test_unknown_username_returns_404(self):
        status, body = self._call("nobody")
        self.assertEqual(status, 404)

    def test_unpublished_user_returns_404(self):
        user_id = str(uuid.uuid4())
        self.ddb.Table("users").put_item(Item={
            "user_id": user_id,
            "email": "draft@example.com",
            "username": "draftuser",
            "published": False,
            "visibility": {},
        })
        status, _ = self._call("draftuser")
        self.assertEqual(status, 404)

    def test_response_includes_visibility_map(self):
        _seed_published_user(self.ddb)
        status, body = self._call("testuser")
        self.assertEqual(status, 200)
        self.assertIn("visibility", body)
        self.assertEqual(body["visibility"]["identity"], "public")
        self.assertEqual(body["visibility"]["communication-style"], "private")


@mock_aws
class TestUserVerify(unittest.TestCase):
    """POST /users/verify — magic link auth."""

    def setUp(self):
        import importlib
        import db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        importlib.reload(db_module)

    def _call(self, token):
        from api.app import handler
        event = _make_event("POST", "/users/verify", body={"token": token})
        result = handler(event, MagicMock())
        body = json.loads(result["body"])
        return result["statusCode"], body

    def _seed_magic_token(self, token=None, email="user@example.com", expired=False):
        token = token or str(uuid.uuid4())
        ttl = int(time.time()) + (3600 if not expired else -1)
        self.ddb.Table("user-tokens").put_item(Item={
            "token_id": token,
            "email": email,
            "is_magic_link": True,
            "ttl": ttl,
        })
        return token

    def test_valid_token_creates_user_and_returns_session(self):
        token = self._seed_magic_token()
        status, body = self._call(token)
        self.assertEqual(status, 200)
        self.assertIn("token", body)
        self.assertIn("email", body)

    def test_verify_does_not_store_null_username(self):
        """Regression: null username in put_item crashed username-index GSI."""
        token = self._seed_magic_token(email="newuser@example.com")
        status, body = self._call(token)
        self.assertEqual(status, 200)
        # Confirm the user record has no 'username' key (not null, absent)
        users = self.ddb.Table("users").scan()["Items"]
        new_user = next(u for u in users if u["email"] == "newuser@example.com")
        self.assertNotIn("username", new_user)

    def test_invalid_token_returns_401(self):
        status, body = self._call("not-a-real-token")
        self.assertEqual(status, 401)

    def test_expired_token_returns_401(self):
        token = self._seed_magic_token(expired=True)
        status, body = self._call(token)
        self.assertEqual(status, 401)

    def test_token_consumed_after_use(self):
        """Token should be deleted so it can't be reused."""
        token = self._seed_magic_token()
        self._call(token)
        status, _ = self._call(token)
        self.assertEqual(status, 401)

    def test_existing_user_is_found_not_duplicated(self):
        email = "existing@example.com"
        user_id = str(uuid.uuid4())
        self.ddb.Table("users").put_item(Item={
            "user_id": user_id,
            "email": email,
            "published": False,
            "visibility": {},
        })
        token = self._seed_magic_token(email=email)
        status, body = self._call(token)
        self.assertEqual(status, 200)
        users = self.ddb.Table("users").scan(
            FilterExpression="email = :e",
            ExpressionAttributeValues={":e": email},
        )["Items"]
        self.assertEqual(len(users), 1, "Should not create duplicate user")


@mock_aws
class TestBearerToken(unittest.TestCase):
    """POST/DELETE /users/me/token — long-lived MCP bearer token."""

    def setUp(self):
        import importlib
        import db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        importlib.reload(db_module)

    def _make_session_token(self, user_id):
        token = str(uuid.uuid4())
        self.ddb.Table("user-tokens").put_item(Item={
            "token_id": token,
            "user_id": user_id,
            "ttl": int(time.time()) + 86400,
        })
        return token

    def _seed_user(self):
        user_id = str(uuid.uuid4())
        self.ddb.Table("users").put_item(Item={
            "user_id": user_id,
            "email": "me@example.com",
            "published": False,
            "visibility": {},
        })
        session_token = self._make_session_token(user_id)
        return user_id, session_token

    def _call(self, method, path, session_token, body=None):
        from api.app import handler
        event = _make_event(method, path, body=body, headers={
            "authorization": f"Bearer {session_token}",
        })
        result = handler(event, MagicMock())
        return result["statusCode"], json.loads(result["body"])

    def test_create_bearer_token(self):
        _, session_token = self._seed_user()
        status, body = self._call("POST", "/users/me/token", session_token)
        self.assertEqual(status, 200)
        self.assertIn("token", body)
        self.assertIsInstance(body["token"], str)

    def test_bearer_token_hash_stored_on_user(self):
        user_id, session_token = self._seed_user()
        _, body = self._call("POST", "/users/me/token", session_token)
        bearer = body["token"]
        expected_hash = hashlib.sha256(bearer.encode()).hexdigest()
        user = self.ddb.Table("users").get_item(Key={"user_id": user_id})["Item"]
        self.assertEqual(user["token_hash"], expected_hash)

    def test_revoke_bearer_token(self):
        user_id, session_token = self._seed_user()
        self._call("POST", "/users/me/token", session_token)
        status, body = self._call("DELETE", "/users/me/token", session_token)
        self.assertEqual(status, 200)
        user = self.ddb.Table("users").get_item(Key={"user_id": user_id})["Item"]
        self.assertNotIn("token_hash", user)

    def test_no_auth_returns_401(self):
        from api.app import handler
        event = _make_event("POST", "/users/me/token")
        result = handler(event, MagicMock())
        self.assertEqual(result["statusCode"], 401)


@mock_aws
class TestPublicProfileKvPath(unittest.TestCase):
    """GET /users/profile/:username — KV fast path."""

    def setUp(self):
        import importlib
        import db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        importlib.reload(db_module)

    def _call(self, username, bearer_token=None):
        from api.app import handler
        headers = {}
        if bearer_token:
            headers["authorization"] = f"Bearer {bearer_token}"
        event = _make_event("GET", f"/users/profile/{username}", headers=headers)
        result = handler(event, MagicMock())
        return result["statusCode"], json.loads(result["body"])

    def test_kv_path_returns_public_files(self):
        """When KV returns data, use it instead of DynamoDB."""
        kv_profile = {
            "username": "kvuser",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "files": {
                "identity": "I am a developer.",
                "communication-style": "I like async.",
            },
            "visibility": {
                "identity": "public",
                "communication-style": "private",
            },
            "token_hash": None,
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = kv_profile

        with patch("api.routers.users.requests.get", return_value=mock_resp), \
             patch("api.routers.users._CF_TOKEN", "fake-token"), \
             patch("api.routers.users._CF_KV_NS", "fake-ns"), \
             patch("api.routers.users._get_cf_account_id", return_value="fake-acct"):
            status, body = self._call("kvuser")

        self.assertEqual(status, 200)
        self.assertIn("identity", body["files"])
        self.assertNotIn("communication-style", body["files"])
        self.assertFalse(body.get("authed"))

    def test_kv_path_bearer_token_unlocks_private_files(self):
        token = "my-bearer"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        kv_profile = {
            "username": "kvuser",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "files": {
                "identity": "I am a developer.",
                "communication-style": "I like async.",
            },
            "visibility": {"identity": "public", "communication-style": "private"},
            "token_hash": token_hash,
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = kv_profile

        with patch("api.routers.users.requests.get", return_value=mock_resp), \
             patch("api.routers.users._CF_TOKEN", "fake-token"), \
             patch("api.routers.users._CF_KV_NS", "fake-ns"), \
             patch("api.routers.users._get_cf_account_id", return_value="fake-acct"):
            status, body = self._call("kvuser", bearer_token=token)

        self.assertEqual(status, 200)
        self.assertTrue(body.get("authed"))
        self.assertIn("communication-style", body["files"])

    def test_kv_404_returns_not_found(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("api.routers.users.requests.get", return_value=mock_resp), \
             patch("api.routers.users._CF_TOKEN", "fake-token"), \
             patch("api.routers.users._CF_KV_NS", "fake-ns"), \
             patch("api.routers.users._get_cf_account_id", return_value="fake-acct"):
            status, _ = self._call("nobody")

        self.assertEqual(status, 404)

    def test_kv_error_falls_back_to_dynamodb(self):
        """On KV exception, fall back to DynamoDB scan."""
        _seed_published_user(self.ddb, username="fallbackuser")

        with patch("api.routers.users.requests.get", side_effect=Exception("timeout")), \
             patch("api.routers.users._CF_TOKEN", "fake-token"), \
             patch("api.routers.users._CF_KV_NS", "fake-ns"), \
             patch("api.routers.users._get_cf_account_id", return_value="fake-acct"):
            status, body = self._call("fallbackuser")

        self.assertEqual(status, 200)
        self.assertIn("identity", body["files"])


@mock_aws
class TestPublishTimestamps(unittest.TestCase):
    """Publish stores last_published_at; approve stores approved_files_at."""

    def setUp(self):
        import importlib
        import db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        importlib.reload(db_module)

    def _make_session_token(self, user_id):
        token = str(uuid.uuid4())
        self.ddb.Table("user-tokens").put_item(Item={
            "token_id": token,
            "user_id": user_id,
            "ttl": int(time.time()) + 86400,
        })
        return token

    def _seed_user_with_session(self):
        user_id = str(uuid.uuid4())
        self.ddb.Table("users").put_item(Item={
            "user_id": user_id,
            "email": "pub@example.com",
            "published": False,
            "visibility": {s: "public" for s in ["identity", "role-and-responsibilities"]},
        })
        session_id = str(uuid.uuid4())
        self.ddb.Table("interview-sessions").put_item(Item={
            "session_id": session_id,
            "user_id": user_id,
            "phase": "reviewing",
            "approved_files": {"identity": "I am a tester.", "role-and-responsibilities": "I test things."},
            "approved_files_at": {"identity": "2026-01-10T00:00:00+00:00", "role-and-responsibilities": "2026-01-11T00:00:00+00:00"},
        })
        session_token = self._make_session_token(user_id)
        return user_id, session_token

    def _call(self, method, path, session_token, body=None):
        from api.app import handler
        event = _make_event(method, path, body=body, headers={
            "authorization": f"Bearer {session_token}",
        })
        result = handler(event, MagicMock())
        return result["statusCode"], json.loads(result["body"])

    def test_publish_stores_last_published_at(self):
        user_id, session_token = self._seed_user_with_session()
        with patch("api.routers.users._write_profile_to_kv"):
            status, body = self._call("POST", "/users/me/publish", session_token, {"username": "timestampuser"})
        self.assertEqual(status, 200)
        self.assertIn("last_published_at", body)
        self.assertIsNotNone(body["last_published_at"])
        # Also stored on DynamoDB user record
        user = self.ddb.Table("users").get_item(Key={"user_id": user_id})["Item"]
        self.assertIn("last_published_at", user)

    def test_get_me_returns_approved_files_at_and_last_published_at(self):
        user_id, session_token = self._seed_user_with_session()
        # Simulate already-published
        now = "2026-01-12T00:00:00+00:00"
        self.ddb.Table("users").update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET last_published_at = :t, username = :u, published = :p",
            ExpressionAttributeValues={":t": now, ":u": "pubuser", ":p": True},
        )
        status, body = self._call("GET", "/users/me", session_token)
        self.assertEqual(status, 200)
        self.assertEqual(body["last_published_at"], now)
        self.assertIn("approved_files_at", body)
        self.assertEqual(body["approved_files_at"]["identity"], "2026-01-10T00:00:00+00:00")

    def test_approve_stores_approved_files_at(self):
        """POST /interview/:id/review/approve should record approved_files_at timestamp."""
        from api.app import handler

        # Create a session in reviewing phase with a draft
        session_id = str(uuid.uuid4())
        self.ddb.Table("interview-sessions").put_item(Item={
            "session_id": session_id,
            "phase": "reviewing",
            "draft_files": {"identity": "Draft identity text."},
            "approved_files": {},
        })
        event = _make_event("POST", f"/interview/{session_id}/review/approve", body={"file": "identity"})
        result = handler(event, MagicMock())
        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertIn("approved_files_at", body)
        self.assertIn("identity", body["approved_files_at"])
        # Verify persisted in DynamoDB
        session = self.ddb.Table("interview-sessions").get_item(Key={"session_id": session_id})["Item"]
        self.assertIn("approved_files_at", session)
        self.assertIn("identity", session["approved_files_at"])

    def test_changed_since_publish_detection(self):
        """approved_files_at newer than last_published_at indicates unpublished changes."""
        user_id, session_token = self._seed_user_with_session()
        # last_published_at is before the approved_files_at timestamps in the session
        self.ddb.Table("users").update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET last_published_at = :t, username = :u, published = :p",
            ExpressionAttributeValues={":t": "2026-01-09T00:00:00+00:00", ":u": "changeduser", ":p": True},
        )
        status, body = self._call("GET", "/users/me", session_token)
        self.assertEqual(status, 200)
        # Both files were approved after the last publish
        self.assertGreater(body["approved_files_at"]["identity"], body["last_published_at"])
        self.assertGreater(body["approved_files_at"]["role-and-responsibilities"], body["last_published_at"])


_MOCK_QUESTION = {"message": "Tell me about yourself.", "heckle": None, "sections_touched": []}
_MOCK_DRAFT    = {"draft": "This is a generated draft."}


def _seed_interview_session(ddb, phase="interviewing", questions_asked=0, questions_total=20,
                            skipped_sections=None, draft_files=None, approved_files=None, history=None):
    """Seed an interview session in moto DynamoDB. Returns session_id."""
    session_id = str(uuid.uuid4())
    ddb.Table("interview-sessions").put_item(Item={
        "session_id": session_id,
        "phase": phase,
        "questions_asked": questions_asked,
        "questions_total": questions_total,
        "section_density": {},
        "skipped_sections": skipped_sections or [],
        "approved_files": approved_files or {},
        "approved_files_at": {},
        "draft_files": draft_files or {},
        "history": history or [
            {"role": "user", "content": "Please begin the interview."},
            {"role": "assistant", "content": "Tell me about yourself."},
        ],
        "created_at": "2026-01-01T00:00:00+00:00",
        "ttl": int(time.time()) + 86400 * 30,
    })
    return session_id


@mock_aws
class TestGetSession(unittest.TestCase):
    """GET /interview/<session_id>"""

    def setUp(self):
        import importlib, db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        importlib.reload(db_module)

    def _call(self, session_id):
        from api.app import handler
        result = handler(_make_event("GET", f"/interview/{session_id}"), MagicMock())
        return result["statusCode"], json.loads(result["body"])

    def test_returns_correct_fields(self):
        sid = _seed_interview_session(self.ddb, questions_asked=5,
                                      draft_files={"identity": "draft"},
                                      approved_files={"role-and-responsibilities": "approved"})
        status, body = self._call(sid)
        self.assertEqual(status, 200)
        self.assertEqual(body["session_id"], sid)
        self.assertEqual(body["phase"], "interviewing")
        self.assertEqual(body["questions_asked"], 5)
        self.assertEqual(body["questions_remaining"], 15)
        self.assertIn("identity", body["draft_files"])
        self.assertIn("role-and-responsibilities", body["approved_files"])

    def test_questions_remaining_arithmetic(self):
        sid = _seed_interview_session(self.ddb, questions_asked=15, questions_total=20)
        _, body = self._call(sid)
        self.assertEqual(body["questions_remaining"], 5)

    def test_missing_session_returns_404(self):
        status, _ = self._call(str(uuid.uuid4()))
        self.assertEqual(status, 404)

    def test_reviewing_phase_fields(self):
        sid = _seed_interview_session(self.ddb, phase="reviewing",
                                      approved_files={"identity": "approved content"})
        _, body = self._call(sid)
        self.assertEqual(body["phase"], "reviewing")
        self.assertIn("identity", body["approved_files"])


@mock_aws
class TestCreateSession(unittest.TestCase):
    """POST /interview"""

    def setUp(self):
        import importlib, db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        importlib.reload(db_module)

    def _call(self):
        from api.app import handler
        result = handler(_make_event("POST", "/interview"), MagicMock())
        return result["statusCode"], json.loads(result["body"])

    @patch("api.routers.interview.call_bedrock", return_value=_MOCK_QUESTION)
    def test_returns_session_id_and_message(self, _mock):
        status, body = self._call()
        self.assertEqual(status, 200)
        self.assertIn("session_id", body)
        self.assertIn("message", body)
        self.assertEqual(body["questions_remaining"], 20)

    @patch("api.routers.interview.call_bedrock", return_value=_MOCK_QUESTION)
    def test_persists_session_to_dynamodb(self, _mock):
        _, body = self._call()
        session_id = body["session_id"]
        item = self.ddb.Table("interview-sessions").get_item(Key={"session_id": session_id})["Item"]
        self.assertEqual(item["phase"], "interviewing")
        self.assertEqual(item["questions_asked"], 0)
        self.assertEqual(len(item["history"]), 2)

    @patch("api.routers.interview.call_bedrock", return_value=_MOCK_QUESTION)
    def test_sets_ttl(self, _mock):
        _, body = self._call()
        item = self.ddb.Table("interview-sessions").get_item(Key={"session_id": body["session_id"]})["Item"]
        self.assertGreater(item["ttl"], int(time.time()))

    @patch("api.routers.interview.call_bedrock", return_value=_MOCK_QUESTION)
    def test_bedrock_called_with_begin_message(self, mock_bedrock):
        self._call()
        args = mock_bedrock.call_args
        messages = args[0][1]
        self.assertEqual(messages[0]["content"], "Please begin the interview.")


@mock_aws
class TestRespond(unittest.TestCase):
    """POST /interview/<session_id>/respond"""

    def setUp(self):
        import importlib, db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        importlib.reload(db_module)

    def _call(self, session_id, text="I am a software engineer."):
        from api.app import handler
        result = handler(_make_event("POST", f"/interview/{session_id}/respond", body={"text": text}), MagicMock())
        return result["statusCode"], json.loads(result["body"])

    @patch("api.routers.interview.call_bedrock", return_value={**_MOCK_QUESTION, "sections_touched": ["identity"]})
    def test_happy_path(self, _mock):
        sid = _seed_interview_session(self.ddb)
        status, body = self._call(sid)
        self.assertEqual(status, 200)
        self.assertIn("message", body)
        self.assertEqual(body["questions_remaining"], 19)
        self.assertEqual(body["phase"], "interviewing")

    @patch("api.routers.interview.call_bedrock", return_value={**_MOCK_QUESTION, "sections_touched": ["identity"]})
    def test_updates_section_density(self, _mock):
        sid = _seed_interview_session(self.ddb)
        self._call(sid)
        item = self.ddb.Table("interview-sessions").get_item(Key={"session_id": sid})["Item"]
        self.assertEqual(item["section_density"]["identity"], 1)

    def test_empty_text_returns_400(self):
        sid = _seed_interview_session(self.ddb)
        status, _ = self._call(sid, text="")
        self.assertEqual(status, 400)

    def test_wrong_phase_returns_400(self):
        sid = _seed_interview_session(self.ddb, phase="reviewing")
        status, _ = self._call(sid)
        self.assertEqual(status, 400)

    @patch("api.routers.interview.call_bedrock")
    def test_phase_transition_at_last_question(self, mock_bedrock):
        # First call = next question, subsequent calls = draft generation (one per section)
        mock_bedrock.side_effect = [_MOCK_QUESTION] + [_MOCK_DRAFT] * len(__import__("models").SECTIONS)
        sid = _seed_interview_session(self.ddb, questions_asked=19, questions_total=20)
        status, body = self._call(sid)
        self.assertEqual(status, 200)
        self.assertEqual(body["phase"], "reviewing")
        item = self.ddb.Table("interview-sessions").get_item(Key={"session_id": sid})["Item"]
        self.assertEqual(item["phase"], "reviewing")
        self.assertTrue(len(item.get("draft_files", {})) > 0)


@mock_aws
class TestSkipQuestion(unittest.TestCase):
    """POST /interview/<session_id>/skip-question"""

    def setUp(self):
        import importlib, db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        importlib.reload(db_module)

    def _call(self, session_id):
        from api.app import handler
        result = handler(_make_event("POST", f"/interview/{session_id}/skip-question"), MagicMock())
        return result["statusCode"], json.loads(result["body"])

    @patch("api.routers.interview.call_bedrock", return_value={"message": "Different question.", "heckle": None})
    def test_adds_skip_marker_to_history(self, _mock):
        sid = _seed_interview_session(self.ddb)
        self._call(sid)
        item = self.ddb.Table("interview-sessions").get_item(Key={"session_id": sid})["Item"]
        contents = [h["content"] for h in item["history"]]
        self.assertTrue(any("[SKIP:" in c for c in contents))

    @patch("api.routers.interview.call_bedrock", return_value={"message": "Different question.", "heckle": None})
    def test_returns_new_question(self, _mock):
        sid = _seed_interview_session(self.ddb)
        status, body = self._call(sid)
        self.assertEqual(status, 200)
        self.assertEqual(body["message"], "Different question.")

    def test_wrong_phase_returns_400(self):
        sid = _seed_interview_session(self.ddb, phase="reviewing")
        status, _ = self._call(sid)
        self.assertEqual(status, 400)


@mock_aws
class TestSkipSection(unittest.TestCase):
    """POST /interview/<session_id>/skip-section"""

    def setUp(self):
        import importlib, db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        importlib.reload(db_module)

    def _call(self, session_id, section):
        from api.app import handler
        result = handler(_make_event("POST", f"/interview/{session_id}/skip-section", body={"section": section}), MagicMock())
        return result["statusCode"], json.loads(result["body"])

    @patch("api.routers.interview.call_bedrock", return_value=_MOCK_QUESTION)
    def test_valid_section_added_to_skipped(self, _mock):
        sid = _seed_interview_session(self.ddb)
        status, body = self._call(sid, "identity")
        self.assertEqual(status, 200)
        self.assertIn("identity", body["skipped_sections"])

    @patch("api.routers.interview.call_bedrock", return_value=_MOCK_QUESTION)
    def test_skipping_already_skipped_is_idempotent(self, _mock):
        sid = _seed_interview_session(self.ddb, skipped_sections=["identity"])
        self._call(sid, "identity")
        item = self.ddb.Table("interview-sessions").get_item(Key={"session_id": sid})["Item"]
        self.assertEqual(item["skipped_sections"].count("identity"), 1)

    def test_invalid_section_returns_400(self):
        sid = _seed_interview_session(self.ddb)
        status, _ = self._call(sid, "not-a-section")
        self.assertEqual(status, 400)


@mock_aws
class TestReactivateSection(unittest.TestCase):
    """POST /interview/<session_id>/reactivate-section — no Bedrock needed"""

    def setUp(self):
        import importlib, db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        importlib.reload(db_module)

    def _call(self, session_id, section):
        from api.app import handler
        result = handler(_make_event("POST", f"/interview/{session_id}/reactivate-section", body={"section": section}), MagicMock())
        return result["statusCode"], json.loads(result["body"])

    def test_removes_section_from_skipped(self):
        sid = _seed_interview_session(self.ddb, skipped_sections=["identity", "goals-and-priorities"])
        status, body = self._call(sid, "identity")
        self.assertEqual(status, 200)
        self.assertNotIn("identity", body["skipped_sections"])
        self.assertIn("goals-and-priorities", body["skipped_sections"])

    def test_reactivating_non_skipped_is_noop(self):
        sid = _seed_interview_session(self.ddb, skipped_sections=["identity"])
        status, body = self._call(sid, "goals-and-priorities")
        self.assertEqual(status, 200)
        self.assertEqual(body["skipped_sections"], ["identity"])

    def test_invalid_section_returns_400(self):
        sid = _seed_interview_session(self.ddb)
        status, _ = self._call(sid, "not-real")
        self.assertEqual(status, 400)


@mock_aws
class TestPauseSession(unittest.TestCase):
    """POST /interview/<session_id>/pause"""

    def setUp(self):
        import importlib, db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        importlib.reload(db_module)

    def _call(self, session_id):
        from api.app import handler
        result = handler(_make_event("POST", f"/interview/{session_id}/pause"), MagicMock())
        return result["statusCode"], json.loads(result["body"])

    @patch("api.routers.interview.call_bedrock", return_value=_MOCK_DRAFT)
    def test_transitions_to_reviewing(self, _mock):
        sid = _seed_interview_session(self.ddb)
        status, body = self._call(sid)
        self.assertEqual(status, 200)
        self.assertEqual(body["phase"], "reviewing")

    @patch("api.routers.interview.call_bedrock", return_value=_MOCK_DRAFT)
    def test_draft_files_populated(self, _mock):
        sid = _seed_interview_session(self.ddb)
        self._call(sid)
        item = self.ddb.Table("interview-sessions").get_item(Key={"session_id": sid})["Item"]
        self.assertEqual(item["phase"], "reviewing")
        self.assertGreater(len(item.get("draft_files", {})), 0)

    def test_already_reviewing_returns_400(self):
        sid = _seed_interview_session(self.ddb, phase="reviewing")
        status, _ = self._call(sid)
        self.assertEqual(status, 400)


@mock_aws
class TestMoreQuestions(unittest.TestCase):
    """POST /interview/<session_id>/more"""

    def setUp(self):
        import importlib, db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        importlib.reload(db_module)

    def _call(self, session_id, count=5):
        from api.app import handler
        result = handler(_make_event("POST", f"/interview/{session_id}/more", body={"count": count}), MagicMock())
        return result["statusCode"], json.loads(result["body"])

    @patch("api.routers.interview.call_bedrock", return_value=_MOCK_QUESTION)
    def test_increases_total_and_returns_to_interviewing(self, _mock):
        sid = _seed_interview_session(self.ddb, phase="reviewing", questions_asked=20, questions_total=20)
        status, body = self._call(sid, count=5)
        self.assertEqual(status, 200)
        self.assertEqual(body["phase"], "interviewing")
        self.assertEqual(body["questions_remaining"], 5)

    @patch("api.routers.interview.call_bedrock", return_value=_MOCK_QUESTION)
    def test_clears_draft_files(self, _mock):
        sid = _seed_interview_session(self.ddb, phase="reviewing",
                                      draft_files={"identity": "old draft"})
        self._call(sid, count=5)
        item = self.ddb.Table("interview-sessions").get_item(Key={"session_id": sid})["Item"]
        self.assertEqual(item["draft_files"], {})

    def test_count_too_large_returns_400(self):
        sid = _seed_interview_session(self.ddb, phase="reviewing")
        status, _ = self._call(sid, count=51)
        self.assertEqual(status, 400)

    def test_count_too_small_returns_400(self):
        sid = _seed_interview_session(self.ddb, phase="reviewing")
        status, _ = self._call(sid, count=0)
        self.assertEqual(status, 400)

    def test_wrong_phase_returns_400(self):
        sid = _seed_interview_session(self.ddb, phase="interviewing")
        status, _ = self._call(sid, count=5)
        self.assertEqual(status, 400)


@mock_aws
class TestReviewFeedback(unittest.TestCase):
    """POST /interview/<session_id>/review/feedback"""

    def setUp(self):
        import importlib, db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        importlib.reload(db_module)

    def _call(self, session_id, file="identity", text="Make it shorter."):
        from api.app import handler
        result = handler(_make_event("POST", f"/interview/{session_id}/review/feedback",
                                     body={"file": file, "text": text}), MagicMock())
        return result["statusCode"], json.loads(result["body"])

    @patch("api.routers.interview.call_bedrock", return_value={"draft": "Revised draft content."})
    def test_updates_draft(self, _mock):
        sid = _seed_interview_session(self.ddb, phase="reviewing",
                                      draft_files={"identity": "Original draft."})
        status, body = self._call(sid)
        self.assertEqual(status, 200)
        self.assertEqual(body["draft"], "Revised draft content.")
        item = self.ddb.Table("interview-sessions").get_item(Key={"session_id": sid})["Item"]
        self.assertEqual(item["draft_files"]["identity"], "Revised draft content.")

    def test_empty_feedback_returns_400(self):
        sid = _seed_interview_session(self.ddb, phase="reviewing",
                                      draft_files={"identity": "Draft."})
        status, _ = self._call(sid, text="")
        self.assertEqual(status, 400)

    def test_invalid_file_returns_400(self):
        sid = _seed_interview_session(self.ddb, phase="reviewing")
        status, _ = self._call(sid, file="not-real")
        self.assertEqual(status, 400)

    def test_wrong_phase_returns_400(self):
        sid = _seed_interview_session(self.ddb, phase="interviewing")
        status, _ = self._call(sid)
        self.assertEqual(status, 400)


@mock_aws
class TestAdminAuth(unittest.TestCase):
    """POST /admin/login and /admin/verify"""

    def setUp(self):
        import importlib, db as db_module
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        importlib.reload(db_module)

    def _login(self, email):
        from api.app import handler
        result = handler(_make_event("POST", "/admin/login", body={"email": email}), MagicMock())
        return result["statusCode"], json.loads(result["body"])

    def _verify(self, token):
        from api.app import handler
        result = handler(_make_event("POST", "/admin/verify", body={"token": token}), MagicMock())
        return result["statusCode"], json.loads(result["body"])

    def _seed_token(self, email="admin@example.com", expired=False):
        token = str(uuid.uuid4())
        ttl = int(time.time()) + (3600 if not expired else -1)
        self.ddb.Table("admin-tokens").put_item(Item={"token_id": token, "email": email, "ttl": ttl})
        return token

    @patch("api.routers.auth._ses")
    @patch.dict(os.environ, {"ADMIN_EMAILS": "admin@example.com"})
    def test_known_email_returns_ok_and_stores_token(self, _mock_ses):
        import importlib
        import api.routers.auth as auth_module
        importlib.reload(auth_module)
        status, body = self._login("admin@example.com")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        items = self.ddb.Table("admin-tokens").scan()["Items"]
        self.assertTrue(any(i["email"] == "admin@example.com" for i in items))

    def test_unknown_email_still_returns_ok(self):
        status, body = self._login("unknown@example.com")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

    def test_verify_valid_token_returns_email(self):
        token = self._seed_token()
        status, body = self._verify(token)
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["email"], "admin@example.com")

    def test_verify_consumes_token(self):
        token = self._seed_token()
        self._verify(token)
        _, body = self._verify(token)
        self.assertFalse(body["ok"])

    def test_verify_expired_token_returns_false(self):
        token = self._seed_token(expired=True)
        _, body = self._verify(token)
        self.assertFalse(body["ok"])

    def test_verify_nonexistent_token_returns_false(self):
        _, body = self._verify(str(uuid.uuid4()))
        self.assertFalse(body["ok"])


if __name__ == "__main__":
    unittest.main()
