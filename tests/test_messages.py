import pytest

from cbr_client import Message, File, ClientException
from conftest import base_url, correct_headers, messages_json

upload_files = [
    (f'test_report.zip.enc', b'report data'),
    (f'test_report.zip.1.sig', b'operator sign'),
    (f'test_report.zip.2.sig', b'client sign'),
    (f'DOVER_CBR_1234567890_20000101_1.xml', b'mchd data'),
    (f'DOVER_CBR_1234567890_20000101_1.xml.sig', b'mchd sign'),
    (f'DOVER_CBR_1234567890111_20000101_1.xml', b'error mchd data'),
    (f'DOVER_CBR_1234567890111_20000101_1.xml.sig', b'error mchd sign'),
]

download_files = [

]


@pytest.fixture
def upload_file():
    file_data = messages_json[0]['Files'][0]
    f = File(**file_data)
    f.content = b'report data'
    yield f, file_data


@pytest.mark.asyncio
async def test_create_message(httpx_mock, client):
    httpx_mock.add_response(
        status_code=200,
        json=messages_json[0],
        headers={'Content-Type': 'application/json'},
        method='POST',
        url=f'{base_url}/back/rapi2/{client.api_version}/messages',
        match_headers=correct_headers
    )
    msg = await client.create_message(upload_files[:-2], '1-ПИ')
    assert isinstance(msg, Message)
    assert msg.status == 'draft'


@pytest.mark.asyncio
@pytest.mark.parametrize('chunked', (True, False))
async def test_upload(httpx_mock, client, upload_file, chunked):
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
    resp = await client.upload(f, chunked=chunked, chunk_size=6)
    assert f.name == resp.name
    assert f.size == resp.size


@pytest.mark.asyncio
async def test_finalize_message(httpx_mock, client):
    msg = Message(**messages_json[0])
    httpx_mock.add_response(
        status_code=200,
        headers={'Content-Type': 'text/html'},
        method='POST',
        url=f'{base_url}/back/rapi2/{client.api_version}/messages/{msg.oid}',
        match_headers=correct_headers
    )
    resp = await client.finalize_message(msg)
    assert resp == b''


@pytest.mark.asyncio
async def test_create_message_error(client):
    with pytest.raises(ClientException) as exc:
        await client.create_message(upload_files, '2-ПИ')
    assert exc.value.error_message == 'Unknown task type 2-ПИ'


@pytest.mark.asyncio
async def test_create_message_mchd_error(client):
    fn = 'DOVER_CBR_1234567890111_20000101_1.xml'
    err = f'Filename {fn} does not match pattern'
    with pytest.raises(ClientException) as exc:
        await client.create_message(upload_files, '1-ПИ')
    assert exc.value.error_message == err


@pytest.mark.asyncio
async def test_get_messages(httpx_mock, client):
    httpx_mock.add_response(
        status_code=200,
        json=messages_json,
        headers={'Content-Type': 'application/json'},
        method='GET',
        url=(f'{base_url}/back/rapi2/{client.api_version}/messages'
             f'?Page=1&Task=Zadacha_61&Type=outbox&Status=registered'),
        match_headers=correct_headers)
    resp = await client.get_messages(
        form='1-ПИ',
        msg_type='outbox',
        status='registered'
    )
    assert isinstance(resp, list)
    assert isinstance(resp[0], Message)
