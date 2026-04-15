import datetime
import json
import uuid
from urllib.parse import parse_qs, urlparse

import aiohttp
import asyncio
import requests
import pytest
import pytest_bdd

from dateutil import parser
from functools import partial
from lxml import html
from pytest_bdd import when, then

from tests.functional.configuration.config import (CLIENT_ID, CLIENT_SECRET)
from tests.functional.utils.helpers import get_role_id_from_user_info_endpoint


scenario = partial(pytest_bdd.scenario, './features/post_patient.feature')

PATIENTS_TO_CREATE = 40
TARGET_TIME_BETWEEN_FIRST_AND_LAST_REQUEST = 10
MAX_CONCURRENT_REQUESTS = PATIENTS_TO_CREATE


@scenario('The rate limit is tripped when POSTing new Patients (>3tps)')
def test_post_patient_rate_limit():
    """BDD scenario wrapper implemented by pytest-bdd steps."""


@scenario('The rate limit is tripped when POSTing to new create record at birth (>3tps)')
def test_post_create_record_at_birth_rate_limit():
    """BDD scenario wrapper implemented by pytest-bdd steps."""


@scenario('The rate limit is shared between create patient and create record at birth (3tps total)')
def test_shared_rate_limit_between_patient_create_endpoints():
    """BDD scenario wrapper implemented by pytest-bdd steps."""


# FIXTURES------------------------------------------------------------------------------------------------------
@pytest.fixture(scope='function')
def healthcare_worker_auth_headers(identity_service_base_url: str) -> dict:
    """Authenticates as a healthcare worker and returns valid request headers"""
    session = requests.session()
    follow_external_callback_redirects = False

    form_request = session.get(
        url=f"{identity_service_base_url}/authorize",
        params={
            "response_type": "code",
            "client_id": CLIENT_ID,
            "state": uuid.uuid4(),
            "redirect_uri": "https://example.org/callback"
        }
    )

    tree = html.fromstring(form_request.text)
    form = tree.forms[0]

    login_request = session.post(
        url=form.action,
        data={
            'username': '656005750107',
            'login': 'Sign in'
        },
        allow_redirects=follow_external_callback_redirects,
    )

    if follow_external_callback_redirects:
        login_location = login_request.history[-1].headers['Location']
    else:
        assert login_request.status_code in (301, 302, 303, 307, 308)

        login_location = login_request.headers['Location']
        for _ in range(10):
            if login_location.startswith("https://example.org/callback"):
                break
            next_response = session.get(login_location, allow_redirects=False)
            assert next_response.status_code in (301, 302, 303, 307, 308)
            login_location = next_response.headers['Location']

    code = parse_qs(urlparse(login_location).query)["code"][0]

    token_request = session.post(
        url=f"{identity_service_base_url}/token",
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': "https://example.org/callback",
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }
    )
    assert token_request.status_code == 200
    access_token = token_request.json()["access_token"]

    headers = {
        "X-Request-ID": str(uuid.uuid4()),
        "X-Correlation-ID": str(uuid.uuid4()),
        "Authorization": f'Bearer {access_token}'
    }

    role_id = get_role_id_from_user_info_endpoint(access_token, identity_service_base_url)
    headers.update({"NHSD-Session-URID": role_id})

    return headers


# SUPPORTING FUNCTIONS-------------------------------------------------------------------------------------------
async def _create_patient(session, headers, url, body):
    details = {'request_time': datetime.datetime.now(datetime.timezone.utc)}

    async with session.post(url=url, headers=headers, json=body) as resp:
        status = resp.status
        headers = resp.headers
        text = await resp.text()
        try:
            json_obj = json.loads(text)
        except ValueError:
            json_obj = resp.json()
        response_dict = json_obj
        details['status'] = status
        details['response'] = response_dict
        details['response_time'] = parser.parse(headers['Date'])
        return details


async def _create_patients(headers, request_specs, loop):
    conn = aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS, limit_per_host=MAX_CONCURRENT_REQUESTS)
    async with aiohttp.ClientSession(connector=conn, loop=loop) as session:
        results = await asyncio.gather(
            *[_create_patient(session, headers, url, body) for url, body in request_specs],
            return_exceptions=True
        )
        return results


