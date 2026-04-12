"""
Unit tests for WhoIsMe API.
Uses moto to mock DynamoDB — no real AWS calls.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("CONTACTS_TABLE",                 "contacts")
os.environ.setdefault("AWS_DEFAULT_REGION",             "us-east-1")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME",        "whoisme-api")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE",   "WhoIsMeApi")


class TestWarmup(unittest.TestCase):

    def test_warmup_event_returns_200(self):
        from api.app import handler
        result = handler({"source": "warmup"}, MagicMock())
        self.assertEqual(result["statusCode"], 200)


if __name__ == "__main__":
    unittest.main()
