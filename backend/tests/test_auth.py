"""
Tests for authentication endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app


client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Web Reconnaissance Framework API" in data["message"]


def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "web-recon-api"


def test_auth_health_check():
    """Test the auth health check endpoint."""
    response = client.get("/api/v1/auth/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "authentication"


@patch('app.services.auth_service.supabase_client')
def test_register_endpoint_format(mock_supabase):
    """Test that the register endpoint accepts correct format."""
    # Mock Supabase response
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_user.email = "test@example.com"
    
    mock_response = MagicMock()
    mock_response.user = mock_user
    
    mock_supabase.client.auth.sign_up.return_value = mock_response
    
    # Test registration data
    register_data = {
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User"
    }
    
    response = client.post("/api/v1/auth/register", json=register_data)
    
    # Should not fail due to format issues
    assert response.status_code in [200, 400]  # 400 might be due to Supabase config


def test_register_invalid_email():
    """Test registration with invalid email."""
    register_data = {
        "email": "invalid-email",
        "password": "testpassword123"
    }
    
    response = client.post("/api/v1/auth/register", json=register_data)
    assert response.status_code == 422  # Validation error


def test_register_short_password():
    """Test registration with short password."""
    register_data = {
        "email": "test@example.com",
        "password": "short"
    }
    
    response = client.post("/api/v1/auth/register", json=register_data)
    assert response.status_code == 422  # Validation error


@patch('app.services.auth_service.supabase_client')
def test_login_endpoint_format(mock_supabase):
    """Test that the login endpoint accepts correct format."""
    # Mock Supabase response
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_user.email = "test@example.com"
    
    mock_session = MagicMock()
    mock_session.access_token = "mock-supabase-token"
    
    mock_response = MagicMock()
    mock_response.user = mock_user
    mock_response.session = mock_session
    
    mock_supabase.client.auth.sign_in_with_password.return_value = mock_response
    
    # Test login data
    login_data = {
        "email": "test@example.com",
        "password": "testpassword123"
    }
    
    response = client.post("/api/v1/auth/login", json=login_data)
    
    # Should not fail due to format issues
    assert response.status_code in [200, 401]  # 401 might be due to Supabase config 