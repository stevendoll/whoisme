"""
Behave environment hooks — set up moto DynamoDB mock around each scenario.
"""
import importlib
import os
import sys

import boto3
from moto import mock_aws

# Ensure src is on path
_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

os.environ.setdefault("CONTACTS_TABLE",               "contacts")
os.environ.setdefault("ADMIN_TOKENS_TABLE",           "admin-tokens")
os.environ.setdefault("USERS_TABLE",                  "users")
os.environ.setdefault("USER_TOKENS_TABLE",            "user-tokens")
os.environ.setdefault("INTERVIEW_SESSIONS_TABLE",     "interview-sessions")
os.environ.setdefault("AWS_DEFAULT_REGION",           "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID",            "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY",        "test")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME",      "whoisme-api")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "WhoIsMeApi")


def _create_tables(ddb):
    ddb.create_table(
        TableName="contacts",
        KeySchema=[{"AttributeName": "contact_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "contact_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    ddb.create_table(
        TableName="admin-tokens",
        KeySchema=[{"AttributeName": "token_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "token_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    ddb.create_table(
        TableName="users",
        KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "user_id",  "AttributeType": "S"},
            {"AttributeName": "email",    "AttributeType": "S"},
            {"AttributeName": "username", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "email-index",
                "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "username-index",
                "KeySchema": [{"AttributeName": "username", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    ddb.create_table(
        TableName="user-tokens",
        KeySchema=[{"AttributeName": "token_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "token_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    ddb.create_table(
        TableName="interview-sessions",
        KeySchema=[{"AttributeName": "session_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "session_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )


def before_scenario(context, scenario):
    context.mock = mock_aws()
    context.mock.start()
    context.ddb = boto3.resource("dynamodb", region_name="us-east-1")
    _create_tables(context.ddb)
    import db as db_module
    importlib.reload(db_module)
    context.response = None
    context.body = {}
    context.session_id = None
    context.bearer_token = None


def after_scenario(context, scenario):
    context.mock.stop()
