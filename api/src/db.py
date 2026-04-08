import os
import boto3

_endpoint = os.environ.get("DYNAMODB_ENDPOINT")
_kwargs = {"endpoint_url": _endpoint} if _endpoint else {}

_dynamodb = boto3.resource("dynamodb", region_name="us-east-1", **_kwargs)

icebreakers_table   = _dynamodb.Table(os.environ.get("ICEBREAKERS_TABLE",   "icebreakers"))
turns_table         = _dynamodb.Table(os.environ.get("TURNS_TABLE",         "conversation_turns"))
conversations_table = _dynamodb.Table(os.environ.get("CONVERSATIONS_TABLE", "t12n-conversations"))
contacts_table      = _dynamodb.Table(os.environ.get("CONTACTS_TABLE",      "t12n-contacts"))
ideas_table         = _dynamodb.Table(os.environ.get("IDEAS_TABLE",         "t12n-conversation-ideas"))
admin_tokens_table  = _dynamodb.Table(os.environ.get("ADMIN_TOKENS_TABLE",  "t12n-admin-tokens"))
