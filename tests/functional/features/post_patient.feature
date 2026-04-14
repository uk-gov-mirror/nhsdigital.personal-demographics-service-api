Feature: Post Patient Spike Arrest Policy

Scenario: The rate limit is tripped when POSTing new Patients (>3tps)
    Given I am a healthcare worker user
    When I post to the Patient endpoint more than 3 times per second
    Then I get a mix of 400 and 429 HTTP response codes
    And the 429 response bodies alert me that there have been too many Create Patient requests

Scenario: The rate limit is tripped when POSTing to new create record at birth (>3tps)
    Given I am a healthcare worker user
    When I post to the create record at birth endpoint more than 3 times per second
    Then I get a mix of 400 and 429 HTTP response codes
    And the 429 response bodies alert me that there have been too many Create Patient requests

Scenario: The rate limit is shared between create patient and create record at birth (3tps total)
    Given I am a healthcare worker user
    When I post to the Patient endpoint and create record at birth endpoint more than 3 times per second in total
    Then I get a mix of 400 and 429 HTTP response codes
    And the 429 response bodies alert me that there have been too many Create Patient requests