import pytest

from cbr_client import ClientException, ProfileQuota, Profile
from conftest import (base_url, correct_headers, wrong_headers, profile_json,
                      quota_json)

wrong_resp = {
  "HTTPStatus": 401,
  "ErrorCode": "ACCOUNT_NOT_FOUND ",
  "ErrorMessage": "Аккаунт не найден",
  "MoreInfo": {}
}


def test_get_profile_ok(httpx_mock, client):
    httpx_mock.add_response(status_code=200,
                            json=profile_json,
                            headers={'Content-Type': 'application/json'},
                            method='GET',
                            url=f'{base_url}/back/rapi2/profile',
                            match_headers=correct_headers)
    info = client.get_profile()
    assert isinstance(info, Profile)
    assert info.status == 'Active'


def test_get_profile_no_auth(httpx_mock, invalid_client):
    httpx_mock.add_response(status_code=401,
                            json=wrong_resp,
                            headers={'Content-Type': 'application/json'},
                            method='GET',
                            url=f'{base_url}/back/rapi2/profile',
                            match_headers=wrong_headers)
    with pytest.raises(ClientException) as exc:
        invalid_client.get_profile()
    assert exc.value.status == 401


def test_get_profile_quota(httpx_mock, client):
    httpx_mock.add_response(status_code=200,
                            json=quota_json,
                            headers={'Content-Type': 'application/json'},
                            method='GET',
                            url=f'{base_url}/back/rapi2/profile/quota',
                            match_headers=correct_headers)
    info = client.get_profile_quota()
    assert isinstance(info, ProfileQuota)
    assert info.used == 142645170

