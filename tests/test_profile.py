import pytest
from cbr_client import ClientException, ProfileQuota, Profile

base_headers = {'Accept': 'application/json', 'User-Agent': 'pytest'}
base_url = 'https://portal5test.cbr.ru/back/rapi2'

correct_headers = base_headers.update({'Authorization': 'Basic dGVzdDoxMjM='})
wrong_headers = base_headers.update({'Authorization': 'Basic dGVzdDI6MzIx'})

correct_resp = {'status': 'correct'}
wrong_resp = {'status': 'wrong'}


def test_get_profile_ok(httpx_mock, client):
    httpx_mock.add_response(status_code=200,
                            json=correct_resp,
                            headers={'Content-Type': 'application/json'},
                            method='GET',
                            url=f'{base_url}/profile',
                            match_headers=correct_headers)
    info = client.get_profile()
    assert isinstance(info, Profile)
    # assert info['status'] == 'correct'


def test_get_profile_no_auth(httpx_mock, client):
    httpx_mock.add_response(status_code=401,
                            json=wrong_resp,
                            headers={'Content-Type': 'application/json'},
                            method='GET',
                            url=f'{base_url}/profile',
                            match_headers=wrong_headers)
    with pytest.raises(ClientException) as exc:
        client.get_profile()
    # assert '401' in exc.value.args[0]


def test_get_profile_quota(httpx_mock, client):
    quota_json = {'TotalQuota': 3221225472,
                  'UsedQuota': 0,
                  'MessageSize': 2147483648}
    httpx_mock.add_response(status_code=200,
                            json=quota_json,
                            headers={'Content-Type': 'application/json'},
                            method='GET',
                            url=f'{base_url}/profile/quota',
                            match_headers=correct_headers)
    info = client.get_profile_quota()
    assert isinstance(info, ProfileQuota)
    assert info.used == 0
