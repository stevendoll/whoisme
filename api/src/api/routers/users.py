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
from drafting import summarize_ideas
from models import DEFAULT_VISIBILITY, SECTIONS, CONTEXT_SECTIONS, User, ContextImportRequest

logger = Logger(service="whoisme-api")
router = Router()

_ses           = boto3.client("sesv2", region_name="us-east-1")
_FROM_EMAIL    = os.environ.get("NOTIFICATION_EMAIL", "")
_SITE_URL      = os.environ.get("SITE_URL", "https://whoisme.io")
_CF_TOKEN      = os.environ.get("CF_API_TOKEN", "")
_CF_KV_NS      = os.environ.get("CF_KV_NAMESPACE_ID", "")
_CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")

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
    auth = (event.headers.get("authorization") or "").strip()
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
        "last_published_at": user.get("last_published_at"),
        "files": approved_files,
        "visibility": user.get("visibility", DEFAULT_VISIBILITY),
        "token_hash": user.get("token_hash"),
    }

    try:
        resp = requests.put(
            _kv_url(username),
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
    if _CF_ACCOUNT_ID:
        return _CF_ACCOUNT_ID
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


def _kv_url(username: str) -> str:
    return (
        f"https://api.cloudflare.com/client/v4/accounts/{_get_cf_account_id()}"
        f"/storage/kv/namespaces/{_CF_KV_NS}/values/{username}"
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/users/profile/<username>")
def get_public_profile(username: str):
    # Check for bearer token in Authorization header
    auth = (router.current_event.headers.get("authorization") or "").strip()
    caller_token = auth[7:] if auth.lower().startswith("bearer ") else None

    # Fast path: read from Cloudflare KV (avoids DynamoDB scan)
    if _CF_TOKEN and _CF_KV_NS:
        try:
            kv_resp = requests.get(
                _kv_url(username),
                headers={"Authorization": f"Bearer {_CF_TOKEN}"},
                timeout=5,
            )
            if kv_resp.status_code == 404:
                raise NotFoundError("Profile not found")
            if kv_resp.status_code == 200:
                profile = kv_resp.json()
                visibility   = profile.get("visibility", DEFAULT_VISIBILITY)
                all_files    = profile.get("files", {})
                stored_hash  = profile.get("token_hash")
                authed = bool(caller_token and stored_hash and _hash_token(caller_token) == stored_hash)
                files = all_files if authed else {
                    k: v for k, v in all_files.items() if visibility.get(k, "public") == "public"
                }
                return {"username": username, "files": files, "visibility": visibility,
                        "updated_at": profile.get("updated_at", ""), "authed": authed}
        except NotFoundError:
            raise
        except Exception as e:
            logger.warning(f"KV read failed, falling back to DynamoDB: {e}")

    # Fallback: DynamoDB scan (used when KV not configured or on KV error)
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

    scan_resp = db.interview_sessions_table.scan(
        FilterExpression="user_id = :u",
        ExpressionAttributeValues={":u": user["user_id"]},
    )
    approved_files: dict = {}
    for session in scan_resp.get("Items", []):
        approved_files.update(session.get("approved_files", {}))

    token_hash = _hash_token(caller_token) if caller_token else None
    authed = bool(token_hash and token_hash == user.get("token_hash"))
    files = approved_files if authed else {
        k: v for k, v in approved_files.items() if visibility.get(k, "public") == "public"
    }

    return {
        "username": username,
        "files": files,
        "visibility": visibility,
        "updated_at": user.get("created_at", ""),
        "authed": authed,
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

    # Gather approved_files_at across all linked sessions (scan until GSI is added)
    approved_files_at: dict = {}
    scan_resp = db.interview_sessions_table.scan(
        FilterExpression="user_id = :u",
        ExpressionAttributeValues={":u": user["user_id"]},
    )
    for session in scan_resp.get("Items", []):
        approved_files_at.update(session.get("approved_files_at", {}))

    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "username": user.get("username"),
        "published": user.get("published", False),
        "visibility": user.get("visibility", DEFAULT_VISIBILITY),
        "has_bearer_token": bool(user.get("token_hash")),
        "last_published_at": user.get("last_published_at"),
        "approved_files_at": approved_files_at,
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

    now = _now_iso()
    db.users_table.update_item(
        Key={"user_id": user["user_id"]},
        UpdateExpression="SET username = :u, published = :p, last_published_at = :t",
        ExpressionAttributeValues={":u": username, ":p": True, ":t": now},
    )
    user["username"] = username
    user["last_published_at"] = now

    _write_profile_to_kv(user, approved_files)

    return {"username": username, "url": f"https://whoisme.io/u/{username}", "last_published_at": now}


@router.post("/users/me/context-publish")
def context_publish():
    """Format answers from a completed context session and publish to KV immediately."""
    user = _get_current_user(router.current_event)

    if not user.get("published") or not user.get("username"):
        raise BadRequestError("Profile must be published before adding quick context")

    body = router.current_event.json_body or {}
    session_id = (body.get("session_id") or "").strip()
    if not session_id:
        raise BadRequestError("session_id is required")

    resp = db.interview_sessions_table.get_item(Key={"session_id": session_id})
    session = resp.get("Item")
    if not session:
        raise NotFoundError("Session not found")

    if session.get("phase") != "complete":
        raise BadRequestError("Session is not complete")

    context_type = session.get("context_type")
    if not context_type or context_type not in CONTEXT_SECTIONS:
        raise BadRequestError("Not a valid context session")

    section_def = CONTEXT_SECTIONS[context_type]
    history = session.get("history", [])

    # Extract user answers (skip the initial "Please begin." turn)
    user_answers = [
        m["content"] for m in history
        if m["role"] == "user" and m["content"] not in ("Please begin.", "Please begin")
    ]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if section_def.format_template:
        ctx = {"date": today}
        for i, answer in enumerate(user_answers):
            ctx[f"q{i}"] = answer
        entry = section_def.format_template.format_map(ctx)
    else:
        # AI formatting (ideas)
        entry = summarize_ideas(history, today)

    # Load or initialize the user's permanent context session
    ctx_session_id = f"ctx-{user['user_id']}"
    ctx_resp = db.interview_sessions_table.get_item(Key={"session_id": ctx_session_id})
    ctx_session = ctx_resp.get("Item") or {
        "session_id": ctx_session_id,
        "user_id": user["user_id"],
        "approved_files": {},
        "approved_files_at": {},
        "history": [],
        "phase": "complete",
        "questions_asked": 0,
        "questions_total": 0,
        "section_density": {},
        "skipped_sections": [],
        "draft_files": {},
        "created_at": _now_iso(),
        "ttl": _ttl_ts(days=3650),  # 10 years — permanent
    }

    existing = ctx_session.get("approved_files", {}).get(context_type, "")
    updated_content = entry + ("\n" + existing if existing else "")

    now = _now_iso()
    ctx_session.setdefault("approved_files", {})[context_type] = updated_content
    ctx_session.setdefault("approved_files_at", {})[context_type] = now

    db.interview_sessions_table.put_item(Item=ctx_session)

    # Gather all approved files across all sessions and publish
    all_approved: dict = {}
    scan_resp = db.interview_sessions_table.scan(
        FilterExpression="user_id = :u",
        ExpressionAttributeValues={":u": user["user_id"]},
    )
    for s in scan_resp.get("Items", []):
        all_approved.update(s.get("approved_files", {}))

    _write_profile_to_kv(user, all_approved)

    return {
        "section": context_type,
        "published_at": now,
        "url": f"https://whoisme.io/u/{user['username']}",
    }


@router.post("/users/me/context-import")
def context_import():
    """Import raw markdown into a context section with a chosen merge strategy."""
    user = _get_current_user(router.current_event)

    if not user.get("published") or not user.get("username"):
        raise BadRequestError("Profile must be published before importing context")

    body = router.current_event.json_body or {}
    req = ContextImportRequest(**body)

    if req.section not in SECTIONS:
        raise BadRequestError(f"Invalid section: {req.section}")

    ctx_session_id = f"ctx-{user['user_id']}"
    ctx_resp = db.interview_sessions_table.get_item(Key={"session_id": ctx_session_id})
    ctx_session = ctx_resp.get("Item") or {
        "session_id": ctx_session_id,
        "user_id": user["user_id"],
        "approved_files": {},
        "approved_files_at": {},
        "history": [],
        "phase": "complete",
        "questions_asked": 0,
        "questions_total": 0,
        "section_density": {},
        "skipped_sections": [],
        "draft_files": {},
        "created_at": _now_iso(),
        "ttl": _ttl_ts(days=3650),
    }

    existing = ctx_session.get("approved_files", {}).get(req.section, "")
    if req.merge == "replace" or not existing:
        updated = req.content
    elif req.merge == "prepend":
        updated = req.content + "\n" + existing
    else:  # append
        updated = existing + "\n" + req.content

    now = _now_iso()
    ctx_session.setdefault("approved_files", {})[req.section] = updated
    ctx_session.setdefault("approved_files_at", {})[req.section] = now
    db.interview_sessions_table.put_item(Item=ctx_session)

    # Scan other sessions, then apply our just-written data on top to avoid
    # eventual consistency issues where the scan returns a stale ctx session.
    all_approved: dict = {}
    scan_resp = db.interview_sessions_table.scan(
        FilterExpression="user_id = :u",
        ExpressionAttributeValues={":u": user["user_id"]},
    )
    for s in scan_resp.get("Items", []):
        if s.get("session_id") != ctx_session_id:
            all_approved.update(s.get("approved_files", {}))
    all_approved.update(ctx_session.get("approved_files", {}))  # always use fresh copy
    _write_profile_to_kv(user, all_approved)

    return {
        "section": req.section,
        "merge": req.merge,
        "published_at": now,
        "url": f"https://whoisme.io/u/{user['username']}",
    }


@router.get("/sections/context")
def get_context_sections():
    """Return context section registry metadata for the frontend."""
    return {
        "sections": [
            {
                "key": s.key,
                "label": s.label,
                "default_visibility": s.default_visibility,
                "ai_driven": len(s.questions) == 0,
            }
            for s in CONTEXT_SECTIONS.values()
        ]
    }


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


@router.post("/users/me/unpublish")
def unpublish():
    """Remove the user's public profile from KV and mark as unpublished."""
    user = _get_current_user(router.current_event)

    username = user.get("username")
    if username and _CF_TOKEN and _CF_KV_NS:
        try:
            resp = requests.delete(
                _kv_url(username),
                headers={"Authorization": f"Bearer {_CF_TOKEN}"},
                timeout=10,
            )
            result = resp.json()
            if not result.get("success"):
                logger.error(f"KV delete failed: {result.get('errors')}")
        except Exception as e:
            logger.error(f"KV delete error: {e}")

    db.users_table.update_item(
        Key={"user_id": user["user_id"]},
        UpdateExpression="SET published = :p REMOVE last_published_at",
        ExpressionAttributeValues={":p": False},
    )
    return {"ok": True}


@router.delete("/users/me")
def delete_account():
    """Permanently delete the user's account and all associated data."""
    user = _get_current_user(router.current_event)
    user_id = user["user_id"]

    # Remove public profile from KV
    username = user.get("username")
    if username and _CF_TOKEN and _CF_KV_NS:
        try:
            resp = requests.delete(
                _kv_url(username),
                headers={"Authorization": f"Bearer {_CF_TOKEN}"},
                timeout=10,
            )
            result = resp.json()
            if not result.get("success"):
                logger.error(f"KV delete failed during account deletion: {result.get('errors')}")
        except Exception as e:
            logger.error(f"KV delete error during account deletion: {e}")

    # Delete all interview sessions for this user
    scan_resp = db.interview_sessions_table.scan(
        FilterExpression="user_id = :u",
        ExpressionAttributeValues={":u": user_id},
    )
    for session in scan_resp.get("Items", []):
        db.interview_sessions_table.delete_item(Key={"session_id": session["session_id"]})

    # Delete user record
    db.users_table.delete_item(Key={"user_id": user_id})

    return {"ok": True}
