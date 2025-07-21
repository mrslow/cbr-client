import httpx
import pytest
from conftest import base_url, correct_headers, messages_json

from cbr_client import _BASE_URL, Client, ClientException, File

error_text = {
    "auth": "Логин и пароль являются обязательными",
    "version": "Значение api_version должно быть v1 или v2",
    "size": "Загружаемый файл должен иметь ненулевой размер",
}


def test_client_no_credentials():
    with pytest.raises(ClientException) as exc:
        Client(url=base_url, login="", password="")
    assert exc.value.error_message == error_text["auth"]


def test_client_no_url():
    client = Client(login="test", password="test")
    assert client.client.base_url == _BASE_URL


@pytest.mark.parametrize("vers", (None, "v3"))
def test_client_invalid_api_version(vers):
    with pytest.raises(ClientException) as exc:
        Client(url=base_url, login="test", password="test", api_version=vers)
    assert exc.value.error_message == error_text["version"]


async def test_client_contextmanager():
    async with Client(login="test", password="test") as client:
        assert not client.is_closed
        assert client.client._auth._auth_header == "Basic dGVzdDp0ZXN0"


async def test_partial_upload_no_content(client):
    f = File(**messages_json[0]["Files"][0])
    with pytest.raises(ClientException) as exc:
        await client._partial_upload(f, chunk_size=2**8)
    assert exc.value.error_message == error_text["size"]


async def test_request_exception(httpx_mock, client):
    def raise_timeout(request):
        raise httpx.ReadTimeout("Test timeout error", request=request)

    httpx_mock.add_callback(raise_timeout)

    with pytest.raises(httpx.ReadTimeout) as exc:
        await client._request("GET", "/test")
    assert exc.value.args[0] == "Test timeout error"


async def test_download(httpx_mock, client):
    f = File(**messages_json[0]["Files"][0])
    httpx_mock.add_response(
        status_code=200,
        content=b"test",
        headers={"Content-Type": "application/octet-stream"},
        method="GET",
        url=(
            f"{base_url}/back/rapi2/messages/"
            f"89f43940-5a3f-4343-a550-d0f0d2152ff5/files/"
            f"e9a30113-6b20-45c8-a923-69f448757655/download"
        ),
        match_headers=correct_headers,
    )
    await client.download(f)
    assert f.content == b"test"


async def test_delete(httpx_mock, client):
    msg_id = "89f43940-5a3f-4343-a550-d0f0d2152ff5"
    httpx_mock.add_response(
        status_code=200,
        headers={"Content-Type": "application/octet-stream"},
        method="DELETE",
        url=f"{base_url}/back/rapi2/{client.api_version}/messages/{msg_id}",
    )
    resp = await client.delete_message(msg_id=msg_id)
    assert resp == b""


async def test_invalid_response(httpx_mock, client):
    httpx_mock.add_response(
        status_code=502,
        headers={"Content-Type": "application/octet-stream"},
        method="GET",
        url=f"{base_url}/back/rapi2/{client.api_version}/test",
    )
    with pytest.raises(ClientException) as exc:
        await client._request("GET", "/test")
    assert exc.value.error_message == "Bad Gateway"
    assert exc.value.status == 502
    assert exc.value.error_code == "INCORRECT_RESPONSE_CONTENT"
    assert exc.value.more_info is None


def test_upload_json(client):
    json = {"Files": [{"Name": "a"}]}
    files = [("a", b"test")]
    new_json = client._update_json(json, files)
    assert new_json["Files"][0]["Name"] == "a"
    assert new_json["Files"][0]["Content"] == b"test"


def test_exception_repr():
    exc = ClientException(
        status=401,
        error_code="ACCOUNT_NOT_FOUND",
        error_message="Аккаунт не найден",
        more_info={},
    )
    assert repr(exc) == (
        'ClientException(status=401, error_code="ACCOUNT_NOT_FOUND", '
        'error_message="Аккаунт не найден", more_info={})'
    )
    assert str(exc) == "401 Аккаунт не найден"
