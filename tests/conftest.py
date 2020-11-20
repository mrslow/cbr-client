import pytest

from client import Client


@pytest.fixture
def client():
    c = Client(login='test', password='123', user_agent='pytest')
    yield c
