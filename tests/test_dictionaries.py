from cbr_client import Dictionary
from conftest import (base_url, correct_headers, dictionary_json,
                      dictionaries_json)


def test_get_dictionaries(httpx_mock, client):
    httpx_mock.add_response(status_code=200,
                            json=dictionaries_json,
                            headers={'Content-Type': 'application/json'},
                            method='GET',
                            url=f'{base_url}/back/rapi2/dictionaries',
                            match_headers=correct_headers)
    dicts = client.get_dictionaries()
    assert isinstance(dicts, list)
    assert isinstance(dicts[0], Dictionary)


def test_get_dictionary(httpx_mock, client):
    oid = '8a6a8d3b-c726-4a94-9fed-97d19ea8d202'
    httpx_mock.add_response(status_code=200,
                            json=dictionary_json,
                            headers={'Content-Type': 'application/json'},
                            method='GET',
                            url=f'{base_url}/back/rapi2/dictionaries/{oid}',
                            match_headers=correct_headers)
    d = client.get_dictionary(oid=oid)
    assert isinstance(d, dict)
