
"""
Layer 4 — FastAPI backend.

Exposes the quality gate and Panta create-flow to the Mini App (and to the
bot, if it ends up calling HTTP instead of importing directly). Never
handles or stores a private key — signing happens client-side in the
Mini App; this backend only builds unsigned transactions and forwards
signed ones to Panta.
"""

from __future__ import annotations

import os
import uuid
import time
import json
from pathlib import Path
import logging
from typing import Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend.models import BuildRequest, QualityCheckRequest, QuoteRequest, RegisterRequest
from backend.panta_client import PantaAPIError, PantaClient
from backend.quality_gate import run_quality_gate

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables with override=True to win over stale shell variables
# In production (Render), environment variables come from the platform, not from .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    logger.info(f"Loaded .env from: {env_path}")
else:
    logger.info("Using environment variables from platform (no .env file)")

app = FastAPI(title="PantaPredict API")

_panta = PantaClient()  # reads PANTA_API_KEY from env

# In-memory wallet session storage
# HACKATHON LIMITATION: This is in-memory and not persistent. Sessions expire after 10 minutes.
# In production, this should use Redis or a database with proper persistence.
wallet_sessions: Dict[str, dict] = {}
SESSION_EXPIRY_SECONDS = 600  # 10 minutes

# PyNaCl for encryption/decryption
import nacl.encoding
import nacl.public
import base58

# Clean up expired sessions periodically
def cleanup_expired_sessions():
    current_time = time.time()
    expired_sessions = [
        session_id for session_id, session_data in wallet_sessions.items()
        if current_time - session_data.get('created_at', 0) > SESSION_EXPIRY_SECONDS
    ]
    for session_id in expired_sessions:
        del wallet_sessions[session_id]
        logger.info(f"Cleaned up expired session: {session_id}")

# Pydantic models for wallet session
class WalletSessionInit(BaseModel):
    dapp_encryption_public_key: str
    # NOTE: dapp_secret_key must be 32 bytes (PyNaCl format), not 64 bytes (Solana format)
    # The frontend should slice Solana's secretKey (64 bytes) to first 32 bytes before encoding
    dapp_secret_key: str


@app.post("/api/quality-check")
def quality_check(payload: QualityCheckRequest):
    # Handle sources_of_truth array - take first source for quality check
    result = run_quality_gate(payload.question, source_field=payload.source)
    return result.to_dict()


@app.post("/api/quote")
def quote(payload: QuoteRequest):
    gate = run_quality_gate(payload.question, source_field=payload.sources_of_truth[0] if payload.sources_of_truth else None)
    if not gate.passed:
        # Don't spend a Panta quote call on a question that will just need
        # to be re-submitted — surface the gate failures first.
        raise HTTPException(status_code=422, detail=gate.to_dict())

    try:
        quote_result = _panta.quote_market(
            question=payload.question,
            resolution_rule=payload.resolution_rule,
            sources_of_truth=payload.sources_of_truth,
            description=payload.description or "",
            image_url=payload.image_url,
            category=payload.category,
            start_time=payload.start_time,
            end_time=payload.end_time,
            resolution_time=payload.resolution_time,
        )
    except PantaAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    return quote_result.raw


@app.post("/api/build")
def build(payload: BuildRequest):
    try:
        result = _panta.build_market(
            create_id=payload.create_id,
            wallet=payload.wallet,
        )
        logger.info(f"RAW Panta build response: {result}")
    except PantaAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return result


@app.post("/api/register")
def register(payload: RegisterRequest):
    try:
        result = _panta.register_market(
            create_id=payload.create_id,
            signature=payload.signature,
        )
    except PantaAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return result


@app.get("/api/markets/{market_id}")
def get_market(market_id: str):
    try:
        return _panta.get_market(market_id)
    except PantaAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@app.get("/api/categories")
def get_categories():
    try:
        return _panta.get_categories()
    except PantaAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@app.get("/healthz")
def healthz():
    """Health check endpoint."""
    api_key = os.getenv("PANTA_API_KEY", "")
    mode = "sandbox" if api_key.startswith("pk_test_") else "live" if api_key.startswith("pk_live_") else "unknown"
    return {"ok": True, "mode": mode}


