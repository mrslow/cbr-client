import logging
import re
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import httpx
from pydantic import BaseModel, Field

_BASE_URL = httpx.URL("https://portal5.cbr.ru")
_CHUNK_SIZE = 2**16
_MCHD = re.compile(
    r"^((DOVER_CBR_(?:\d{10}|\d{12}))|ON_EMCHD)"
    r"_\d{8}_(.{1,10}|[a-fA-F0-9-]{36})\.[xX][mM][lL]$"
)

logger = logging.getLogger("cbr-client")
logger.setLevel("DEBUG")


type_map = {
    "sig": "Sign",
    "xml": "SerializedWebForm",
    "poa": "PowerOfAttorney",
}


class ClientException(Exception):
    def __init__(
        self,
        status: Optional[int] = 418,
        error_code: Optional[str] = "I_AM_A_TEAPOT",
        error_message: Optional[str] = None,
        more_info: Optional[dict] = None,
    ):
        self.status = status
        self.error_code = error_code
        self.error_message = error_message
        self.more_info = more_info

    def __repr__(self):
        return (
            f"ClientException(status={self.status}, "
            f'error_code="{self.error_code}", '
            f'error_message="{self.error_message}", '
            f"more_info={self.more_info})"
        )

    def __str__(self):
        return f"{self.status} {self.error_message}"


