import json
import pytest

from cbr_client import Client

base_headers = {'Accept': 'application/json', 'User-Agent': 'pytest'}
base_url = 'https://portal5test.cbr.ru'

correct_headers = {'Authorization': 'Basic dGVzdDoxMjM='}
correct_headers.update(base_headers)
wrong_headers = {'Authorization': 'Basic dGVzdDI6MzIx'}
wrong_headers.update(base_headers)

tasks_json = json.loads(open('./tests/data/tasks.json').read())
profile_json = json.loads(open('./tests/data/profile.json').read())
quota_json = json.loads(open('./tests/data/quota.json').read())
dictionaries_json = json.loads(open('./tests/data/dictionaries.json').read())
dictionary_json = json.loads(open('./tests/data/dictionary.json').read())
messages_json = json.loads(open('./tests/data/messages.json').read())
receipts_json = json.loads(open('./tests/data/receipts.json').read())


@pytest.fixture
def client():
    c = Client(url=base_url, login='test', password='123', user_agent='pytest')
    yield c


@pytest.fixture
def invalid_client():
    c = Client(url=base_url, login='test2', password='321',
               user_agent='pytest')
    yield c
