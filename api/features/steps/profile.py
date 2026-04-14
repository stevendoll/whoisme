"""Step definitions for public_profile.feature."""
import hashlib
import json
import uuid

from behave import given, when, then
from common import make_event, call_handler

_PUBLIC_FILES  = {"identity": "I am a developer.", "role-and-responsibilities": "I build tools."}
_PRIVATE_FILES = {"communication-style": "I prefer async.", "goals-and-priorities": "Ship fast."}
_ALL_FILES     = {**_PUBLIC_FILES, **_PRIVATE_FILES}
_VISIBILITY    = {
    "identity": "public",
    "role-and-responsibilities": "public",
    "communication-style": "private",
    "goals-and-priorities": "private",
}


def _seed_user(ddb, username, published=True, token_hash=None):
    user_id = str(uuid.uuid4())
    user = {
        "user_id": user_id,
        "email": f"{username}@example.com",
        "username": username,
        "published": published,
        "visibility": _VISIBILITY,
    }
    if token_hash:
        user["token_hash"] = token_hash
    ddb.Table("users").put_item(Item=user)

    session_id = str(uuid.uuid4())
    ddb.Table("interview-sessions").put_item(Item={
        "session_id": session_id,
        "user_id": user_id,
        "phase": "reviewing",
        "approved_files": _ALL_FILES,
        "approved_files_at": {},
    })
    return user_id


@given('a published user "{username}" exists with public and private files')
def step_published_user(context, username):
    _seed_user(context.ddb, username)
    context.username = username


@given('"{username}" has a bearer token "{token}"')
def step_set_bearer_token(context, username, token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    # Update user record with token_hash
    result = context.ddb.Table("users").scan(
        FilterExpression="username = :u",
        ExpressionAttributeValues={":u": username},
    )
    user = result["Items"][0]
    context.ddb.Table("users").update_item(
        Key={"user_id": user["user_id"]},
        UpdateExpression="SET token_hash = :h",
        ExpressionAttributeValues={":h": token_hash},
    )
    context.bearer_token = token


@given('an unpublished user "{username}" exists')
def step_unpublished_user(context, username):
    _seed_user(context.ddb, username, published=False)


@when('I GET the profile for "{username}" without authentication')
def step_get_profile_anon(context, username):
    result = call_handler(make_event("GET", f"/users/profile/{username}"))
    context.response = result
    context.body = json.loads(result["body"])


@when('I GET the profile for "{username}" with bearer token "{token}"')
def step_get_profile_with_token(context, username, token):
    result = call_handler(make_event(
        "GET", f"/users/profile/{username}",
        headers={"authorization": f"Bearer {token}"},
    ))
    context.response = result
    context.body = json.loads(result["body"])


@then("only public files are returned")
def step_only_public(context):
    files = context.body.get("files", {})
    for key in _PRIVATE_FILES:
        assert key not in files, f"Private file {key} unexpectedly returned"
    for key in _PUBLIC_FILES:
        assert key in files, f"Public file {key} missing"


@then("all files are returned")
def step_all_files(context):
    files = context.body.get("files", {})
    for key in _ALL_FILES:
        assert key in files, f"File {key} missing from response"


@then("authed is true")
def step_authed_true(context):
    assert context.body.get("authed") is True, f"authed={context.body.get('authed')}"


@then("authed is false")
def step_authed_false(context):
    assert context.body.get("authed") is False, f"authed={context.body.get('authed')}"
