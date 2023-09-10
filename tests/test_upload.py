from fastapi.testclient import TestClient
from weaver.app import app

client = TestClient(app)

def test_upload_endpoint():
    # Create a mock file to upload
    mock_file_content = b"Mock file content"
    mock_file = {"file": ("mock_file.txt", mock_file_content)}

    response = client.post("/upload/", files=mock_file)
    assert response.status_code == 200
    assert "file_id" in response.json()

def test_upload_endpoint_file_type_restriction():
    # Create a mock file of a disallowed type
    mock_file_content = b"Mock file content"
    mock_file = {"file": ("mock_file.exe", mock_file_content)}

    response = client.post("/upload/", files=mock_file)
    assert response.status_code == 400
    assert "error" in response.json()

def test_upload_endpoint_file_size_limit():
    # Create a mock file that exceeds the size limit
    mock_file_content = b"Mock file content" * 1000000  # Adjust this value as needed
    mock_file = {"file": ("large_file.txt", mock_file_content)}

    response = client.post("/upload/", files=mock_file)
    assert response.status_code == 413
    assert "error" in response.json()

def test_upload_endpoint_missing_file():
    response = client.post("/upload/")
    assert response.status_code == 400
    assert "error" in response.json()