class Client:
    def __init__(
        self,
        *,
        login: str,
        password: str,
        url: str = None,
        user_agent: str = None,
        timeout: float = 5.0,
        api_version: str = "v2",
    ):
        headers = {"Accept": "application/json"}
        if user_agent:
            headers.update({"User-Agent": user_agent})
        if api_version not in ("v1", "v2"):
            raise ClientException(
                error_message="Значение api_version должно быть v1 или v2"
            )
        self.api_version = api_version
        self.prefix = "/back/rapi2"
        if not url:
            url = _BASE_URL
        if all((login, password)):
            self.client = httpx.AsyncClient(
                base_url=url,
                headers=headers,
                auth=(login, password),
                timeout=httpx.Timeout(timeout=timeout),
            )
        else:
            raise ClientException(
                error_message="Логин и пароль являются обязательными"
            )

    @property
    def is_closed(self):
        return self.client.is_closed

    @staticmethod
    def _get_filetype(name):
        s = name.split(".")
        tail = s[-1]
        if s[0].startswith(("DOVER_CBR", "ON_EMCHD")) and tail != "sig":
            tail = "poa"
            if not _MCHD.match(name):
                raise ClientException(
                    error_message=f"Имя файла {name} не соответствует шаблону"
                )
        return type_map.get(tail, "Document")

    @staticmethod
    def _get_signed(name):
        s = name.split(".")
        tail = s[-1]
        if tail == "sig":
            signed = ".".join(s[:2])
            return f"{signed}.enc" if signed.endswith(".zip") else signed

    def _set_payload(self, task, title, text, corr_id, files):
        payload = {
            "Task": task,
            "Title": title,
            "Text": text,
            "Files": [],
        }
        if corr_id is not None:
            payload["CorrelationId"] = str(corr_id)
        for f in files:
            filetype = f[2] if len(f) == 3 else self._get_filetype(f[0])
            data = {
                "Name": f[0],
                "Encrypted": f[0].endswith(".enc", -4),
                "Size": len(f[1]),
                "FileType": filetype,
                "SignedFile": self._get_signed(f[0]),
                "ReposytoryType": "http",
            }
            payload["Files"].append(data)
        return payload

    @staticmethod
    def _update_json(json, files):
        for f in files:
            for rf in json["Files"]:
                if f[0] == rf["Name"]:
                    rf["Content"] = f[1]
        return json

    @staticmethod
    def _upload_headers(index, offset, total):
        return {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(offset),
            "Content-Range": f"bytes {index}-{index + offset - 1}/{total}",
        }

    async def _partial_upload(self, f, chunk_size):
        if not f.content or len(f.content) == 0:
            raise ClientException(
                error_message="Загружаемый файл должен иметь ненулевой размер"
            )
        resp = None
        for i in range(0, len(f.content), chunk_size):
            chunk = f.content[i : i + chunk_size]
            hdrs = self._upload_headers(i, len(chunk), len(f.content))
            resp = await self._request(
                method="PUT", url=f.upload_url, headers=hdrs, content=chunk
            )
        return resp

    @staticmethod
    def is_json(resp):
        return "application/json" in resp.headers.get("content-type", "")

    async def _request(self, method, url, **kwargs):
        if not url.startswith(self.prefix):
            url = f"{self.prefix}/{self.api_version}" + url
        resp = await self.client.request(method, url, **kwargs)
        logger.debug(f"{method} {url} {resp.status_code}")
        try:
            resp.raise_for_status()
            return resp.json() if self.is_json(resp) else resp.content
        except httpx.HTTPStatusError as exc:
            err = Error(**resp.json()) if self.is_json(resp) else make_err(exc)
            logger.debug(err)
            raise ClientException(**err.dict())

    async def get_tasks(self):
        resp = await self._request("GET", "/tasks")
        return [Task(**item) for item in resp]

    async def get_profile(self):
        resp = await self._request("GET", "/profile")
        return Profile(**resp)

    async def get_profile_quota(self):
        resp = await self._request("GET", "/profile/quota")
        return ProfileQuota(**resp)

    async def get_dictionaries(self):
        resp = await self._request("GET", "/dictionaries")
        return [Dictionary(**dictionary) for dictionary in resp]

    async def get_dictionary(self, oid):
        return await self._request("GET", f"/dictionaries/{oid}")

    async def create_message(
        self, files, task, title=None, text=None, corr_id=None
    ):
        payload = self._set_payload(task, title, text, corr_id, files)
        resp = await self._request("POST", "/messages", json=payload)
        json = self._update_json(resp, files)
        return Message(**json)

    async def upload(self, f, chunked=False, chunk_size=_CHUNK_SIZE):
        await self._request("POST", f.session_url)
        if chunked:
            resp = await self._partial_upload(f, chunk_size)
        else:
            hdr = self._upload_headers(0, len(f.content), len(f.content))
            resp = await self._request(
                method="PUT", url=f.upload_url, content=f.content, headers=hdr
            )
        return File(**resp)

    async def finalize_message(self, msg):
        return await self._request("POST", f"/messages/{msg.oid}")

    async def get_receipts(self, msg_id):
        receipts = await self._request("GET", f"/messages/{msg_id}/receipts")
        return [Receipt(**meta) for meta in receipts]

    async def download(self, f):
        f.content = await self._request("GET", f.download_url)

    async def get_messages(
        self,
        task: Optional[str] = None,
        msg_type: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
    ):
        params = {"Page": page}
        if task:
            params["Task"] = task
        if msg_type:
            params["Type"] = msg_type
        if status:
            params["Status"] = status
        messages = await self._request("GET", "/messages", params=params)
        return [Message(**msg) for msg in messages]

    async def delete_message(self, msg_id):
        return await self._request("DELETE", f"/messages/{msg_id}")

    async def close(self):
        if not self.is_closed:
            await self.client.aclose()

    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.__aexit__(exc_type, exc_val, exc_tb)


class Repository(BaseModel):
    type: str = Field(alias="RepositoryType", default=None)
    host: str = Field(alias="Host", default=None)
    port: int = Field(alias="Port", default=None)
    path: str = Field(alias="Path", default=None)


class File(BaseModel):
    name: str = Field(alias="Name", default=None)
    content: bytes = Field(alias="Content", default=None, repr=False)
    size: int = Field(alias="Size", default=0)
    encrypted: bool = Field(alias="Encrypted", default=False)
    filetype: str = Field(alias="FileType", default=None)
    signed_file: str = Field(alias="SignedFile", default=None)
    description: str = Field(alias="Description", default=None)
    oid: UUID = Field(alias="Id", default=None)
    repository: List[Repository] = Field(
        alias="RepositoryInfo", default_factory=list
    )

    @property
    def upload_url(self):
        path = self.repository[0].path.rsplit("/", 1)[0]
        return path if path.startswith("/") else f"/{path}"

    @property
    def session_url(self):
        return f"{self.upload_url}/createUploadSession"

    @property
    def download_url(self):
        return f"{self.upload_url}/download"


