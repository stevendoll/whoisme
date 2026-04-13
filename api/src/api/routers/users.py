import hashlib
import json
import os
import uuid
from datetime import datetime, timezone, timedelta

import boto3
import requests
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import BadRequestError, NotFoundError, UnauthorizedError

import db
from models import DEFAULT_VISIBILITY, SECTIONS, User

logger = Logger(service="whoisme-api")
router = Router()

_ses        = boto3.client("sesv2", region_name="us-east-1")
_FROM_EMAIL = os.environ.get("NOTIFICATION_EMAIL", "")
_SITE_URL   = os.environ.get("SITE_URL", "https://whoisme.io")
_CF_TOKEN   = os.environ.get("CF_API_TOKEN", "")
_CF_KV_NS   = os.environ.get("CF_KV_NAMESPACE_ID", "")

_SESSION_TTL_H = 24
_USER_TOKEN_TTL_DAYS = 365


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ttl_ts(hours: int = 0, days: int = 0) -> int:
    delta = timedelta(hours=hours, days=days)
    return int((datetime.now(timezone.utc) + delta).timestamp())


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _get_current_user(event) -> dict:
    auth = (event.get_header_value("authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        raise UnauthorizedError("Missing Authorization header")
    token = auth[7:]

    resp = db.user_tokens_table.get_item(Key={"token_id": token})
    item = resp.get("Item")
    if not item:
        raise UnauthorizedError("Invalid or expired token")

    now = int(datetime.now(timezone.utc).timestamp())
    if item.get("ttl", 0) < now:
        raise UnauthorizedError("Token expired")

    user_resp = db.users_table.get_item(Key={"user_id": item["user_id"]})
    user = user_resp.get("Item")
    if not user:
        raise UnauthorizedError("User not found")
    return user


def _send_magic_link(to_email: str, token: str) -> None:
    link = f"{_SITE_URL}/#/verify?token={token}"
    try:
        _ses.send_email(
            FromEmailAddress=_FROM_EMAIL,
            Destination={"ToAddresses": [to_email]},
            Content={
                "Simple": {
                    "Subject": {"Data": "Sign in to WhoIsMe"},
                    "Body": {
                        "Text": {
                            "Data": (
                                f"Click the link below to sign in to WhoIsMe.\n"
                                f"It expires in {_SESSION_TTL_H} hours and can only be used once.\n\n"
                                f"{link}\n"
                            )
                        }
                    },
                }
            },
        )
        logger.info(f"Magic link sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send magic link: {e}")


def _write_profile_to_kv(user: dict, approved_files: dict) -> None:
    if not _CF_TOKEN or not _CF_KV_NS:
        logger.warning("CF KV not configured — skipping KV write")
        return

    username = user.get("username")
    if not username:
        return

    profile = {
        "username": username,
        "updated_at": _now_iso(),
        "files": approved_files,
        "visibility": user.get("visibility", DEFAULT_VISIBILITY),
        "token_hash": user.get("token_hash"),
    }

    url = f"https://api.cloudflare.com/client/v4/accounts/{{account_id}}/storage/kv/namespaces/{_CF_KV_NS}/values/{username}"
    # Account ID is embedded in the KV namespace URL pattern; use workers API
    kv_url = f"https://api.cloudflare.com/client/v4/accounts/PLACEHOLDER/storage/kv/namespaces/{_CF_KV_NS}/values/{username}"

    # The account ID is not stored in env — derive it from the KV namespace ID via the API
    try:
        resp = requests.put(
            f"https://api.cloudflare.com/client/v4/accounts/{_get_cf_account_id()}/storage/kv/namespaces/{_CF_KV_NS}/values/{username}",
            headers={"Authorization": f"Bearer {_CF_TOKEN}", "Content-Type": "application/json"},
            data=json.dumps(profile),
            timeout=10,
        )
        result = resp.json()
        if not result.get("success"):
            logger.error(f"KV write failed: {result.get('errors')}")
        else:
            logger.info(f"KV profile written for {username}")
    except Exception as e:
        logger.error(f"KV write error: {e}")


_cf_account_id_cache: str | None = None

def _get_cf_account_id() -> str:
    global _cf_account_id_cache
    if _cf_account_id_cache:
        return _cf_account_id_cache
    resp = requests.get(
        "https://api.cloudflare.com/client/v4/accounts",
        headers={"Authorization": f"Bearer {_CF_TOKEN}"},
        timeout=10,
    )
    data = resp.json()
    if data.get("success") and data.get("result"):
        _cf_account_id_cache = data["result"][0]["id"]
        return _cf_account_id_cache
    raise RuntimeError("Could not retrieve Cloudflare account ID")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/users/profile/<username>")
def get_public_profile(username: str):
    result = db.users_table.query(
        IndexName="username-index",
        KeyConditionExpression="username = :u",
        ExpressionAttributeValues={":u": username},
    )
    users = result.get("Items", [])
    if not users:
        raise NotFoundError("Profile not found")

    user = users[0]
    if not user.get("published"):
        raise NotFoundError("Profile not found")

    visibility = user.get("visibility", DEFAULT_VISIBILITY)

    # Gather approved files across all sessions
    scan_resp = db.interview_sessions_table.scan(
        FilterExpression="user_id = :u",
        ExpressionAttributeValues={":u": user["user_id"]},
    )
    approved_files: dict = {}
    for session in scan_resp.get("Items", []):
        approved_files.update(session.get("approved_files", {}))

    # Filter to public files only
    public_files = {k: v for k, v in approved_files.items() if visibility.get(k, "public") == "public"}

    return {
        "username": username,
        "files": public_files,
        "visibility": visibility,
        "updated_at": user.get("created_at", ""),
    }


@router.post("/users/start")
def start_auth():
    body = router.current_event.json_body or {}
    email = (body.get("email") or "").strip().lower()
    session_id = body.get("session_id")

    if not email or "@" not in email:
        raise BadRequestError("Valid email required")

    token = str(uuid.uuid4())
    ttl = _ttl_ts(hours=_SESSION_TTL_H)

    db.user_tokens_table.put_item(Item={
        "token_id": token,
        "email": email,
        "session_id": session_id,  # link interview session on verify
        "ttl": ttl,
        "is_magic_link": True,
    })
    _send_magic_link(email, token)
    return {"ok": True}


@router.post("/users/verify")
def verify_auth():
    body = router.current_event.json_body or {}
    token = (body.get("token") or "").strip()
    if not token:
        raise BadRequestError("token is required")

    resp = db.user_tokens_table.get_item(Key={"token_id": token})
    item = resp.get("Item")
    if not item or not item.get("is_magic_link"):
        raise UnauthorizedError("Invalid or expired token")

    now = int(datetime.now(timezone.utc).timestamp())
    if item.get("ttl", 0) < now:
        raise UnauthorizedError("Token expired")

    db.user_tokens_table.delete_item(Key={"token_id": token})

    email = item["email"]

    # Find or create user
    existing = db.users_table.query(
        IndexName="email-index",
        KeyConditionExpression="email = :e",
        ExpressionAttributeValues={":e": email},
    )
    users = existing.get("Items", [])

    if users:
        user = users[0]
    else:
        user = {
            "user_id": str(uuid.uuid4()),
            "email": email,
            "created_at": _now_iso(),
            "published": False,
            "visibility": DEFAULT_VISIBILITY,
        }
        db.users_table.put_item(Item=user)
        logger.info(f"New user created: {user['user_id']}")

    # Issue session token
    session_token = str(uuid.uuid4())
    db.user_tokens_table.put_item(Item={
        "token_id": session_token,
        "user_id": user["user_id"],
        "ttl": _ttl_ts(days=30),
    })

    # Link interview session if provided
    interview_session_id = item.get("session_id")
    if interview_session_id:
        try:
            db.interview_sessions_table.update_item(
                Key={"session_id": interview_session_id},
                UpdateExpression="SET user_id = :u",
                ExpressionAttributeValues={":u": user["user_id"]},
            )
        except Exception as e:
            logger.warning(f"Could not link interview session: {e}")

    return {"token": session_token, "user_id": user["user_id"], "email": email}


@router.get("/users/me")
def get_me():
    user = _get_current_user(router.current_event)

    # Find their interview session (most recent linked)
    approved_files: dict = {}
    sessions = db.interview_sessions_table.query(
        IndexName="user-id-index",
        KeyConditionExpression="user_id = :u",
        ExpressionAttributeValues={":u": user["user_id"]},
    ) if False else {"Items": []}  # GSI not added yet — fetch via scan workaround below

    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "username": user.get("username"),
        "published": user.get("published", False),
        "visibility": user.get("visibility", DEFAULT_VISIBILITY),
        "has_bearer_token": bool(user.get("token_hash")),
    }


@router.patch("/users/me/visibility")
def update_visibility():
    user = _get_current_user(router.current_event)
    body = router.current_event.json_body or {}
    visibility = body.get("visibility") or {}

    valid_values = {"public", "private"}
    for section, value in visibility.items():
        if section not in SECTIONS:
            raise BadRequestError(f"Unknown section: {section}")
        if value not in valid_values:
            raise BadRequestError(f"Visibility must be 'public' or 'private'")

    current = dict(user.get("visibility", DEFAULT_VISIBILITY))
    current.update(visibility)

    db.users_table.update_item(
        Key={"user_id": user["user_id"]},
        UpdateExpression="SET visibility = :v",
        ExpressionAttributeValues={":v": current},
    )
    return {"visibility": current}


@router.post("/users/me/publish")
def publish():
    user = _get_current_user(router.current_event)
    body = router.current_event.json_body or {}
    username = (body.get("username") or "").strip().lower()

    if not username:
        raise BadRequestError("username is required")
    if len(username) < 2 or len(username) > 30:
        raise BadRequestError("username must be 2-30 characters")
    import re
    if not re.match(r"^[a-z0-9_-]+$", username):
        raise BadRequestError("username may only contain lowercase letters, numbers, hyphens, and underscores")

    # Check username not taken
    existing = db.users_table.query(
        IndexName="username-index",
        KeyConditionExpression="username = :u",
        ExpressionAttributeValues={":u": username},
    )
    for item in existing.get("Items", []):
        if item["user_id"] != user["user_id"]:
            raise BadRequestError("Username already taken")

    # Gather approved files from their interview sessions
    # Simple scan for user's sessions (no GSI on user_id yet)
    approved_files: dict = {}
    scan_resp = db.interview_sessions_table.scan(
        FilterExpression="user_id = :u",
        ExpressionAttributeValues={":u": user["user_id"]},
    )
    for session in scan_resp.get("Items", []):
        approved_files.update(session.get("approved_files", {}))

    if not approved_files:
        raise BadRequestError("No approved files to publish")

    db.users_table.update_item(
        Key={"user_id": user["user_id"]},
        UpdateExpression="SET username = :u, published = :p",
        ExpressionAttributeValues={":u": username, ":p": True},
    )
    user["username"] = username

    _write_profile_to_kv(user, approved_files)

    return {"username": username, "url": f"https://whoisme.io/u/{username}"}


@router.post("/users/me/token")
def create_bearer_token():
    """Generate a long-lived bearer token for MCP access."""
    user = _get_current_user(router.current_event)

    token = str(uuid.uuid4())
    token_hash = _hash_token(token)

    db.users_table.update_item(
        Key={"user_id": user["user_id"]},
        UpdateExpression="SET token_hash = :h",
        ExpressionAttributeValues={":h": token_hash},
    )

    # Update KV with new hash if published
    if user.get("published") and user.get("username"):
        user["token_hash"] = token_hash
        scan_resp = db.interview_sessions_table.scan(
            FilterExpression="user_id = :u",
            ExpressionAttributeValues={":u": user["user_id"]},
        )
        approved_files: dict = {}
        for session in scan_resp.get("Items", []):
            approved_files.update(session.get("approved_files", {}))
        if approved_files:
            _write_profile_to_kv(user, approved_files)

    return {"token": token}


@router.delete("/users/me/token")
def revoke_bearer_token():
    user = _get_current_user(router.current_event)
    db.users_table.update_item(
        Key={"user_id": user["user_id"]},
        UpdateExpression="REMOVE token_hash",
    )
    return {"ok": True}


@router.post("/users/me/import")
def import_session():
    """Link an existing interview session to the authenticated user's account."""
    user = _get_current_user(router.current_event)
    body = router.current_event.json_body or {}
    session_id = (body.get("session_id") or "").strip()
    if not session_id:
        raise BadRequestError("session_id is required")

    resp = db.interview_sessions_table.get_item(Key={"session_id": session_id})
    session = resp.get("Item")
    if not session:
        raise NotFoundError("Session not found")

    if session.get("user_id") and session["user_id"] != user["user_id"]:
        raise BadRequestError("Session belongs to another user")

    db.interview_sessions_table.update_item(
        Key={"session_id": session_id},
        UpdateExpression="SET user_id = :u",
        ExpressionAttributeValues={":u": user["user_id"]},
    )
    return {"ok": True}
