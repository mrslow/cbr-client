import httpx
import logging

from dataclasses import dataclass, InitVar, asdict
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID

_BASE_URL = httpx.URL('https://portal5.cbr.ru')
_CHUNK_SIZE = 2**16

logger = logging.getLogger('cbr-client')
logger.setLevel('DEBUG')


tasks = {
    '1-ПИ': 'Zadacha_61',
    '1-ИЦБ': 'Zadacha_98',
    '1-АРЕНДА': 'Zadacha_98',
    '1-ПОЕЗДКИ': 'Zadacha_98',
    '1-РОУМИНГ': 'Zadacha_98',
    '1-ТРАНСПОРТ': 'Zadacha_98',
    '2-ТРАНСПОРТ': 'Zadacha_98',
    '3-ТРАНСПОРТ': 'Zadacha_98',
    '1-МЕД': 'Zadacha_98',
}


class ClientException(Exception):
    def __init__(self,
                 status: Optional[int] = None,
                 error_code: Optional[str] = None,
                 error_message: Optional[str] = None,
                 more_info: Optional[dict] = None):
        self.status = status
        self.error_code = error_code
        self.error_message = error_message
        self.more_info = more_info

    def __repr__(self):
        return (f'ClientException(status={self.status}, '
                f'error_code="{self.error_code}", '
                f'error_message="{self.error_message}", '
                f'more_info={self.more_info})')

    def __str__(self):
        return f'{self.status} {self.error_message}'


