import httpx
import logging

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


class Client:

    def __init__(self, *, login: str, password: str, url: str = None,
                 user_agent: str = None, timeout: float = 5.0):
        headers = {'Accept': 'application/json'}
        if user_agent:
            headers.update({'User-Agent': user_agent})
        if not url:
            url = _BASE_URL
        if all((login, password)):
            self.client = httpx.Client(base_url=url,
                                       headers=headers,
                                       auth=(login, password),
                                       timeout=httpx.Timeout(timeout=timeout))
        else:
            raise ClientException(
                error_message='Login and password are required')

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
            data = {
                'Name': f[0],
                'Encrypted': int(f[0].endswith('.enc', -4)),
                'Size': len(f[1]),
                'SignedFile': f[0][:-6] if f[0].endswith('.sig', -4) else None,
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

    def _partial_upload(self, f, chunk_size):
        if not f.content or len(f.content) == 0:
            raise ClientException(
                error_message='Uploaded file must not be empty')
        resp = None
        for i in range(0, len(f.content), chunk_size):
            chunk = f.content[i:i + chunk_size]
            hdrs = self._upload_headers(i, len(chunk), len(f.content))
            resp = self._request('PUT', f.upload_url, headers=hdrs, data=chunk)
        return resp

    def _request(self, method, url, **kwargs):
        try:
            resp = self.client.request(method, url, **kwargs)
            logger.debug(f'{method} {url} {resp.status_code}')
        except Exception as exc:
            logger.exception('Critical')
            raise ClientException(error_message=str(exc))
        try:
            resp.raise_for_status()
            if 'application/json' in resp.headers.get('content-type', ''):
                return resp.json()
            else:
                return resp.content
        except httpx.HTTPStatusError:
            err = Error(**resp.json())
            logger.debug(err)
            raise ClientException(**err.dict())

    def get_tasks(self):
        resp = self._request('GET', '/back/rapi2/tasks')
        return [Task(**item) for item in resp]

    def get_profile(self):
        resp = self._request('GET', '/back/rapi2/profile')
        return Profile(**resp)

    def get_profile_quota(self):
        resp = self._request('GET', '/back/rapi2/profile/quota')
        return ProfileQuota(**resp)

    def get_dictionaries(self):
        resp = self._request('GET', '/back/rapi2/dictionaries')
        return [Dictionary(**dictionary) for dictionary in resp]

    def get_dictionary(self, oid):
        return self._request('GET', f'/back/rapi2/dictionaries/{oid}')

    def create_message(self, files, form, title=None, text=None):
        payload = self._set_payload(form, title, text, files)
        resp = self._request('POST', '/back/rapi2/messages', json=payload)
        json = self._update_json(resp, files)
        return Message(**json)

    def upload(self, f, chunked=False, chunk_size=_CHUNK_SIZE):
        self._request('POST', f.session_url)
        if chunked:
            resp = self._partial_upload(f, chunk_size)
        else:
            hdr = self._upload_headers(0, len(f.content), len(f.content))
            resp = self._request('PUT', f.upload_url, data=f.content,
                                 headers=hdr)
        return File(**resp)

    def finalize_message(self, msg):
        return self._request('POST', f'/back/rapi2/messages/{msg.oid}')

    def get_receipts(self, msg_id):
        receipts = self._request('GET',
                                 f'/back/rapi2/messages/{msg_id}/receipts')
        return [Receipt(**meta) for meta in receipts]

    def download(self, f):
        f.content = self._request('GET', f.download_url)

    def get_messages(self,
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
        messages = self._request('GET', '/back/rapi2/messages', params=params)
        return [Message(**msg) for msg in messages]

    def delete_message(self, msg_id):
        return self._request('DELETE', f'/back/rapi2/messages/{msg_id}')


class ReducedRepresentation:
    def __repr_args__(self: BaseModel) -> "ReprArgs":
        return [
            (key, value)
            for key, value in self.__dict__.items()
            if self.__fields__[key].field_info.extra.get("repr", True)
        ]


class Repository(BaseModel):
    type: str = Field(alias='RepositoryType', default=None)
    host: str = Field(alias='Host', default=None)
    port: int = Field(alias='Port', default=None)
    path: str = Field(alias='Path', default=None)


class File(ReducedRepresentation, BaseModel):
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
        return f'/back/{self.repository[0].path}'.rsplit('/', 1)[0]

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
