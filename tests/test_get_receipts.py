from cbr_client import Receipt
from conftest import base_url, correct_headers, receipts_json


def test_get_receipts(httpx_mock, client):
    msg_id = 'd66c4f1f-a6e5-4996-a6fb-fbb308135585'
    httpx_mock.add_response(
        status_code=200,
        json=receipts_json,
        headers={'Content-Type': 'application/json'},
        method='GET',
        url=f'{base_url}/back/rapi2/messages/{msg_id}/receipts',
        match_headers=correct_headers
    )
    receipts = client.get_receipts(msg_id=msg_id)
    assert isinstance(receipts, list)
    assert isinstance(receipts[0], Receipt)
