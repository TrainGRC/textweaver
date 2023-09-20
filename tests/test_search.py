from fastapi.testclient import TestClient
from weaver.app import app
import os

client = TestClient(app)

def test_search_endpoint_status_code():
    response = client.get("/search/?query=test query&results_to_return=5", headers={"Authorization": f"Bearer {os.getenv('BEARER_TOKEN')}"})
    assert response.status_code == 200

def test_search_endpoint_time_elapsed():
    response = client.get("/search/?query=test query&results_to_return=5", headers={"Authorization": f"Bearer {os.getenv('BEARER_TOKEN')}"})
    assert "time_elapsed" in response.json()

def test_search_endpoint_results():
    response = client.get("/search/?query=test query&results_to_return=5", headers={"Authorization": f"Bearer {os.getenv('BEARER_TOKEN')}"})
    assert "results" in response.json()

def test_search_endpoint_invalid_query():
    response = client.get("/search/?query=&results_to_return=5", headers={"Authorization": f"Bearer {os.getenv('BEARER_TOKEN')}"})
    assert response.status_code == 422

def test_search_endpoint_invalid_results_to_return():
    response = client.get("/search/?query=test query&results_to_return=-1", headers={"Authorization": f"Bearer {os.getenv('BEARER_TOKEN')}"})
    assert response.status_code == 422

def test_search_endpoint_no_query():
    response = client.get("/search/?results_to_return=5", headers={"Authorization": f"Bearer {os.getenv('BEARER_TOKEN')}"})
    assert response.status_code == 422