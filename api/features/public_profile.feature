Feature: Public profile access
  As an AI agent or colleague
  I want to read someone's WhoIsMe profile
  So that I can understand how to work with them

  Background:
    Given the DynamoDB tables exist
    And a published user "alice" exists with public and private files

  Scenario: Anonymous access returns only public files
    When I GET the profile for "alice" without authentication
    Then the response status is 200
    And only public files are returned
    And authed is false

  Scenario: Valid bearer token returns all files
    Given "alice" has a bearer token "secret-token"
    When I GET the profile for "alice" with bearer token "secret-token"
    Then the response status is 200
    And all files are returned
    And authed is true

  Scenario: Wrong bearer token returns public files only
    Given "alice" has a bearer token "correct-token"
    When I GET the profile for "alice" with bearer token "wrong-token"
    Then the response status is 200
    And only public files are returned
    And authed is false

  Scenario: Unknown username returns 404
    When I GET the profile for "nobody" without authentication
    Then the response status is 404

  Scenario: Unpublished user returns 404
    Given an unpublished user "bob" exists
    When I GET the profile for "bob" without authentication
    Then the response status is 404