def _create_request_specs(url, body, num_patients=PATIENTS_TO_CREATE):
    return [(url, body) for _ in range(num_patients)]


def _create_mixed_request_specs(pds_url, num_patients=PATIENTS_TO_CREATE):
    urls_and_bodies = [
        (f'{pds_url}/Patient', json.dumps({"nhsNumberAllocation": "Done"})),
        (f'{pds_url}/Patient/$create-record-at-birth', json.dumps({"createRecordAtBirthAllocation": "Done"}))
    ]
    return [urls_and_bodies[i % len(urls_and_bodies)] for i in range(num_patients)]


def _assert_requests_fired_fast_enough(results, target_time_between_first_and_last_request):
    request_times = sorted(x['request_time'] for x in results)
    elapsed_time_req = request_times[-1] - request_times[0]
    assert elapsed_time_req.total_seconds() < 1

    response_times = sorted(x['response_time'] for x in results)
    actual_time_between_first_and_last_request = response_times[-1] - response_times[0]

    assert actual_time_between_first_and_last_request.total_seconds() <= target_time_between_first_and_last_request


def _run_rate_limit_requests(healthcare_worker_auth_headers: dict, request_specs: list) -> list:
    loop = asyncio.new_event_loop()
    results = loop.run_until_complete(
        _create_patients(healthcare_worker_auth_headers, request_specs, loop)
    )
    _assert_requests_fired_fast_enough(results, TARGET_TIME_BETWEEN_FIRST_AND_LAST_REQUEST)
    return results


# STEPS----------------------------------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------------
# WHEN------------------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
@when("I post to the Patient endpoint more than 3 times per second", target_fixture='post_results')
def post_patient_multiple_times(healthcare_worker_auth_headers: dict, pds_url: str) -> list:
    url = f'{pds_url}/Patient'
    body = json.dumps({"nhsNumberAllocation": "Done"})
    request_specs = _create_request_specs(url, body)
    return _run_rate_limit_requests(healthcare_worker_auth_headers, request_specs)


@pytest.mark.asyncio
@when("I post to the create record at birth endpoint more than 3 times per second", target_fixture='post_results')
def post_create_record_at_birth_multiple_times(healthcare_worker_auth_headers: dict, pds_url: str) -> list:
    url = f'{pds_url}/Patient/$create-record-at-birth'
    body = json.dumps({"createRecordAtBirthAllocation": "Done"})
    request_specs = _create_request_specs(url, body)
    return _run_rate_limit_requests(healthcare_worker_auth_headers, request_specs)


@pytest.mark.asyncio
@when(
    "I post to the Patient endpoint and create record at birth endpoint more than 3 times per second in total",
    target_fixture='post_results'
)
def post_to_both_endpoints_multiple_times(healthcare_worker_auth_headers: dict, pds_url: str) -> list:
    request_specs = _create_mixed_request_specs(pds_url)
    return _run_rate_limit_requests(healthcare_worker_auth_headers, request_specs)


# THEN------------------------------------------------------------------------------------------------------------
@then("I get a mix of 400 and 429 HTTP response codes")
def assert_expected_spike_arrest_response_codes(post_results):
    successful_requests = [x for x in post_results if x['status'] == 400]
    spike_arrests = [x for x in post_results if x['status'] == 429]
    # Different environments can throttle slightly differently; require a true 400/429 mix.
    assert len(successful_requests) > 0
    assert len(spike_arrests) > 0
    assert len(successful_requests) + len(spike_arrests) == len(post_results)


@then("the 429 response bodies alert me that there have been too many Create Patient requests")
def assert_expected_429_diagnostics(post_results):
    spike_arrests = [x for x in post_results if x['status'] == 429]
    diagnostics = [x['response']['issue'][0]['diagnostics'] for x in spike_arrests]
    expected_diagnostics = 'There have been too many Create Patient requests. Please try again later.'
    correct_diagnostics = [x for x in diagnostics if x == expected_diagnostics]
    assert len(correct_diagnostics) == len(spike_arrests), "Some of the diagnostics messages were not as expected"
