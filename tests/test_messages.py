import pytest

from cbr_client import Message, File, ClientException
from conftest import base_url, correct_headers, messages_json

upload_files = [
    (f'test_report.zip.enc', b'report data'),
    (f'test_report.zip.enc.1.sig', b'operator sign'),
    (f'test_report.zip.enc.2.sig', b'client sign')
]

download_files = [

]


@pytest.fixture
def upload_file():
    file_data = messages_json[0]['Files'][0]
    f = File(**file_data)
    f.content = b'report data'
    yield f, file_data


def test_create_message(httpx_mock, client):
    httpx_mock.add_response(status_code=200,
                            json=messages_json[0],
                            headers={'Content-Type': 'application/json'},
                            method='POST',
                            url=f'{base_url}/back/rapi2/messages',
                            match_headers=correct_headers)
    msg = client.create_message(upload_files, '1-ПИ')
    assert isinstance(msg, Message)
    assert msg.status == 'draft'


@pytest.mark.parametrize('chunked', (True, False))
def test_upload(httpx_mock, client, upload_file, chunked):
    f, data = upload_file
    sdata = {'UploadUrl': '/', 'ExpirationDateTime': '2021-01-01 00:00:00'}
    httpx_mock.add_response(status_code=200,
                            json=sdata,
                            headers={'Content-Type': 'application/json'},
                            method='POST',
                            url=f'{base_url}{f.session_url}',
                            match_headers=correct_headers)
    httpx_mock.add_response(status_code=201,
                            json=data,
                            headers={'Content-Type': 'application/json'},
                            method='PUT',
                            url=f'{base_url}{f.upload_url}',
                            match_headers=correct_headers)
    resp = client.upload(f, chunked=chunked, chunk_size=6)
    assert f.name == resp.name
    assert f.size == resp.size


def test_finalize_message(httpx_mock, client):
    msg = Message(**messages_json[0])
    httpx_mock.add_response(status_code=200,
                            headers={'Content-Type': 'text/html'},
                            method='POST',
                            url=f'{base_url}/back/rapi2/messages/{msg.oid}',
                            match_headers=correct_headers)
    resp = client.finalize_message(msg)
    assert resp == b''


def test_create_message_error(client):
    with pytest.raises(ClientException) as exc:
        client.create_message(upload_files, '2-ПИ')
    assert exc.value.error_message == 'Неизвестный тип задачи 2-ПИ'


def test_get_messages(httpx_mock, client):
    httpx_mock.add_response(
        status_code=200,
        json=messages_json,
        headers={'Content-Type': 'application/json'},
        method='GET',
        url=(f'{base_url}/back/rapi2/messages?Page=1&Task=Zadacha_61&'
             f'Type=outbox&Status=registered'),
        match_headers=correct_headers)
    resp = client.get_messages(form='1-ПИ', msg_type='outbox',
                               status='registered')
    assert isinstance(resp, list)
    assert isinstance(resp[0], Message)
