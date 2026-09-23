"""
Tests for Layer 4 - FastAPI backend.

Tests the REST API endpoints that expose quality gate and Panta client functionality.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app, _get_panta_client


@pytest.fixture(autouse=True)
def setup_env():
    """Set up environment variables for tests."""
    os.environ["PANTA_API_KEY"] = "pk_test_dummy_key"
    yield
    os.environ.pop("PANTA_API_KEY", None)


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_quality_check_passing(client):
    """Test quality check endpoint with a good question."""
    response = client.post(
        "/api/quality-check",
        json={
            "question": "Will Bitcoin reach $100k by 2026-12-31? per CoinDesk",
            "source": "https://coindesk.com"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is True
    assert "checks" in data
    assert data["checks"]["deadline"]["passed"] is True
    assert data["checks"]["source"]["passed"] is True
    assert data["checks"]["binary"]["passed"] is True


def test_quality_check_failing(client):
    """Test quality check endpoint with a bad question."""
    response = client.post(
        "/api/quality-check",
        json={
            "question": "Bitcoin might go up",  # No deadline, no source, not yes/no
            "source": None
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is False
    assert data["checks"]["deadline"]["passed"] is False
    assert data["checks"]["source"]["passed"] is False
    assert data["checks"]["binary"]["passed"] is False


def test_quote_with_good_question(client):
    """Test quote endpoint with a question that passes quality gate."""
    with patch('backend.main._get_panta_client') as mock_get_client:
        mock_panta = MagicMock()
        mock_quote = MagicMock()
        mock_quote.raw = {
            "quoteId": "q_test_123",
            "feeUsdc": 40
        }
        mock_panta.quote_market.return_value = mock_quote
        mock_get_client.return_value = mock_panta
        
        response = client.post(
            "/api/quote",
            json={
                "question": "Will Bitcoin reach $100k by 2026-12-31? per CoinDesk",
                "source": "https://coindesk.com",
                "deadline": "2026-12-31T23:59:59Z"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["quoteId"] == "q_test_123"
        assert data["feeUsdc"] == 40


def test_quote_with_bad_question(client):
    """Test quote endpoint rejects questions that fail quality gate."""
    response = client.post(
        "/api/quote",
        json={
            "question": "Bitcoin might go up",
            "source": None,
            "deadline": None
        }
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert data["detail"]["passed"] is False


def test_build_endpoint(client):
    """Test build endpoint creates unsigned transaction."""
    with patch('backend.main._get_panta_client') as mock_get_client:
        mock_panta = MagicMock()
        mock_panta.build_market.return_value = {
            "buildId": "b_test_456",
            "transaction": "base64_encoded_tx"
        }
        mock_get_client.return_value = mock_panta
        
        response = client.post(
            "/api/build",
            json={
                "quote_id": "q_test_123",
                "creator_wallet": "test_wallet_address"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["buildId"] == "b_test_456"
        assert "transaction" in data


def test_register_endpoint(client):
    """Test register endpoint submits signed transaction."""
    with patch('backend.main._get_panta_client') as mock_get_client:
        mock_panta = MagicMock()
        mock_panta.register_market.return_value = {
            "marketId": "m_test_789",
            "status": "registered"
        }
        mock_get_client.return_value = mock_panta
        
        response = client.post(
            "/api/register",
            json={
                "build_id": "b_test_456",
                "signed_transaction": "signed_base64_tx"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["marketId"] == "m_test_789"
        assert data["status"] == "registered"


def test_get_market_endpoint(client):
    """Test get market endpoint retrieves market data."""
    with patch('backend.main._get_panta_client') as mock_get_client:
        mock_panta = MagicMock()
        mock_panta.get_market.return_value = {
            "marketId": "m_test_789",
            "question": "Will Bitcoin reach $100k?",
            "yesPrice": 0.65
        }
        mock_get_client.return_value = mock_panta
        
        response = client.get("/api/markets/m_test_789")
        assert response.status_code == 200
        data = response.json()
        assert data["marketId"] == "m_test_789"
        assert data["yesPrice"] == 0.65


def test_quote_handles_panta_api_error(client):
    """Test quote endpoint handles Panta API errors."""
    from backend.panta_client import PantaAPIError
    
    with patch('backend.main._get_panta_client') as mock_get_client:
        mock_panta = MagicMock()
        mock_panta.quote_market.side_effect = PantaAPIError(400, {"detail": "Invalid image URL"})
        mock_get_client.return_value = mock_panta
        
        response = client.post(
            "/api/quote",
            json={
                "question": "Will Bitcoin reach $100k by 2026-12-31? per CoinDesk",
                "source": "https://coindesk.com",
                "deadline": "2026-12-31T23:59:59Z"
            }
        )
        assert response.status_code == 400


def test_build_handles_panta_api_error(client):
    """Test build endpoint handles Panta API errors."""
    from backend.panta_client import PantaAPIError
    
    with patch('backend.main._get_panta_client') as mock_get_client:
        mock_panta = MagicMock()
        mock_panta.build_market.side_effect = PantaAPIError(404, {"detail": "Quote not found"})
        mock_get_client.return_value = mock_panta
        
        response = client.post(
            "/api/build",
            json={
                "quote_id": "invalid_quote",
                "creator_wallet": "test_wallet"
            }
        )
        assert response.status_code == 404


def test_register_handles_panta_api_error(client):
    """Test register endpoint handles Panta API errors."""
    from backend.panta_client import PantaAPIError
    
    with patch('backend.main._get_panta_client') as mock_get_client:
        mock_panta = MagicMock()
        mock_panta.register_market.side_effect = PantaAPIError(400, {"detail": "Invalid signature"})
        mock_get_client.return_value = mock_panta
        
        response = client.post(
            "/api/register",
            json={
                "build_id": "b_test_456",
                "signed_transaction": "invalid_signature"
            }
        )
        assert response.status_code == 400


def test_get_market_handles_panta_api_error(client):
    """Test get market endpoint handles Panta API errors."""
    from backend.panta_client import PantaAPIError
    
    with patch('backend.main._get_panta_client') as mock_get_client:
        mock_panta = MagicMock()
        mock_panta.get_market.side_effect = PantaAPIError(404, {"detail": "Market not found"})
        mock_get_client.return_value = mock_panta
        
        response = client.get("/api/markets/nonexistent")
        assert response.status_code == 404


def test_quote_with_optional_fields(client):
    """Test quote endpoint with optional fields."""
    with patch('backend.main._get_panta_client') as mock_get_client:
        mock_panta = MagicMock()
        mock_quote = MagicMock()
        mock_quote.raw = {
            "quoteId": "q_test_456",
            "feeUsdc": 50
        }
        mock_panta.quote_market.return_value = mock_quote
        mock_get_client.return_value = mock_panta
        
        response = client.post(
            "/api/quote",
            json={
                "question": "Will Ethereum reach $10k by 2027-12-31? per official data",
                "source": "https://ethereum.org",
                "deadline": "2027-12-31T23:59:59Z",
                "description": "Additional context",
                "image_url": "https://example.com/image.jpg",
                "category": "crypto"
            }
        )
        assert response.status_code == 200
        
        # Verify all optional fields were passed to the client
        call_args = mock_panta.quote_market.call_args
        assert call_args.kwargs["description"] == "Additional context"
        assert call_args.kwargs["image_url"] == "https://example.com/image.jpg"
        assert call_args.kwargs["category"] == "crypto"


def test_quality_check_with_source_field(client):
    """Test quality check when source is provided as a separate field."""
    response = client.post(
        "/api/quality-check",
        json={
            "question": "Will X happen by Friday?",
            "source": "https://example.com"
        }
    )
    assert response.status_code == 200
    data = response.json()
    # Source field should satisfy the source check even if not in question text
    assert data["checks"]["source"]["passed"] is True
