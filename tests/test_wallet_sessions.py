"""Tests for wallet session endpoints."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from backend.main import app
import pytest
import nacl.encoding
import nacl.public
import json
import nacl.utils
import base58

client = TestClient(app)


def test_wallet_session_init():
    """Test wallet session initialization with both public and secret keys."""
    response = client.post("/api/wallet-session-init", json={
        "dapp_encryption_public_key": "test_public_key_123",
        "dapp_secret_key": "test_secret_key_456"
    })
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 0


def test_wallet_session_retrieval():
    """Test wallet session retrieval."""
    # First create a session with both keys
    init_response = client.post("/api/wallet-session-init", json={
        "dapp_encryption_public_key": "test_public_key_456",
        "dapp_secret_key": "test_secret_key_789"
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
        "dapp_encryption_public_key": "test_public_key_789",
        "dapp_secret_key": "test_secret_key_abc"
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


def test_wallet_decryption_integration():
    """Test full wallet decryption flow with mock Phantom response."""
    # Create ephemeral keypair
    dapp_keypair = nacl.public.PrivateKey.generate()
    dapp_public_key = base58.b58encode(dapp_keypair.encode()).decode('utf-8')
    dapp_secret_key = base58.b58encode(dapp_keypair.encode()).decode('utf-8')
    
    # Create Phantom keypair
    phantom_keypair = nacl.public.PrivateKey.generate()
    phantom_public_key = base58.b58encode(phantom_keypair.public_key.encode()).decode('utf-8')
    
    # Create Box for encryption (using dapp private key and phantom public key)
    encrypt_box = nacl.public.Box(dapp_keypair, phantom_keypair.public_key)
    
    # Mock wallet data to encrypt
    wallet_data = {"public_key": "TestWalletPublicKey123", "session": "test_session_token"}
    wallet_data_json = json.dumps(wallet_data).encode('utf-8')
    
    # Encrypt the data
    encrypted_data = encrypt_box.encrypt(wallet_data_json)
    
    # Extract nonce (first 24 bytes) and actual encrypted data
    nonce = encrypted_data[:24]
    data = encrypted_data[24:]
    
    # Encode in base58
    nonce_b58 = base58.b58encode(nonce).decode('utf-8')
    data_b58 = base58.b58encode(data).decode('utf-8')
    
    # Initialize session
    init_response = client.post("/api/wallet-session-init", json={
        "dapp_encryption_public_key": dapp_public_key,
        "dapp_secret_key": dapp_secret_key
    })
    session_id = init_response.json()["session_id"]
    
    # Simulate Phantom callback with encrypted data
    callback_response = client.get(f"/wallet-callback?session_id={session_id}&phantom_encryption_public_key={phantom_public_key}&data={data_b58}&nonce={nonce_b58}")
    assert callback_response.status_code == 200
    # The HTML truncates the wallet address for display, so check for partial
    assert "TestWalletPublicKey1" in callback_response.text
    assert "icKey123" in callback_response.text
    
    # Verify wallet address was stored correctly (this is the real check)
    session_response = client.get(f"/api/wallet-session/{session_id}")
    session_data = session_response.json()
    assert session_data["wallet_address"] == "TestWalletPublicKey123"
    
    # CRITICAL: Verify wallet address is NOT the phantom_encryption_public_key
    # This proves we're extracting the real wallet address, not the encryption key
    assert session_data["wallet_address"] != phantom_public_key
    assert session_data["wallet_address"] == "TestWalletPublicKey123"
