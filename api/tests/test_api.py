"""
Unit tests for WhoIsMe API routers.
Uses moto to mock DynamoDB — no real AWS calls.
"""

import json
import os
import sys
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Ensure src/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("ICEBREAKERS_TABLE",    "icebreakers")
os.environ.setdefault("TURNS_TABLE",          "conversation_turns")
os.environ.setdefault("CONVERSATIONS_TABLE",  "conversations")
os.environ.setdefault("CONTACTS_TABLE",       "contacts")
os.environ.setdefault("IDEAS_TABLE",          "conversation_ideas")
os.environ.setdefault("AWS_DEFAULT_REGION",   "us-east-1")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME",        "whoisme-api")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE",   "WhoIsMeApi")


def _apigw_event(method: str, path: str, body: dict | None = None, path_params: dict | None = None) -> dict:
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "test",
            "http": {"method": method, "path": path, "sourceIp": "1.2.3.4", "userAgent": "test"},
            "requestId": "test-request-id",
            "routeKey": f"{method} {path}",
            "stage": "$default",
        },
        "body": json.dumps(body) if body else None,
        "pathParameters": path_params or {},
        "isBase64Encoded": False,
    }


class TestIcebreakers(unittest.TestCase):

    def _seed_icebreaker(self, table, text="The gap between knowing and doing is costing us."):
        item = {
            "icebreaker_id": str(uuid.uuid4()),
            "text": text,
            "is_active": "true",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        table.put_item(Item=item)
        return item

    def test_get_icebreaker_returns_random_active(self):
        import boto3
        from moto import mock_aws

        with mock_aws():
            ddb = boto3.resource("dynamodb", region_name="us-east-1")
            table = ddb.create_table(
                TableName="icebreakers",
                AttributeDefinitions=[
                    {"AttributeName": "icebreaker_id", "AttributeType": "S"},
                    {"AttributeName": "is_active", "AttributeType": "S"},
                ],
                KeySchema=[{"AttributeName": "icebreaker_id", "KeyType": "HASH"}],
                GlobalSecondaryIndexes=[{
                    "IndexName": "is_active-index",
                    "KeySchema": [{"AttributeName": "is_active", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }],
                BillingMode="PAY_PER_REQUEST",
            )

            seeded = self._seed_icebreaker(table)

            with patch("db.icebreakers_table", table):
                import importlib
                import api.routers.icebreakers as mod
                importlib.reload(mod)

                from api.app import handler
                event = _apigw_event("GET", "/conversations/icebreakers")
                result = handler(event, MagicMock())

                self.assertEqual(result["statusCode"], 200)
                body = json.loads(result["body"])
                self.assertIn("text", body)
                self.assertEqual(body["text"], seeded["text"])

    def test_get_icebreaker_404_when_empty(self):
        import boto3
        from moto import mock_aws

        with mock_aws():
            ddb = boto3.resource("dynamodb", region_name="us-east-1")
            table = ddb.create_table(
                TableName="icebreakers",
                AttributeDefinitions=[
                    {"AttributeName": "icebreaker_id", "AttributeType": "S"},
                    {"AttributeName": "is_active", "AttributeType": "S"},
                ],
                KeySchema=[{"AttributeName": "icebreaker_id", "KeyType": "HASH"}],
                GlobalSecondaryIndexes=[{
                    "IndexName": "is_active-index",
                    "KeySchema": [{"AttributeName": "is_active", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }],
                BillingMode="PAY_PER_REQUEST",
            )

            with patch("db.icebreakers_table", table):
                import importlib
                import api.routers.icebreakers as mod
                importlib.reload(mod)

                from api.app import handler
                event = _apigw_event("GET", "/conversations/icebreakers")
                result = handler(event, MagicMock())
                self.assertEqual(result["statusCode"], 404)


class TestTurns(unittest.TestCase):

    def _make_tables(self, ddb):
        turns = ddb.create_table(
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
        conversations = ddb.create_table(
            TableName="conversations",
            AttributeDefinitions=[{"AttributeName": "conversation_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "conversation_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        ideas = ddb.create_table(
            TableName="conversation_ideas",
            AttributeDefinitions=[{"AttributeName": "idea_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "idea_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        return turns, conversations, ideas

    def test_post_visitor_turn_saves_and_calls_bedrock(self):
        import boto3
        from moto import mock_aws

        with mock_aws():
            ddb = boto3.resource("dynamodb", region_name="us-east-1")
            turns_table, conversations_table, ideas_table = self._make_tables(ddb)
            conv_id = str(uuid.uuid4())

            mock_replies = {
                "consultant1": "That's exactly where most companies get stuck. What does your rollout look like?",
                "consultant2": "Imagine calling a diet 'eating less pizza' — same energy. What are you actually changing?",
            }

            with patch("db.turns_table", turns_table), \
                 patch("db.conversations_table", conversations_table), \
                 patch("db.ideas_table", ideas_table), \
                 patch("bedrock_helpers.generate_consultant_replies", return_value=mock_replies):
                import importlib
                import api.routers.turns as turns_mod
                importlib.reload(turns_mod)

                from api.app import handler
                event = _apigw_event(
                    "POST",
                    f"/conversations/{conv_id}/turns",
                    body={"order": 0, "text": "The gap between knowing and doing.", "speaker": "visitor"},
                    path_params={"conversation_id": conv_id},
                )
                result = handler(event, MagicMock())
                self.assertEqual(result["statusCode"], 200)
                body = json.loads(result["body"])
                self.assertEqual(body["turn"]["text"], "The gap between knowing and doing.")
                replies = body.get("consultantReplies", [])
                self.assertEqual(len(replies), 2)
                speakers = {r["speaker"] for r in replies}
                self.assertEqual(speakers, {"consultant1", "consultant2"})

    def test_warmup_event_returns_200(self):
        from api.app import handler
        result = handler({"source": "warmup"}, MagicMock())
        self.assertEqual(result["statusCode"], 200)


if __name__ == "__main__":
    unittest.main()
