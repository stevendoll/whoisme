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

TABLES = [
    {
        "TableName": "whoisme-interview-sessions",
        "AttributeDefinitions": [
            {"AttributeName": "session_id", "AttributeType": "S"},
        ],
        "KeySchema": [
            {"AttributeName": "session_id", "KeyType": "HASH"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "whoisme-users",
        "AttributeDefinitions": [
            {"AttributeName": "user_id", "AttributeType": "S"},
        ],
        "KeySchema": [
            {"AttributeName": "user_id", "KeyType": "HASH"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "whoisme-user-tokens",
        "AttributeDefinitions": [
            {"AttributeName": "token", "AttributeType": "S"},
        ],
        "KeySchema": [
            {"AttributeName": "token", "KeyType": "HASH"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "whoisme-admin-tokens",
        "AttributeDefinitions": [
            {"AttributeName": "token", "AttributeType": "S"},
        ],
        "KeySchema": [
            {"AttributeName": "token", "KeyType": "HASH"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "whoisme-contacts",
        "AttributeDefinitions": [
            {"AttributeName": "contact_id", "AttributeType": "S"},
        ],
        "KeySchema": [
            {"AttributeName": "contact_id", "KeyType": "HASH"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
]


def create_tables():
    existing = [t.name for t in dynamodb.tables.all()]
    for spec in TABLES:
        name = spec["TableName"]
        if name not in existing:
            dynamodb.create_table(**spec)
            print(f"Created table: {name}")
        else:
            print(f"Table already exists: {name}")


if __name__ == "__main__":
    create_tables()
    print("Done.")
