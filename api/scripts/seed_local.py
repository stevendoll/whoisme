"""
Seed local DynamoDB with icebreaker sentences.
Run: DYNAMODB_ENDPOINT=http://localhost:8000 pipenv run python scripts/seed_local.py
"""

import os
import uuid
import boto3
from datetime import datetime, timezone

ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")  # None = use real AWS
REGION = "us-east-1"

_kwargs = {"endpoint_url": ENDPOINT} if ENDPOINT else {}
dynamodb = boto3.resource("dynamodb", region_name=REGION, **_kwargs)

ICEBREAKERS = [
    "The gap between knowing and doing is costing us.",
    "Our competitors moved six months ago. What are we waiting for?",
    "We've talked about AI for two years. What's actually different this time?",
    "The last initiative promised transformation. It delivered a pilot.",
    "Your best people are leaving for companies that let them use better tools.",
    "We're automating the wrong things.",
    "The board is asking about AI. What's your answer?",
    "Every month we wait, the gap gets harder to close.",
    "We hired for what worked in 2020. That company doesn't exist anymore.",
    "The data you need to decide is already inside your organization.",
    "Moving fast without a plan is expensive. So is planning without moving.",
    "Your AI vendor has a roadmap. Do you?",
    "The risk isn't moving too fast. It's explaining why you moved too slow.",
    "Transformation isn't an IT project.",
    "You don't need more proof of concept. You need momentum.",
]


def create_tables():
    existing = [t.name for t in dynamodb.tables.all()]

    if "icebreakers" not in existing:
        dynamodb.create_table(
            TableName="icebreakers",
            AttributeDefinitions=[
                {"AttributeName": "icebreaker_id", "AttributeType": "S"},
                {"AttributeName": "is_active", "AttributeType": "S"},
            ],
            KeySchema=[{"AttributeName": "icebreaker_id", "KeyType": "HASH"}],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "is_active-index",
                    "KeySchema": [{"AttributeName": "is_active", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print("Created table: icebreakers")
    else:
        print("Table already exists: icebreakers")

    if "conversation_turns" not in existing:
        dynamodb.create_table(
            TableName="conversation_turns",
            AttributeDefinitions=[
                {"AttributeName": "conversation_id", "AttributeType": "S"},
                {"AttributeName": "order", "AttributeType": "N"},
            ],
            KeySchema=[
                {"AttributeName": "conversation_id", "KeyType": "HASH"},
                {"AttributeName": "order", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print("Created table: conversation_turns")
    else:
        print("Table already exists: conversation_turns")


def seed_icebreakers():
    table = dynamodb.Table("icebreakers")
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    for text in ICEBREAKERS:
        table.put_item(Item={
            "icebreaker_id": str(uuid.uuid4()),
            "text": text,
            "is_active": "true",
            "created_at": now,
        })
        count += 1
    print(f"Seeded {count} icebreakers")


if __name__ == "__main__":
    create_tables()
    seed_icebreakers()
    print("Done.")
