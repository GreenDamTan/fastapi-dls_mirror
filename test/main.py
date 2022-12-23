from starlette.testclient import TestClient
import importlib.util
import sys

MODULE, PATH = 'main.app', '../app/main.py'

spec = importlib.util.spec_from_file_location(MODULE, PATH)
main = importlib.util.module_from_spec(spec)
sys.modules[MODULE] = main
spec.loader.exec_module(main)

client = TestClient(main.app)


def test_index():
    response = client.get('/')
    assert response.status_code == 200


def test_status():
    response = client.get('/status')
    assert response.status_code == 200
    assert response.json()['status'] == 'up'
