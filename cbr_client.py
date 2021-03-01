import httpx
import logging

from dataclasses import dataclass, field, InitVar, MISSING
from datetime import datetime
from uuid import UUID

_BASE_URL = 'https://portal5.cbr.ru/back/rapi2'
_CHUNK_SIZE = 1024 * 64

logger = logging.getLogger('cbr-client')
logger.setLevel('DEBUG')


tasks = {
    '1-ПИ': 'Zadacha_61',
    '1-PI': 'Zadacha_61',
    '1-ИЦБ': 'Zadacha_98',
    '1-ICB': 'Zadacha_98',
    '1-АРЕНДА': 'Zadacha_98',
    '1-ARENDA': 'Zadacha_98',
    '1-ПОЕЗДКИ': 'Zadacha_98',
    '1-POEZDKI': 'Zadacha_98',
    '1-РОУМИНГ': 'Zadacha_98',
    '1-ROUMING': 'Zadacha_98',
    '1-ТРАНСПОРТ': 'Zadacha_98',
    '1-TRANSPORT': 'Zadacha_98',
    '2-ТРАНСПОРТ': 'Zadacha_98',
    '2-TRANSPORT': 'Zadacha_98',
    '3-ТРАНСПОРТ': 'Zadacha_98',
    '3-TRANSPORT': 'Zadacha_98',
    '1-МЕД': 'Zadacha_98',
    '1-MED': 'Zadacha_98',
}


def str_to_date(date_str):
    if date_str:
        return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')


def str_to_uuid(uuid_str):
    return UUID(uuid_str) if uuid_str else None


class ClientException(Exception):
    pass


class Client:

    def __init__(self, *, login: str, password: str, url: str = None,
                 user_agent: str = None):
        headers = {'Accept': 'application/json'}
        if user_agent:
            headers.update({'User-Agent': user_agent})
        if not url:
            url = _BASE_URL
        if all((login, password)):
            self.client = httpx.Client(base_url=url,
                                       headers=headers,
                                       auth=(login, password))
        else:
            raise ClientException('Login and password are required')

    def get_tasks(self):
        resp = self._request('GET', '/tasks')
        return [Task(item) for item in resp]

    def get_profile(self):
        resp = self._request('GET', '/profile')
        return Profile(resp)

    def get_profile_quota(self):
        resp = self._request('GET', '/profile/quota')
        return ProfileQuota(resp)

    def get_dictionaries(self):
        return self._request('GET', '/dictionaries')

    def get_dictionary(self, oid):
        return self._request('GET', f'/dictionaries/{oid}')

    def create_message(self, files, form):
        msg = OutboxMessage(files, form)
        resp = self._request('POST', '/messages', json=msg.get_payload())
        msg.refill(resp)
        return msg

    def _partial_upload(self, f):
        for i in range(0, len(f.content), _CHUNK_SIZE):
            chunk = f.content[i:i + _CHUNK_SIZE]
            headers = dict([
                ('Content-Type', 'application/octet-stream'),
                ('Content-Length', str(len(chunk))),
                ('Content-Range', f'bytes {i}-{i+len(chunk)-1}/{f.size}')
            ])
            self._request('PUT', f.upload_url, headers=headers, data=f.content)

    def upload(self, msg):
        for f in msg.files:
            self._request('POST', f.session_url)
            self._partial_upload(f)

    def finalize_message(self, msg):
        self._request('POST', f'/messages/{msg.oid}')

    def get_receipts(self, msg_id):
        receipts = self._request('GET', f'/messages/{msg_id}/receipts')
        return [Receipt(msg_id=msg_id, meta=meta) for meta in receipts]

    def download(self, obj):
        for f in obj.files:
            f.content = self._request('GET', f.download_url)

    def get_messages(self,
                     task: str = None,
                     type: str = None,
                     status: str = None,
                     page: int = 1
                     ):
        params = {'Page': page}
        if task:
            params['Task'] = task
        if type:
            params['Type'] = type
        if status:
            params['Status'] = status
        messages = self._request('GET', '/messages', json=params)
        return [InboxMessage(msg) for msg in messages]

    def delete_message(self, msg_id):
        return self._request('DELETE', f'/messages/{msg_id}')

    def _request(self, method, url, **kwargs):
        resp = self.client.request(method, url, **kwargs)
        logger.debug(f'{method} {url} {resp.status_code}')
        try:
            resp.raise_for_status()
            if 'application/json' in resp.headers.get('content-type', ''):
                return resp.json()
            else:
                return resp.content
        except httpx.HTTPStatusError as exc:
            raise ClientException(str(exc))


