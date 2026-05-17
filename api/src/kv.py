"""Shared Cloudflare KV helpers."""
import json
import os

import requests
from aws_lambda_powertools import Logger

import db
from models import DEFAULT_VISIBILITY

logger = Logger(service="whoisme-api")

_CF_TOKEN      = os.environ.get("CF_API_TOKEN", "")
_CF_KV_NS      = os.environ.get("CF_KV_NAMESPACE_ID", "")
_CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")

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


def kv_url(username: str) -> str:
    return (
        f"https://api.cloudflare.com/client/v4/accounts/{_get_cf_account_id()}"
        f"/storage/kv/namespaces/{_CF_KV_NS}/values/{username}"
    )


def gather_approved_files(user_id: str) -> dict:
    """Merge approved_files across all interview sessions for a user."""
    approved: dict = {}
    scan_resp = db.interview_sessions_table.scan(
        FilterExpression="user_id = :u",
        ExpressionAttributeValues={":u": user_id},
    )
    for session in scan_resp.get("Items", []):
        approved.update(session.get("approved_files", {}))
    return approved


def gather_document_files(user_id: str) -> dict:
    """Collect the latest published version content from whoisme-documents."""
    from boto3.dynamodb.conditions import Key
    files: dict = {}
    # Scan user's documents
    scan_resp = db.documents_table.query(
        KeyConditionExpression=Key("user_id").eq(user_id),
    )
    for doc in scan_resp.get("Items", []):
        document_id = doc["document_id"]
        title = doc["title"]
        # Get latest published version
        versions_resp = db.document_versions_table.query(
            IndexName="document-created-index",
            KeyConditionExpression=Key("document_id").eq(document_id),
            ScanIndexForward=False,
            Limit=20,
        )
        for v in versions_resp.get("Items", []):
            if v.get("is_published"):
                files[title] = v["content"]
                break
    return files


def write_profile_to_kv(user: dict, approved_files: dict) -> None:
    """Write merged profile (interview sessions + documents) to Cloudflare KV."""
    if not _CF_TOKEN or not _CF_KV_NS:
        logger.warning("CF KV not configured — skipping KV write")
        return

    username = user.get("username")
    if not username:
        return

    # Document files take precedence over interview session files
    doc_files = gather_document_files(user["user_id"])
    merged = {**approved_files, **doc_files}

    profile = {
        "username": username,
        "updated_at": _now_iso(),
        "last_published_at": user.get("last_published_at"),
        "files": merged,
        "visibility": user.get("visibility", DEFAULT_VISIBILITY),
        "token_hash": user.get("token_hash"),
    }

    try:
        resp = requests.put(
            kv_url(username),
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


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
