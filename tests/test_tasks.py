from cbr_client import Task
from conftest import base_url, correct_headers, tasks_json


def test_tasks(httpx_mock, client):
    httpx_mock.add_response(status_code=200,
                            json=tasks_json,
                            headers={'Content-Type': 'application/json'},
                            method='GET',
                            url=f'{base_url}/back/rapi2/tasks',
                            match_headers=correct_headers)
    tasks = client.get_tasks()
    assert isinstance(tasks, list)
    assert isinstance(tasks[0], Task)