@app.post("/api/wallet-session-init")
def init_wallet_session(payload: WalletSessionInit):
    """Initialize a wallet connection session and store the ephemeral keypair."""
    cleanup_expired_sessions()
    
    # Validate secret key length (must be 32 bytes for PyNaCl, not 64 bytes like Solana)
    try:
        decoded_secret = base58.b58decode(payload.dapp_secret_key)
        if len(decoded_secret) != 32:
            raise HTTPException(
                status_code=400, 
                detail=f"dapp_secret_key must be 32 bytes (got {len(decoded_secret)} bytes). If using Solana keypair, slice secretKey to first 32 bytes."
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid dapp_secret_key encoding: {str(e)}")
    
    session_id = str(uuid.uuid4())
    wallet_sessions[session_id] = {
        "dapp_encryption_public_key": payload.dapp_encryption_public_key,
        "dapp_secret_key": payload.dapp_secret_key,  # Store for decryption
        "created_at": time.time(),
        "wallet_address": None,
        "session_token": None
    }
    
    logger.info(f"Initialized wallet session: {session_id}")
    return {"session_id": session_id}


@app.post("/api/wallet-callback-simulated")
def wallet_callback_simulated(payload: dict):
    """Simulated callback for testing - stores the actual wallet address."""
    cleanup_expired_sessions()
    
    session_id = payload.get("session_id")
    wallet_address = payload.get("wallet_address")
    
    if not session_id or not wallet_address:
        raise HTTPException(status_code=400, detail="Missing session_id or wallet_address")
    
    session = wallet_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    session["wallet_address"] = wallet_address
    logger.info(f"Simulated wallet connection for session {session_id}: {wallet_address}")
    
    return {"status": "success", "session_id": session_id}


@app.get("/api/wallet-session/{session_id}")
def get_wallet_session(session_id: str):
    """Retrieve wallet session data."""
    cleanup_expired_sessions()
    
    session = wallet_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    return {
        "session_id": session_id,
        "wallet_address": session.get("wallet_address"),
        "created_at": session.get("created_at"),
        "expired": (time.time() - session.get("created_at", 0)) > SESSION_EXPIRY_SECONDS
    }


@app.get("/wallet-callback", response_class=HTMLResponse)
def wallet_callback_page(session_id: str = None, phantom_encryption_public_key: str = None, data: str = None, nonce: str = None):
    """Process Phantom wallet connection callback with real decryption."""
    bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "PantaPredictBot")
    
    wallet_address = None
    error_message = None
    
    if session_id and phantom_encryption_public_key and data and nonce:
        try:
            session = wallet_sessions.get(session_id)
            if not session:
                error_message = "Session not found or expired"
            else:
                # Decode base58 encoded values
                phantom_public_key_bytes = base58.b58decode(phantom_encryption_public_key)
                nonce_bytes = base58.b58decode(nonce)
                data_bytes = base58.b58decode(data)
                
                # Decode dapp secret key from base58
                dapp_secret_key_bytes = base58.b58decode(session["dapp_secret_key"])
                
                # Reconstruct keypair for decryption
                dapp_keypair = nacl.public.PrivateKey(dapp_secret_key_bytes)
                phantom_public_key = nacl.public.PublicKey(phantom_public_key_bytes)
                
                # Create Box for decryption (using dapp private key and phantom public key)
                decrypt_box = nacl.public.Box(dapp_keypair, phantom_public_key)
                
                # Decrypt the data using the box
                decrypted_data = decrypt_box.decrypt(data_bytes, nonce_bytes)
                
                if not decrypted_data:
                    error_message = "Failed to decrypt wallet data"
                else:
                    # Parse decrypted JSON
                    decrypted_json = json.loads(decrypted_data.decode('utf-8'))
                    
                    # Extract the user's public key (wallet address)
                    wallet_address = decrypted_json.get("public_key")
                    session_token = decrypted_json.get("session")
                    
                    # Store in session
                    session["wallet_address"] = wallet_address
                    session["session_token"] = session_token
                    session["phantom_encryption_public_key"] = phantom_encryption_public_key
                    
                    logger.info(f"Successfully decrypted wallet connection for session {session_id}: {wallet_address}")
                    
        except Exception as e:
            logger.error(f"Error processing wallet callback: {e}")
            error_message = f"Error processing wallet connection: {str(e)}"
    
    # Use session_id from query params for the return link
    return_link = f"https://t.me/{bot_username}/PPB"
    if session_id:
        return_link = f"https://t.me/{bot_username}/PPB?startapp={session_id}"
    
    status_text = "Wallet Connected!" if wallet_address else "Connection Failed"
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Wallet Connected</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0a0a0f;
                color: #f0f0f5;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                text-align: center;
                max-width: 400px;
            }}
            h1 {{
                color: #7A8BA0;
                margin-bottom: 20px;
            }}
            p {{
                color: #a1a1aa;
                margin-bottom: 30px;
                line-height: 1.6;
            }}
            .error {{
                color: #f43f5e;
                margin-bottom: 20px;
            }}
            .wallet-info {{
                background: #1a1a24;
                border: 1px solid #2a2a3a;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 20px;
                font-family: monospace;
                font-size: 12px;
                word-break: break-all;
            }}
            .btn {{
                display: inline-block;
                background: linear-gradient(135deg, #7A8BA0, #A0785C);
                color: white;
                padding: 16px 32px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 600;
                transition: transform 0.2s;
            }}
            .btn:hover {{
                transform: translateY(-2px);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>✅ {status_text}</h1>
            <p>Your Phantom wallet has been successfully connected. Tap below to return to Telegram and continue creating your prediction market.</p>
            {'<div class="error">' + error_message + '</div>' if error_message else ''}
            {'<div class="wallet-info">Wallet: ' + wallet_address[:20] + '...' + wallet_address[-8:] + '</div>' if wallet_address else ''}
            <a href="{return_link}" class="btn">Return to Telegram</a>
        </div>
    </body>
    </html>
    """


# Serve the Mini App static files at / (mounted AFTER all /api routes to prevent shadowing)
if os.path.isdir("miniapp"):
    app.mount("/", StaticFiles(directory="miniapp", html=True), name="miniapp")