class Client:

    def __init__(self, *, login: str, password: str, url: str = None,
                 user_agent: str = None, timeout: float = 5.0):
        headers = {'Accept': 'application/json'}
        if user_agent:
            headers.update({'User-Agent': user_agent})
        if not url:
            url = _BASE_URL
        self.prefix = '/back/rapi2'
        if all((login, password)):
            self.client = httpx.AsyncClient(
                base_url=url,
                headers=headers,
                auth=(login, password),
                timeout=httpx.Timeout(timeout=timeout)
            )
        else:
            raise ClientException(
                error_message='Login and password are required')

    @property
    def is_closed(self):
        return self.client.is_closed

    @staticmethod
    def _set_payload(form, title, text, files):
        if form not in tasks:
            raise ClientException(
                error_message=f'Неизвестный тип задачи {form}')
        payload = {
            'Task': tasks[form],
            'Title': title or f'Отчет {form}',
            'Text': text,
            'Files': []
        }
        for f in files:
            signed = f'{f[0][:-6]}.enc' if f[0].endswith('.sig', -4) else None
            data = {
                'Name': f[0],
                'Encrypted': f[0].endswith('.enc', -4),
                'Size': len(f[1]),
                'SignedFile': signed,
                'ReposytoryType': 'http'
            }
            payload['Files'].append(data)
        return payload

    @staticmethod
    def _update_json(json, files):
        for f in files:
            for rf in json['Files']:
                if f[0] == rf['Name']:
                    rf['Content'] = f[1]
        return json

    @staticmethod
    def _upload_headers(index, offset, total):
        return dict([
            ('Content-Type', 'application/octet-stream'),
            ('Content-Length', str(offset)),
            ('Content-Range', f'bytes {index}-{index + offset - 1}/{total}')
        ])

    async def _partial_upload(self, f, chunk_size):
        if not f.content or len(f.content) == 0:
            raise ClientException(
                error_message='Uploaded file must not be empty')
        resp = None
        for i in range(0, len(f.content), chunk_size):
            chunk = f.content[i:i + chunk_size]
            hdrs = self._upload_headers(i, len(chunk), len(f.content))
            resp = await self._request(
                method='PUT',
                url=f.upload_url,
                headers=hdrs,
                content=chunk
            )
        return resp

    @staticmethod
    def is_json(resp):
        return 'application/json' in resp.headers.get('content-type', '')

    async def _request(self, method, url, **kwargs):
        if not url.startswith(self.prefix):
            url = self.prefix + url
        try:
            resp = await self.client.request(method, url, **kwargs)
            logger.debug(f'{method} {url} {resp.status_code}')
        except Exception as exc:
            logger.exception('Critical')
            raise ClientException(error_message=str(exc))
        try:
            resp.raise_for_status()
            return resp.json() if self.is_json(resp) else resp.content
        except httpx.HTTPStatusError as exc:
            err = Error(**resp.json()) if self.is_json(resp) else RespError(exc)
            logger.debug(err)
            raise ClientException(**err.dict())

    async def get_tasks(self):
        resp = await self._request('GET', '/tasks')
        return [Task(**item) for item in resp]

    async def get_profile(self):
        resp = await self._request('GET', '/profile')
        return Profile(**resp)

    async def get_profile_quota(self):
        resp = await self._request('GET', '/profile/quota')
        return ProfileQuota(**resp)

    async def get_dictionaries(self):
        resp = await self._request('GET', '/dictionaries')
        return [Dictionary(**dictionary) for dictionary in resp]

    async def get_dictionary(self, oid):
        return await self._request('GET', f'/dictionaries/{oid}')

    async def create_message(self, files, form, title=None, text=None):
        payload = self._set_payload(form, title, text, files)
        resp = await self._request('POST', '/messages', json=payload)
        json = self._update_json(resp, files)
        return Message(**json)

    async def upload(self, f, chunked=False, chunk_size=_CHUNK_SIZE):
        await self._request('POST', f.session_url)
        if chunked:
            resp = await self._partial_upload(f, chunk_size)
        else:
            hdr = self._upload_headers(0, len(f.content), len(f.content))
            resp = await self._request(
                method='PUT',
                url=f.upload_url,
                content=f.content,
                headers=hdr
            )
        return File(**resp)

    async def finalize_message(self, msg):
        return await self._request('POST', f'/messages/{msg.oid}')

    async def get_receipts(self, msg_id):
        receipts = await self._request('GET', f'/messages/{msg_id}/receipts')
        return [Receipt(**meta) for meta in receipts]

    async def download(self, f):
        f.content = await self._request('GET', f.download_url)

    async def get_messages(
            self,
            form: Optional[str] = None,
            msg_type: Optional[str] = None,
            status: Optional[str] = None,
            page: int = 1
    ):
        params = {'Page': page}
        if form:
            params['Task'] = tasks.get(form)
        if msg_type:
            params['Type'] = msg_type
        if status:
            params['Status'] = status
        messages = await self._request('GET', '/messages', params=params)
        return [Message(**msg) for msg in messages]

    async def delete_message(self, msg_id):
        return await self._request('DELETE', f'/messages/{msg_id}')

    async def close(self):
        if not self.is_closed:
            await self.client.aclose()

    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.__aexit__(exc_type, exc_val, exc_tb)


class Repository(BaseModel):
    type: str = Field(alias='RepositoryType', default=None)
    host: str = Field(alias='Host', default=None)
    port: int = Field(alias='Port', default=None)
    path: str = Field(alias='Path', default=None)


class File(BaseModel):
    name: str = Field(alias='Name', default=None)
    content: bytes = Field(alias='Content', default=None, repr=False)
    size: int = Field(alias='Size', default=0)
    encrypted: bool = Field(alias='Encrypted', default=False)
    signed_file: str = Field(alias='SignedFile', default=None)
    description: str = Field(alias='Description', default=None)
    oid: UUID = Field(alias='Id', default=None)
    repository: List[Repository] = Field(alias='RepositoryInfo',
                                         default_factory=list)

    @property
    def upload_url(self):
        path = self.repository[0].path.rsplit('/', 1)[0]
        return path if path.startswith('/') else f'/{path}'

    @property
    def session_url(self):
        return f'{self.upload_url}/createUploadSession'

    @property
    def download_url(self):
        return f'{self.upload_url}/download'


