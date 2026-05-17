"""
Migrate approved_files from interview sessions → whoisme-documents + whoisme-document-versions.

For each user, merges approved_files across all their interview sessions and creates:
  - One document row per section (whoisme-documents)
  - One published version row per section (whoisme-document-versions)

Skips sections that already have a document. Safe to re-run.

Usage:
  python scripts/migrate_approved_files.py [--dry-run]
"""

import sys
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

DRY_RUN = "--dry-run" in sys.argv

ddb = boto3.resource("dynamodb", region_name="us-east-1")
sessions_table  = ddb.Table("whoisme-interview-sessions")
users_table     = ddb.Table("whoisme-users")
docs_table      = ddb.Table("whoisme-documents")
versions_table  = ddb.Table("whoisme-document-versions")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_all_sessions():
    items = []
    resp = sessions_table.scan()
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = sessions_table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    return items


def get_existing_docs(user_id):
    resp = docs_table.query(
        KeyConditionExpression=Key("user_id").eq(user_id)
    )
    return {doc["title"] for doc in resp.get("Items", [])}


def migrate():
    sessions = get_all_sessions()
    print(f"Found {len(sessions)} sessions total")

    # Group approved_files by user_id
    by_user: dict[str, dict[str, str]] = {}
    for s in sessions:
        user_id = s.get("user_id")
        if not user_id:
            continue
        approved = s.get("approved_files", {})
        if not approved:
            continue
        if user_id not in by_user:
            by_user[user_id] = {}
        by_user[user_id].update(approved)  # last session wins per section

    print(f"Found {len(by_user)} users with approved_files")

    total_created = 0
    total_skipped = 0

    for user_id, files in by_user.items():
        existing = get_existing_docs(user_id)
        for title, content in files.items():
            if not content or not content.strip():
                continue
            if title in existing:
                print(f"  SKIP {user_id[:8]} / {title} (document already exists)")
                total_skipped += 1
                continue

            document_id = str(uuid.uuid4())
            version_id  = str(uuid.uuid4())
            ts = now_iso()

            print(f"  {'DRY ' if DRY_RUN else ''}CREATE {user_id[:8]} / {title} ({len(content)} chars)")

            if not DRY_RUN:
                docs_table.put_item(Item={
                    "user_id":     user_id,
                    "document_id": document_id,
                    "title":       title,
                    "visibility":  "public",
                    "created_at":  ts,
                })
                versions_table.put_item(Item={
                    "document_id": document_id,
                    "version_id":  version_id,
                    "content":     content,
                    "created_at":  ts,
                    "is_published": True,
                    "published_at": ts,
                })

            total_created += 1

    print(f"\nDone. Created: {total_created}, Skipped: {total_skipped}")
    if DRY_RUN:
        print("(dry run — no writes made)")


if __name__ == "__main__":
    migrate()
