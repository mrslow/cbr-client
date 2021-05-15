import httpx
import pytest

from pydantic import BaseModel, Field
from cbr_client import (Client, ClientException, _BASE_URL, File,
                        ReducedRepresentation)
from conftest import base_url, messages_json, correct_headers


def test_client_no_credentials():
    with pytest.raises(ClientException) as exc:
        Client(url=base_url, login='', password='')
    assert exc.value.error_message == 'Login and password are required'


def test_client_no_url():
    client = Client(login='test', password='test')
    assert client.client.base_url == _BASE_URL


def test_partial_upload_no_content(client, ):
    f = File(**messages_json[0]['Files'][0])
    with pytest.raises(ClientException) as exc:
        client._partial_upload(f, chunk_size=2**8)
    assert exc.value.error_message == 'Uploaded file must not be empty'


def test_request_exception(httpx_mock, client):
    def raise_timeout(request, extensions: dict):
        raise httpx.ReadTimeout('Test timeout error', request=request)

    httpx_mock.add_callback(raise_timeout)

    with pytest.raises(ClientException) as exc:
        client._request('GET', '/test')
    assert exc.value.error_message == 'Test timeout error'


def test_download(httpx_mock, client):
    f = File(**messages_json[0]['Files'][0])
    httpx_mock.add_response(
        status_code=200,
        data=b'test',
        headers={'Content-Type': 'application/octet-stream'},
        method='GET',
        url=(f'{base_url}/back/rapi2/messages/'
             f'89f43940-5a3f-4343-a550-d0f0d2152ff5/files/'
             f'e9a30113-6b20-45c8-a923-69f448757655/download'),
        match_headers=correct_headers)
    client.download(f)
    assert f.content == b'test'


def test_delete(httpx_mock, client):
    msg_id = '89f43940-5a3f-4343-a550-d0f0d2152ff5'
    httpx_mock.add_response(
        status_code=200,
        headers={'Content-Type': 'application/octet-stream'},
        method='DELETE',
        url=f'{base_url}/back/rapi2/messages/{msg_id}'
    )
    resp = client.delete_message(msg_id=msg_id)
    assert resp == b''


def test_upload_json(client):
    json = {'Files': [{'Name': 'a'}]}
    files = [('a', b'test')]
    new_json = client._update_json(json, files)
    assert new_json['Files'][0]['Name'] == 'a'
    assert new_json['Files'][0]['Content'] == b'test'


def test_repr_field():
    class Model(ReducedRepresentation, BaseModel):
        a: int = Field()
        b: int = Field(repr=True)
        c: int = Field(repr=False)

    m = Model(a=1, b=2, c=3)
    assert "a=1" in repr(m)
    assert "b=2" in repr(m)
    assert "c=3" not in repr(m)
