import os
import os.path
import jwt
import uuid
import time
import requests
from pytest import fixture, skip
from pytest_bdd import scenario, given, when, then, parsers


skip("unfinished code", allow_module_level=True)


@fixture
def signing_key():
    try:
        keypath = os.path.abspath(os.getenv("UNATTENDED_ACCESS_SIGNING_KEY_PATH"))
    except TypeError:
        raise RuntimeError("UNATTENDED_ACCESS_SIGNING_KEY_PATH is blank or not set")

    with open(keypath, "r") as f:
        key = f.read()

    if not key:
        raise RuntimeError("Key empty. Check UNATTENDED_ACCESS_SIGNING_KEY_PATH.")

    return key


@fixture
def api_key():
    key = os.getenv("UNATTENDED_ACCESS_API_KEY")

    if not key:
        raise RuntimeError("No key found. Check UNATTENDED_ACCESS_API_KEY.")

    return key


@scenario(
    "features/unattended_access.feature",
    "PDS FHIR API accepts request with valid access token",
)
def test_valid():
    pass


@scenario(
    "features/unattended_access.feature",
    "PDS FHIR API rejects request with invalid access token",
)
def test_invalid():
    pass


@scenario(
    "features/unattended_access.feature",
    "PDS FHIR API rejects request with missing access token",
)
def test_missing():
    pass


@scenario(
    "features/unattended_access.feature",
    "PDS FHIR API rejects request with expired access token",
)
def test_expired():
    pass


@given("I am authenticating using unattended access", target_fixture="auth")
def auth():
    return {}


@given("I have a valid access token")
def set_valid_access_token(auth, signing_key, api_key):
    claims = {
        "sub": api_key,
        "iss": api_key,
        "jti": str(uuid.uuid4()),
        "aud": "https://api.service.nhs.uk/oauth2/token",
        "exp": int(time.time()) + 300,
    }

    encoded_jwt = jwt.encode(claims, signing_key, algorithm="RS512", headers={"kid": "test-1"})

    response = requests.post(
        "https://internal-dev.api.service.nhs.uk/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": encoded_jwt,
        },
    )

    print(response.json())

    assert False


@given("I have an invalid access token")
def set_invalid_access_token(auth):
    auth["access_token"] = "INVALID_ACCESS_TOKEN"


@given("I have no access token")
def set_no_access_token(auth):
    auth["access_token"] = None


@given("I have an expired access token")
def set_expired_access_token(auth, signing_key, api_key):
    claims = {
        "sub": api_key,
        "iss": api_key,
        "jti": str(uuid.uuid4()),
        "aud": "https://api.service.nhs.uk/oauth2/token",
        "exp": int(time.time()),
    }

    encoded_jwt = jwt.encode(claims, signing_key, algorithm="RS512", headers={"kid": "test-1"})

    response = requests.post(
        "https://internal-dev.api.service.nhs.uk/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": encoded_jwt,
        },
    )

    print(response.json())

    assert False


@given("I have a request context", target_fixture="context")
def context():
    return {}


@when("I GET a patient")
def get_patient(auth, context):
    authentication = auth["access_token"]

    if authentication is not None:
        authentication = f"Bearer {authentication}"

    response = requests.get(
        "https://internal-dev.api.service.nhs.uk/personal-demographics/Patient/9000000009",
        headers={
            "NHSD-SESSION-URID": "123",
            "Authorization": f"Bearer {authentication}",
        },
    )

    context["response"] = response.json()
    context["status"] = response.status_code


@then(
    parsers.cfparse(
        "I get a {status:Number} HTTP response", extra_types=dict(Number=int)
    )
)
def check_status(status, context):
    print(context["response"])
    assert context["status"] == status


@then("I get a Patient resource in the response")
def check_patient_resource(context):
    assert False


@then("I get a diagnosis of invalid access token")
def check_diagnosis_invalid(context):
    assert context["response"]["issue"][0]["diagnostics"] == "Invalid Access Token"


@then("I get a diagnosis of expired access token")
def check_diagnosis_expired(context):
    assert False


@then("I get an error response")
def check_error_response(context):
    assert context["response"]["issue"][0]["severity"] == "error"
