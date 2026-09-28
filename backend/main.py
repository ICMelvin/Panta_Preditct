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
from pathlib import Path
import logging

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from backend.models import BuildRequest, QuoteRequest, RegisterRequest
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


@app.post("/api/quality-check")
def quality_check(payload: QuoteRequest):
    # Handle sources_of_truth array - take first source for quality check
    source_field = payload.sources_of_truth[0] if payload.sources_of_truth and len(payload.sources_of_truth) > 0 else None
    result = run_quality_gate(payload.question, source_field=source_field)
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


# Serve the Mini App static files at / (mounted AFTER all /api routes to prevent shadowing)
if os.path.isdir("miniapp"):
    app.mount("/", StaticFiles(directory="miniapp", html=True), name="miniapp")
