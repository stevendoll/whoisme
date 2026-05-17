import uuid
from datetime import datetime, timezone

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import BadRequestError, NotFoundError, ServiceError

import db
import kv
from models import SECTIONS
from api.routers.users import _get_current_user

logger = Logger(service="whoisme-api")
router = Router()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_document(document_id: str, user_id: str) -> dict:
    resp = db.documents_table.get_item(Key={"user_id": user_id, "document_id": document_id})
    doc = resp.get("Item")
    if not doc:
        raise NotFoundError("Document not found")
    return doc


def _latest_version(document_id: str) -> dict | None:
    from boto3.dynamodb.conditions import Key as K
    resp = db.document_versions_table.query(
        IndexName="document-created-index",
        KeyConditionExpression=K("document_id").eq(document_id),
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def _latest_published_version(document_id: str) -> dict | None:
    from boto3.dynamodb.conditions import Key as K
    resp = db.document_versions_table.query(
        IndexName="document-created-index",
        KeyConditionExpression=K("document_id").eq(document_id),
        ScanIndexForward=False,
        Limit=20,
    )
    for v in resp.get("Items", []):
        if v.get("is_published"):
            return v
    return None


def _build_document_response(doc: dict, latest_published: dict | None, has_draft: bool) -> dict:
    return {
        "document_id": doc["document_id"],
        "title": doc["title"],
        "created_at": doc["created_at"],
        "visibility": doc.get("visibility", "public"),
        "version_id": latest_published["version_id"] if latest_published else None,
        "content": latest_published["content"] if latest_published else None,
        "published_at": latest_published.get("published_at") if latest_published else None,
        "has_draft": has_draft,
    }


@router.get("/documents")
def list_documents():
    user = _get_current_user(router.current_event)
    from boto3.dynamodb.conditions import Key as K

    resp = db.documents_table.query(
        KeyConditionExpression=K("user_id").eq(user["user_id"]),
    )
    docs = resp.get("Items", [])
    result = []
    for doc in docs:
        doc_id = doc["document_id"]
        latest = _latest_version(doc_id)
        has_draft = bool(latest and not latest.get("is_published"))
        if latest and latest.get("is_published"):
            latest_published = latest
        elif has_draft:
            latest_published = _latest_published_version(doc_id)
        else:
            latest_published = None
        result.append(_build_document_response(doc, latest_published, has_draft))
    return {"documents": result}


@router.post("/documents")
def create_document():
    user = _get_current_user(router.current_event)
    body = router.current_event.json_body or {}
    title = (body.get("title") or "").strip()
    content = (body.get("content") or "").strip()

    if not title:
        raise BadRequestError("title is required")
    if title not in SECTIONS:
        raise BadRequestError(f"Invalid section: {title}")
    if not content:
        raise BadRequestError("content is required")

    from boto3.dynamodb.conditions import Key as K
    existing = db.documents_table.query(
        KeyConditionExpression=K("user_id").eq(user["user_id"]),
    )
    for doc in existing.get("Items", []):
        if doc["title"] == title:
            raise ServiceError(409, f"Document with title '{title}' already exists")

    now = _now_iso()
    document_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    visibility = user.get("visibility", {}).get(title, "public")

    db.documents_table.put_item(Item={
        "user_id": user["user_id"],
        "document_id": document_id,
        "title": title,
        "visibility": visibility,
        "created_at": now,
    })
    db.document_versions_table.put_item(Item={
        "document_id": document_id,
        "version_id": version_id,
        "content": content,
        "created_at": now,
        "is_published": False,
        "published_at": None,
    })

    doc = {
        "user_id": user["user_id"],
        "document_id": document_id,
        "title": title,
        "visibility": visibility,
        "created_at": now,
    }
    return _build_document_response(doc, None, True)


@router.post("/documents/<document_id>/versions")
def create_version(document_id: str):
    user = _get_current_user(router.current_event)
    _get_document(document_id, user["user_id"])  # verify ownership

    body = router.current_event.json_body or {}
    content = (body.get("content") or "").strip()
    if not content:
        raise BadRequestError("content is required")

    latest = _latest_version(document_id)
    if latest and not latest.get("is_published"):
        raise ServiceError(409, "Latest version is not yet published — publish it before saving a new draft")

    now = _now_iso()
    version_id = str(uuid.uuid4())
    db.document_versions_table.put_item(Item={
        "document_id": document_id,
        "version_id": version_id,
        "content": content,
        "created_at": now,
        "is_published": False,
        "published_at": None,
    })
    return {"version_id": version_id, "created_at": now}


@router.get("/documents/<document_id>/versions")
def get_versions(document_id: str):
    user = _get_current_user(router.current_event)
    _get_document(document_id, user["user_id"])  # verify ownership

    from boto3.dynamodb.conditions import Key as K
    resp = db.document_versions_table.query(
        IndexName="document-created-index",
        KeyConditionExpression=K("document_id").eq(document_id),
        ScanIndexForward=False,
        Limit=50,
    )
    versions = [
        {
            "version_id": v["version_id"],
            "created_at": v["created_at"],
            "is_published": v.get("is_published", False),
            "published_at": v.get("published_at"),
            "content": v["content"],
        }
        for v in resp.get("Items", [])
    ]
    return {"versions": versions}


@router.post("/documents/<document_id>/versions/<version_id>/publish")
def publish_version(document_id: str, version_id: str):
    user = _get_current_user(router.current_event)
    doc = _get_document(document_id, user["user_id"])

    resp = db.document_versions_table.get_item(
        Key={"document_id": document_id, "version_id": version_id}
    )
    version = resp.get("Item")
    if not version:
        raise NotFoundError("Version not found")
    if version.get("is_published"):
        raise ServiceError(409, "Version is already published")

    now = _now_iso()
    db.document_versions_table.update_item(
        Key={"document_id": document_id, "version_id": version_id},
        UpdateExpression="SET is_published = :t, published_at = :n",
        ExpressionAttributeValues={":t": True, ":n": now},
    )
    version["is_published"] = True
    version["published_at"] = now

    approved_files = kv.gather_approved_files(user["user_id"])
    kv.write_profile_to_kv(user, approved_files)

    return _build_document_response(doc, version, False)
