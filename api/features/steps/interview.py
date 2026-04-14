"""Step definitions for interview_session.feature."""
import json
from unittest.mock import patch, MagicMock

from behave import given, when, then
from common import make_event, call_handler, seed_interview_session

_MOCK_QUESTION = {"message": "Tell me about yourself.", "heckle": None, "sections_touched": []}
_MOCK_DRAFT    = {"draft": "This is a generated draft."}


@given("the DynamoDB tables exist")
def step_tables_exist(context):
    # Tables are created in environment.py before_scenario
    pass


@given("Bedrock is mocked to return questions")
def step_mock_bedrock_questions(context):
    context.bedrock_patcher = patch(
        "api.routers.interview.call_bedrock",
        return_value=_MOCK_QUESTION,
    )
    context.bedrock_mock = context.bedrock_patcher.start()


@given("Bedrock is mocked to return drafts")
def step_mock_bedrock_drafts(context):
    if hasattr(context, "bedrock_patcher"):
        context.bedrock_patcher.stop()
    context.bedrock_patcher = patch(
        "api.routers.interview.call_bedrock",
        return_value=_MOCK_DRAFT,
    )
    context.bedrock_mock = context.bedrock_patcher.start()


@given("an active interview session exists")
def step_active_session(context):
    context.session_id = seed_interview_session(context.ddb)


@given('a session with "{section}" in skipped_sections')
def step_session_with_skipped(context, section):
    context.session_id = seed_interview_session(context.ddb, skipped_sections=[section])


@given("a session in reviewing phase with 20 of 20 questions asked")
def step_reviewing_session(context):
    context.session_id = seed_interview_session(
        context.ddb, phase="reviewing", questions_asked=20, questions_total=20
    )
    context.bedrock_patcher = patch(
        "api.routers.interview.call_bedrock",
        return_value=_MOCK_QUESTION,
    )
    context.bedrock_mock = context.bedrock_patcher.start()


@when("I create a new interview session")
def step_create_session(context):
    result = call_handler(make_event("POST", "/interview"))
    context.response = result
    context.body = json.loads(result["body"])
    if "session_id" in context.body:
        context.session_id = context.body["session_id"]


@when('I respond with "{text}"')
def step_respond(context, text):
    result = call_handler(make_event(
        "POST", f"/interview/{context.session_id}/respond", body={"text": text}
    ))
    context.response = result
    context.body = json.loads(result["body"])
    context.answered_text = text


@when('I skip section "{section}"')
def step_skip_section(context, section):
    result = call_handler(make_event(
        "POST", f"/interview/{context.session_id}/skip-section", body={"section": section}
    ))
    context.response = result
    context.body = json.loads(result["body"])


@when('I reactivate section "{section}"')
def step_reactivate_section(context, section):
    result = call_handler(make_event(
        "POST", f"/interview/{context.session_id}/reactivate-section", body={"section": section}
    ))
    context.response = result
    context.body = json.loads(result["body"])


@when("I pause the interview")
def step_pause(context):
    result = call_handler(make_event("POST", f"/interview/{context.session_id}/pause"))
    context.response = result
    context.body = json.loads(result["body"])


@when("I request 5 more questions")
def step_more_questions(context):
    result = call_handler(make_event(
        "POST", f"/interview/{context.session_id}/more", body={"count": 5}
    ))
    context.response = result
    context.body = json.loads(result["body"])


@when("I skip a question")
def step_skip_question(context):
    result = call_handler(make_event("POST", f"/interview/{context.session_id}/skip-question"))
    context.response = result
    context.body = json.loads(result["body"])


@then("the response status is {status:d}")
def step_status(context, status):
    assert context.response["statusCode"] == status, \
        f"Expected {status}, got {context.response['statusCode']}: {context.response['body']}"


@then("the response contains a session_id")
def step_has_session_id(context):
    assert "session_id" in context.body, f"No session_id in {context.body}"


@then("the response contains a message")
def step_has_message(context):
    assert "message" in context.body, f"No message in {context.body}"


@then('the session is saved in DynamoDB with phase "{phase}"')
def step_session_phase(context, phase):
    sid = context.body.get("session_id") or context.session_id
    item = context.ddb.Table("interview-sessions").get_item(Key={"session_id": sid})["Item"]
    assert item["phase"] == phase, f"Expected phase {phase}, got {item['phase']}"


@then("questions_remaining is {count:d}")
def step_questions_remaining(context, count):
    assert context.body["questions_remaining"] == count, \
        f"Expected {count}, got {context.body['questions_remaining']}"


@then("the session history contains my answer")
def step_history_has_answer(context):
    item = context.ddb.Table("interview-sessions").get_item(
        Key={"session_id": context.session_id}
    )["Item"]
    contents = [h["content"] for h in item["history"]]
    assert context.answered_text in contents, f"Answer not in history: {contents}"


@then('"{section}" is in skipped_sections')
def step_in_skipped(context, section):
    assert section in context.body.get("skipped_sections", []), \
        f"{section} not in {context.body.get('skipped_sections')}"


@then('"{section}" is not in skipped_sections')
def step_not_in_skipped(context, section):
    assert section not in context.body.get("skipped_sections", []), \
        f"{section} unexpectedly in {context.body.get('skipped_sections')}"


@then('the phase is "{phase}"')
def step_phase_is(context, phase):
    assert context.body.get("phase") == phase, \
        f"Expected phase {phase}, got {context.body.get('phase')}"


@then("draft_files are generated")
def step_draft_files_generated(context):
    assert len(context.body.get("draft_files", {})) > 0, \
        "No draft_files in response"


def after_scenario(context, scenario):
    if hasattr(context, "bedrock_patcher"):
        context.bedrock_patcher.stop()
