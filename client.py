import httpx
import logging

_BASE_URL = 'https://portal5test.cbr.ru/back/rapi2'

logger = logging.getLogger('cbr-client')
logger.setLevel('DEBUG')


class ClientException(Exception):
    pass


class Client:

    def __init__(self, login: str, password: str, user_agent: str = None):
        headers = {'Accept': 'application/json'}
        if user_agent:
            headers.update({'User-Agent': user_agent})
        if all((login, password)):
            self.client = httpx.Client(base_url=_BASE_URL,
                                       headers=headers,
                                       auth=(login, password))
        else:
            raise ClientException('Login and password are required')

    def get_profile(self):
        return self._request('GET', '/profile')

    def get_profile_quota(self):
        return self._request('GET', '/profile/quota')

    def get_dictionaries(self):
        return self._request('GET', '/dictionaries')

    def get_dictionary(self, oid):
        return self._request('GET', f'/dictionaries/{oid}')

    def _request(self, method, url, **kwargs):
        resp = self.client.request(method, url, **kwargs)
        logger.debug(f'{method} {url} {resp.status_code}')
        try:
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise ClientException(str(exc))
