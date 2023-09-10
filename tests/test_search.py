from fastapi.testclient import TestClient
from weaver.app import app

client = TestClient(app)

def test_search_endpoint_status_code():
    response = client.post("/search/", json={"query": "test query", "results_to_return": 5})
    assert response.status_code == 200

def test_search_endpoint_time_elapsed():
    response = client.post("/search/", json={"query": "test query", "results_to_return": 5})
    assert "time_elapsed" in response.json()

def test_search_endpoint_results():
    response = client.post("/search/", json={"query": "test query", "results_to_return": 5})
    assert "results" in response.json()

def test_search_endpoint_invalid_query():
    response = client.post("/search/", json={"query": "", "results_to_return": 5})
    assert response.status_code == 422

def test_search_endpoint_invalid_results_to_return():
    response = client.post("/search/", json={"query": "test query", "results_to_return": -1})
    assert response.status_code == 422

def test_search_endpoint_no_query():
    response = client.post("/search/", json={"results_to_return": 5})
    assert response.status_code == 422

def test_search_endpoint_no_results_to_return():
    response = client.post("/search/", json={"query": "test query"})
    assert response.status_code == 422