class Receipt(BaseModel):
    oid: UUID = Field(alias="Id", default=None)
    receive_time: datetime = Field(alias="ReceiveTime", default=None)
    status_time: datetime = Field(alias="StatusTime", default=None)
    status: str = Field(alias="Status", default=None)
    message: str = Field(alias="Message", default=None)
    files: List[File] = Field(alias="Files", default_factory=list)


class Message(BaseModel):
    files: List[File] = Field(alias="Files", default_factory=list)
    form: str = None
    oid: UUID = Field(alias="Id", default=None)
    corr_id: UUID = Field(alias="CorrelationId", default=None)
    group_id: UUID = Field(alias="GroupId", default=None)
    title: str = None
    text: str = None
    created: datetime = Field(alias="CreationDate", default=None)
    updated: datetime = Field(alias="UpdatedDate", default=None)
    status: str = Field(alias="Status", default=None)
    task: str = None
    regnum: str = Field(alias="RegNumber", default=None)
    size: int = Field(alias="TotalSize", default=0)
    receipts: List[Receipt] = Field(alias="Receipts", default_factory=list)


class Sender(BaseModel):
    inn: str = Field(alias="Inn", default=None)
    ogrn: str = Field(alias="Ogrn", default=None)
    bik: str = Field(alias="Bik", default=None)
    regnum: str = Field(alias="RegNum", default=None)
    division_code: str = Field(alias="DivisionCode", default=None)


class Task(BaseModel):
    code: str = Field(alias="Code", default=None)
    name: str = Field(alias="Name", default=None)
    description: str = Field(alias="Description", default=None)
    direction: str = Field(alias="Direction", default=None)
    allow_aspera: bool = Field(alias="AllowAspera", default=False)
    allow_linked_messages: bool = Field(
        alias="AllowLinkedMessages", default=False
    )


class SupervisionDivision(BaseModel):
    name: str = Field(alias="Name", default=None)


class Activity(BaseModel):
    short_name: str = Field(alias="ShortName", default=None)
    full_name: str = Field(alias="FullName", default=None)
    supervision_division: SupervisionDivision = Field(
        alias="SupervisionDevision"
    )


class Profile(BaseModel):
    short_name: str = Field(alias="ShortName", default=None)
    full_name: str = Field(alias="FullName", default=None)
    activities: List[Activity] = Field(alias="Activities", default=None)
    inn: str = Field(alias="Inn", default=None)
    ogrn: str = Field(alias="Ogrn", default=None)
    international_id: str = Field(alias="InternationalId", default=None)
    opf: str = Field(alias="Opf", default=None)
    email: str = Field(alias="Email", default=None)
    address: str = Field(alias="Address", default=None)
    phone: str = Field(alias="Phone", default=None)
    created: datetime = Field(alias="CreationDate", default=None)
    status: str = Field(alias="Status", default=None)


class ProfileQuota(BaseModel):
    total: int = Field(alias="TotalQuota", default=0)
    used: int = Field(alias="UsedQuota", default=0)
    msg_size: int = Field(alias="MessageSize", default=0)


class Dictionary(BaseModel):
    oid: UUID = Field(alias="Id")
    text: str = Field(alias="Text")
    date: datetime = Field(alias="Date")


class Error(BaseModel):
    status: int = Field(alias="HTTPStatus")
    error_code: str = Field(alias="ErrorCode")
    error_message: str = Field(alias="ErrorMessage")
    more_info: Optional[dict] = Field(alias="MoreInfo")


def make_err(exc: httpx.HTTPStatusError):
    return Error(
        **{
            "HTTPStatus": exc.response.status_code,
            "ErrorCode": "INCORRECT_RESPONSE_CONTENT",
            "ErrorMessage": exc.response.reason_phrase,
            "MoreInfo": None,
        }
    )
