def test_health_check_returns_200(client):
    """Test that the health endpoint returns 200 and expected payload structure."""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "AICTE Security Deposit / FDR Management Portal"
    assert data["version"] == "1.0.0"
    assert data["database"] == "connected"


def test_404_json_error_handler(client):
    """Test that requesting an undefined route returns a clean JSON 404 response."""
    response = client.get("/api/non-existent-endpoint")

    assert response.status_code == 404
    assert response.is_json
    data = response.get_json()
    assert data["error"] == "Resource not found"
    assert data["status_code"] == 404
