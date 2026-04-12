"""
Create local DynamoDB tables for development.
Run: DYNAMODB_ENDPOINT=http://localhost:8000 pipenv run python scripts/seed_local.py
"""

import os
import boto3

ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
REGION = "us-east-1"

_kwargs = {"endpoint_url": ENDPOINT} if ENDPOINT else {}
dynamodb = boto3.resource("dynamodb", region_name=REGION, **_kwargs)


def create_tables():
    existing = [t.name for t in dynamodb.tables.all()]

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


if __name__ == "__main__":
    create_tables()
    print("Done.")