@dataclass
class Message:
    files: list = field(init=False, default_factory=list)
    form: str = field(init=False, default=None)
    oid: UUID = field(init=False, default=None)
    corr_id: UUID = field(init=False, default=None)
    group_id: UUID = field(init=False, default=None)
    title: str = field(init=False, default=None)
    text: str = field(init=False, default=None)
    created: datetime = field(init=False, default=None)
    updated: datetime = field(init=False, default=None)
    status: str = field(init=False, default=None)
    task: str = field(init=False, default=None)
    regnum: str = field(init=False, default=None)
    size: int = field(init=False, default=0)
    receipts: list = field(init=False, default_factory=list)

    def refill(self, meta):
        self.oid = str_to_uuid(meta.get('Id'))
        self.corr_id = str_to_uuid(meta.get('CorrelationId'))
        self.group_id = str_to_uuid(meta.get('GroupId'))
        self.created = str_to_date(meta.get('CreationDate'))
        self.updated = str_to_date(meta.get('UpdatedDate'))
        self.status = meta.get('Status')
        self.regnum = meta.get('RegNumber')
        self.size = meta.get('TotalSize')
        if len(self.files) > 0:
            self._update_files(meta['Files'])
        else:
            self._set_files(meta['Files'])

    def _set_files(self, info):
        self.files = [UploadFile(msg_id=self.oid, meta=meta) for meta in info]

    def _update_files(self, info):
        for meta in info:
            for f in self.files:
                if f.name == meta['Name']:
                    f.msg_id = self.oid
                    f.refill(meta)
                    break


@dataclass
class OutboxMessage(Message):
    files: list
    form: InitVar[str] = field(init=True)

    def __post_init__(self, form):
        self.task = tasks[form]
        self.title = f'Отправка отчета {form}'
        self.text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.files = [DownloadFile(msg_id=self.oid, name=name, content=content)
                      for name, content in self.files]

    def get_payload(self):
        json = {
            'Task': self.task,
            'Title': self.title,
            'Text': self.text,
            'Files': [f.get_payload() for f in self.files]
        }
        if self.corr_id:
            json['CorrelationId'] = str(self.corr_id)
        return json


@dataclass
class InboxMessage(Message):
    meta: InitVar[dict]

    def __post_init__(self, meta):
        super().refill(meta)
        self.task = meta.get('TaskName')
        self.title = meta.get('Title')
        self.text = meta.get('Text')
        self.receipts = [Receipt(msg_id=self.oid, meta=rcpt)
                         for rcpt in meta['Receipts']]


@dataclass
class Receipt:
    msg_id: UUID
    meta: InitVar[dict]
    oid: UUID = field(init=False, default=None)
    receive_time: datetime = field(init=False, default=None)
    status_time: datetime = field(init=False, default=None)
    status: str = field(init=False, default=None)
    message: str = field(init=False, default=None)
    files: list = field(init=False, default_factory=list)

    def __post_init__(self, meta: dict):
        self.oid = str_to_uuid(meta['Id'])
        self.receive_time = str_to_date(meta['ReceiveTime'])
        self.status_time = str_to_date(meta['StatusTime'])
        self.status = meta['Status']
        self.message = meta['Message']
        self.files = [
            ReceiptFile(msg_id=self.msg_id, rcpt_id=self.oid, meta=item)
            for item in meta['Files']]


@dataclass
class File:
    msg_id: UUID
    name: str = field(init=False, default=None)
    content: bytes = field(init=False, default=None, repr=False)
    size: int = field(init=False, default=0)
    encrypted: bool = field(init=False, default=False)
    signed_file: str = field(init=False, default=None)
    description: str = field(init=False, default=None)
    oid: UUID = field(init=False, default=None)
    repository: list = field(init=False, default_factory=list)

    def refill(self, meta):
        self.name = meta.get('Name')
        self.size = meta.get('Size')
        self.encrypted = bool(meta.get('Encrypted'))
        self.signed_file = meta.get('SignedFile')
        self.description = meta.get('Description')
        self.oid = str_to_uuid(meta.get('Id'))
        self.repository = [Repository(item) for item in meta['RepositoryInfo']]

    @property
    def upload_url(self):
        return f'/messages/{self.msg_id}/files/{self.oid}'

    @property
    def session_url(self):
        return f'{self.upload_url}/createUploadSession'

    @property
    def download_url(self):
        return f'{self.upload_url}/download'


