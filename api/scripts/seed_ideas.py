"""
Seed conversation_ideas table with initial ideas.
Run against production:  pipenv run python scripts/seed_ideas.py
Run against local:       DYNAMODB_ENDPOINT=http://localhost:8000 pipenv run python scripts/seed_ideas.py
"""

import os
import uuid
import boto3
from datetime import datetime, timezone

ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
REGION   = "us-east-1"

_kwargs  = {"endpoint_url": ENDPOINT} if ENDPOINT else {}
dynamodb = boto3.resource("dynamodb", region_name=REGION, **_kwargs)
table    = dynamodb.Table(os.environ.get("IDEAS_TABLE", "whoisme-conversation-ideas"))

IDEAS = [
    {
        "text":           "This sounds like exactly the kind of challenge where a real conversation with Steven would move things forward faster than any AI.",
        "description":    "CTA — suggest talking to us",
        "is_active":      True,
        "insertion_type": "fixed",
        "fixed_turn":     7,
        "is_once_only":   True,
    },
    {
        "text":           "Why are Americans so much more pessimistic about AI than people in other countries?",
        "description":    "Provocation — American vs global AI attitudes",
        "is_active":      True,
        "insertion_type": "random",
        "is_once_only":   False,
    },
    {
        "text":           "Does AI make us rethink how companies and society fundamentally work?",
        "description":    "Big picture — AI and societal restructuring",
        "is_active":      True,
        "insertion_type": "random",
        "is_once_only":   False,
    },
]

now = datetime.now(timezone.utc).isoformat()

for idea in IDEAS:
    item = {
        "idea_id":    str(uuid.uuid4()),
        "created_at": now,
        **idea,
    }
    table.put_item(Item=item)
    print(f"  ✓ {item['idea_id']}  [{item['insertion_type']}]  {item['description']}")

print(f"\nSeeded {len(IDEAS)} ideas into {table.name}")
