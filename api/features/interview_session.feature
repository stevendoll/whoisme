Feature: Interview session lifecycle
  As a user building a WhoIsMe profile
  I want to be interviewed by an AI
  So that my profile sections are drafted automatically

  Background:
    Given the DynamoDB tables exist
    And Bedrock is mocked to return questions

  Scenario: Starting a new interview session
    When I create a new interview session
    Then the response status is 200
    And the response contains a session_id
    And the response contains a message
    And the session is saved in DynamoDB with phase "interviewing"
    And questions_remaining is 20

  Scenario: Answering a question decrements questions remaining
    Given an active interview session exists
    When I respond with "I am a backend engineer"
    Then the response status is 200
    And questions_remaining is 19
    And the session history contains my answer

  Scenario: Skipping a section adds it to skipped_sections
    Given an active interview session exists
    When I skip section "identity"
    Then the response status is 200
    And "identity" is in skipped_sections

  Scenario: Reactivating a skipped section removes it
    Given a session with "identity" in skipped_sections
    When I reactivate section "identity"
    Then the response status is 200
    And "identity" is not in skipped_sections

  Scenario: Pausing transitions session to reviewing phase
    Given an active interview session exists
    And Bedrock is mocked to return drafts
    When I pause the interview
    Then the response status is 200
    And the phase is "reviewing"
    And draft_files are generated

  Scenario: Requesting more questions returns to interviewing
    Given a session in reviewing phase with 20 of 20 questions asked
    When I request 5 more questions
    Then the response status is 200
    And the phase is "interviewing"
    And questions_remaining is 5

  Scenario: Skipping a question does not count against total
    Given an active interview session exists
    When I skip a question
    Then the response status is 200
    And questions_remaining is 20
