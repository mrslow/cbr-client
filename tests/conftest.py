import pytest

from cbr_client import Client


@pytest.fixture
def client():
    c = Client(url='https://portal5test.cbr.ru/back/rapi2', login='test',
               password='123', user_agent='pytest')
    yield c