@dataclass
class DownloadFile(File):
    name: str = field(default=MISSING)
    content: bytes = field(default=MISSING, repr=False)

    def __post_init__(self):
        self.encrypted = self.name.endswith('.enc', -4)
        self.size = len(self.content)
        if self.name.endswith('.sig', -4):
            self.signed_file = self.name[:-6]

    def get_payload(self):
        json = {
            'Name': self.name,
            'Encrypted': int(self.encrypted),
            'SignedFile': self.signed_file,
            'RepositoryType': 'http',
            'Size': self.size
        }
        return json


@dataclass
class UploadFile(File):
    meta: InitVar[dict]

    def __post_init__(self, meta: dict):
        super().refill(meta)

    @property
    def upload_url(self):
        return None

    @property
    def session_url(self):
        return None


@dataclass
class ReceiptFile(File):
    rcpt_id: UUID
    meta: InitVar[dict]

    def __post_init__(self, meta: dict):
        super().refill(meta)

    @property
    def upload_url(self):
        return None

    @property
    def session_url(self):
        return None

    @property
    def download_url(self):
        return (f'/messages/{self.msg_id}/receipts/{self.rcpt_id}/files/'
                f'{self.oid}/download')


@dataclass
class Repository:
    meta: InitVar[dict]
    type: str = field(init=False, default=None)
    host: str = field(init=False, default=None)
    port: int = field(init=False, default=None)
    path: str = field(init=False, default=None)

    def __post_init__(self, meta: dict):
        self.type = meta.get('RepositoryType')
        self.host = meta.get('Host')
        self.port = meta.get('Port')
        self.path = meta.get('Path')


@dataclass
class Sender:
    meta: InitVar[dict]
    inn: str = field(init=False, default=None)
    ogrn: str = field(init=False, default=None)
    bik: str = field(init=False, default=None)
    regnum: str = field(init=False, default=None)
    division_code: str = field(init=False, default=None)

    def __post_init__(self, meta: dict):
        self.inn = meta.get('Inn')
        self.ogrn = meta.get('Ogrn')
        self.bik = meta.get('Bik')
        self.regnum = meta.get('RegNum')
        self.division_code = meta.get('DivisionCode')


@dataclass
class Task:
    meta: InitVar[dict]
    code: str = field(init=False)
    name: str = field(init=False)
    description: str = field(init=False)
    direction: str = field(init=False)
    allow_aspera: bool = field(init=False)
    allow_linked_messages: bool = field(init=False)

    def __post_init__(self, meta: dict):
        self.code = meta.get('Code')
        self.name = meta.get('Name')
        self.description = meta.get('Description')
        self.direction = meta.get('Direction')
        self.allow_aspera = meta.get('AllowAspera')
        self.allow_linked_messages = meta.get('AllowLinkedMessages')


@dataclass
class Profile:
    meta: InitVar[dict]
    short_name: str = field(init=False)
    full_name: str = field(init=False)
    activities: list = field(init=False)
    inn: str = field(init=False)
    ogrn: str = field(init=False)
    international_id: str = field(init=False)
    opf: str = field(init=False)
    email: str = field(init=False)
    address: str = field(init=False)
    phone: str = field(init=False)
    created: datetime = field(init=False)
    status: str = field(init=False)

    def __post_init__(self, meta: dict):
        self.short_name = meta.get('ShortName')
        self.full_name = meta.get('FullName')
        self.activities = self._get_activities(meta.get('Activities', {}))
        self.inn = meta.get('Inn')
        self.ogrn = meta.get('Ogrn')
        self.international_id = meta.get('InternationalId')
        self.opf = meta.get('Opf')
        self.email = meta.get('Email')
        self.address = meta.get('Address')
        self.phone = meta.get('Phone')
        self.created = str_to_date(meta.get('CreationDate'))
        self.status = meta.get('Status')

    @staticmethod
    def _get_activities(data):
        return [Activity(d) for d in data]


@dataclass
class Activity:
    meta: InitVar[dict]
    short_name: str = field(init=False)
    full_name: str = field(init=False)
    supervision_division: str = field(init=False)

    def __post_init__(self, meta: dict):
        self.short_name = meta.get('ShortName')
        self.full_name = meta.get('FullName')
        self.supervision_division = (meta.get('SupervisionDevision', {})
                                     .get('Name'))


@dataclass
class ProfileQuota:
    meta: InitVar[dict]
    total: int = field(init=False)
    used: int = field(init=False)
    msg_size: int = field(init=False)

    def __post_init__(self, meta: dict):
        self.total = meta.get('TotalQuota')
        self.used = meta.get('UsedQuota')
        self.msg_size = meta.get('MessageSize')
