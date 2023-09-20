from fastapi.testclient import TestClient
from weaver.app import app
import os
import io

client = TestClient(app)

def test_upload_endpoint():
    # Open a real file to upload
    with open('test_files/test_file.txt', 'rb') as f:
        file_content = f.read()

    test_file = {"file": ("test_file.txt", io.BytesIO(file_content))}
    test_data = {"file_type": "text"}  # Add this line

    response = client.post("/upload/", files=test_file, data=test_data, headers={"Authorization": f"Bearer {os.getenv('BEARER_TOKEN')}"})
    assert response.status_code == 200
    assert "doc_id" in response.json()
    assert "original_filename" in response.json()

def test_upload_endpoint_file_type_restriction():
    # Create a mock file of a disallowed type
    with open('test_files/test_file.txt', 'rb') as f:
        file_content = f.read()
    
    test_file = {"file": ("test_file.txt", io.BytesIO(file_content))}
    test_data = {"file_type": "exe"}  # Add this line

    response = client.post("/upload/", files=test_file, data=test_data, headers={"Authorization": f"Bearer {os.getenv('BEARER_TOKEN')}"})
    assert response.status_code == 400
    assert "detail" in response.json()

def test_upload_endpoint_file_size_limit():
    # Create a mock file that exceeds the size limit
    mock_file_content = b"Mock file content" * 10000000  # Adjust this value as needed
    mock_file = {"file": ("large_file.txt", mock_file_content)}

    response = client.post("/upload/", files=mock_file, headers={"Authorization": f"Bearer {os.getenv('BEARER_TOKEN')}"})
    assert response.status_code == 413
    assert "detail" in response.json()

def test_upload_endpoint_missing_file():
    response = client.post("/upload/", headers={"Authorization": f"Bearer {os.getenv('BEARER_TOKEN')}"})
    assert response.status_code == 422
    assert "detail" in response.json()