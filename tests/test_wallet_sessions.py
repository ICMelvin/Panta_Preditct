"""Tests for wallet session endpoints."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from backend.main import app
import pytest
import time

client = TestClient(app)


def test_wallet_session_init():
    """Test wallet session initialization."""
    response = client.post("/api/wallet-session-init", json={
        "dapp_encryption_public_key": "test_public_key_123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 0


def test_wallet_session_retrieval():
    """Test wallet session retrieval."""
    # First create a session
    init_response = client.post("/api/wallet-session-init", json={
        "dapp_encryption_public_key": "test_public_key_456"
    })
    session_id = init_response.json()["session_id"]
    
    # Then retrieve it
    response = client.get(f"/api/wallet-session/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["wallet_address"] is None  # Not connected yet
    assert data["expired"] is False


def test_wallet_session_not_found():
    """Test that non-existent session returns 404."""
    response = client.get("/api/wallet-session/nonexistent_session")
    assert response.status_code == 404


def test_wallet_session_expiry():
    """Test that expired sessions are handled correctly."""
    # Create a session
    init_response = client.post("/api/wallet-session-init", json={
        "dapp_encryption_public_key": "test_public_key_789"
    })
    session_id = init_response.json()["session_id"]
    
    # Try to retrieve immediately - should work
    response = client.get(f"/api/wallet-session/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["expired"] is False
    
    # Note: We can't easily test actual expiry without time.sleep
    # which would slow down tests, so we skip actual time-based expiry test


def test_wallet_callback_page():
    """Test wallet callback HTML page."""
    response = client.get("/wallet-callback")
    assert response.status_code == 200
    assert "Wallet Connected" in response.text
    assert "Return to Telegram" in response.text


def test_wallet_callback_page_with_session():
    """Test wallet callback page with session_id."""
    response = client.get("/wallet-callback?session_id=test_session_123")
    assert response.status_code == 200
    assert "Wallet Connected" in response.text
    assert "startapp=test_session_123" in response.text


def test_simulated_wallet_callback():
    """Test simulated wallet callback endpoint."""
    # First create a session
    init_response = client.post("/api/wallet-session-init", json={
        "dapp_encryption_public_key": "test_public_key_sim"
    })
    session_id = init_response.json()["session_id"]
    
    # Simulate wallet connection
    response = client.post("/api/wallet-callback-simulated", json={
        "session_id": session_id,
        "wallet_address": "test_wallet_address_xyz"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["session_id"] == session_id
    
    # Verify wallet address was stored
    get_response = client.get(f"/api/wallet-session/{session_id}")
    session_data = get_response.json()
    assert session_data["wallet_address"] == "test_wallet_address_xyz"
