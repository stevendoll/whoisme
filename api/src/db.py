import os
import boto3

_endpoint = os.environ.get("DYNAMODB_ENDPOINT")
_kwargs = {"endpoint_url": _endpoint} if _endpoint else {}

_dynamodb = boto3.resource("dynamodb", region_name="us-east-1", **_kwargs)

contacts_table           = _dynamodb.Table(os.environ.get("CONTACTS_TABLE",           "whoisme-contacts"))
admin_tokens_table       = _dynamodb.Table(os.environ.get("ADMIN_TOKENS_TABLE",       "whoisme-admin-tokens"))
users_table              = _dynamodb.Table(os.environ.get("USERS_TABLE",              "whoisme-users"))
user_tokens_table        = _dynamodb.Table(os.environ.get("USER_TOKENS_TABLE",        "whoisme-user-tokens"))
interview_sessions_table = _dynamodb.Table(os.environ.get("INTERVIEW_SESSIONS_TABLE", "whoisme-interview-sessions"))
