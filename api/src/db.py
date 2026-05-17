import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

_endpoint = os.environ.get("DYNAMODB_ENDPOINT")
_kwargs = {"endpoint_url": _endpoint} if _endpoint else {}

_dynamodb = boto3.resource("dynamodb", region_name="us-east-1", **_kwargs)

contacts_table           = _dynamodb.Table(os.environ.get("CONTACTS_TABLE",           "whoisme-contacts"))
admin_tokens_table       = _dynamodb.Table(os.environ.get("ADMIN_TOKENS_TABLE",       "whoisme-admin-tokens"))
users_table              = _dynamodb.Table(os.environ.get("USERS_TABLE",              "whoisme-users"))
user_tokens_table        = _dynamodb.Table(os.environ.get("USER_TOKENS_TABLE",        "whoisme-user-tokens"))
interview_sessions_table = _dynamodb.Table(os.environ.get("INTERVIEW_SESSIONS_TABLE", "whoisme-interview-sessions"))
documents_table          = _dynamodb.Table(os.environ.get("DOCUMENTS_TABLE",          "whoisme-documents"))
document_versions_table  = _dynamodb.Table(os.environ.get("DOCUMENT_VERSIONS_TABLE",  "whoisme-document-versions"))


def upsert_published_document(user_id: str, title: str, content: str) -> None:
    """Create or update a published document for a user.

    If a document with this title already exists for the user, adds a new
    published version. Otherwise creates the document and first published version.
    """
    ts = datetime.now(timezone.utc).isoformat()

    # Check for existing document
    resp = documents_table.query(
        KeyConditionExpression=Key("user_id").eq(user_id),
        FilterExpression="title = :t",
        ExpressionAttributeValues={":t": title},
    )
    items = resp.get("Items", [])

    if items:
        document_id = items[0]["document_id"]
    else:
        document_id = str(uuid.uuid4())
        documents_table.put_item(Item={
            "user_id":     user_id,
            "document_id": document_id,
            "title":       title,
            "visibility":  "public",
            "created_at":  ts,
        })

    version_id = str(uuid.uuid4())
    document_versions_table.put_item(Item={
        "document_id":  document_id,
        "version_id":   version_id,
        "content":      content,
        "created_at":   ts,
        "is_published": True,
        "published_at": ts,
    })
