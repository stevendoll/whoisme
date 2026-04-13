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


if __name__ == "__main__":
    unittest.main()