class Receipt(BaseModel):
    oid: UUID = Field(alias='Id', default=None)
    receive_time: datetime = Field(alias='ReceiveTime', default=None)
    status_time: datetime = Field(alias='StatusTime', default=None)
    status: str = Field(alias='Status', default=None)
    message: str = Field(alias='Message', default=None)
    files: List[File] = Field(alias='Files', default_factory=list)


class Message(BaseModel):
    files: List[File] = Field(alias='Files', default_factory=list)
    form: str = None
    oid: UUID = Field(alias='Id', default=None)
    corr_id: UUID = Field(alias='CorrelationId', default=None)
    group_id: UUID = Field(alias='GroupId', default=None)
    title: str = None
    text: str = None
    created: datetime = Field(alias='CreationDate', default=None)
    updated: datetime = Field(alias='UpdatedDate', default=None)
    status: str = Field(alias='Status', default=None)
    task: str = None
    regnum: str = Field(alias='RegNumber', default=None)
    size: int = Field(alias='TotalSize', default=0)
    receipts: List[Receipt] = Field(alias='Receipts', default_factory=list)


class Sender(BaseModel):
    inn: str = Field(alias='Inn', default=None)
    ogrn: str = Field(alias='Ogrn', default=None)
    bik: str = Field(alias='Bik', default=None)
    regnum: str = Field(alias='RegNum', default=None)
    division_code: str = Field(alias='DivisionCode', default=None)


class Task(BaseModel):
    code: str = Field(alias='Code', default=None)
    name: str = Field(alias='Name', default=None)
    description: str = Field(alias='Description', default=None)
    direction: str = Field(alias='Direction', default=None)
    allow_aspera: bool = Field(alias='AllowAspera', default=False)
    allow_linked_messages: bool = Field(alias='AllowLinkedMessages',
                                        default=False)


class SupervisionDivision(BaseModel):
    name: str = Field(alias='Name', default=None)


class Activity(BaseModel):
    short_name: str = Field(alias='ShortName', default=None)
    full_name: str = Field(alias='FullName', default=None)
    supervision_division: SupervisionDivision = Field(
        alias='SupervisionDevision')


class Profile(BaseModel):
    short_name: str = Field(alias='ShortName', default=None)
    full_name: str = Field(alias='FullName', default=None)
    activities: List[Activity] = Field(alias='Activities', default=None)
    inn: str = Field(alias='Inn', default=None)
    ogrn: str = Field(alias='Ogrn', default=None)
    international_id: str = Field(alias='InternationalId', default=None)
    opf: str = Field(alias='Opf', default=None)
    email: str = Field(alias='Email', default=None)
    address: str = Field(alias='Address', default=None)
    phone: str = Field(alias='Phone', default=None)
    created: datetime = Field(alias='CreationDate', default=None)
    status: str = Field(alias='Status', default=None)


class ProfileQuota(BaseModel):
    total: int = Field(alias='TotalQuota', default=0)
    used: int = Field(alias='UsedQuota', default=0)
    msg_size: int = Field(alias='MessageSize', default=0)


class Dictionary(BaseModel):
    oid: UUID = Field(alias='Id')
    text: str = Field(alias='Text')
    date: datetime = Field(alias='Date')


class Error(BaseModel):
    status: int = Field(alias='HTTPStatus')
    error_code: str = Field(alias='ErrorCode')
    error_message: str = Field(alias='ErrorMessage')
    more_info: Optional[dict] = Field(alias='MoreInfo')


@dataclass
class RespError:
    exc: InitVar[httpx.HTTPStatusError]
    status: int = Field(init=False)
    error_code: str = Field(init=False)
    error_message: str = Field(init=False)
    more_info: Optional[dict] = Field(init=False)

    def __post_init__(self, exc: httpx.HTTPStatusError):
        self.status: int = exc.response.status_code
        self.error_code: str = 'INCORRECT_RESPONSE_CONTENT'
        self.error_message: str = exc.response.reason_phrase
        self.more_info = None

    def dict(self):
        return asdict(self)
