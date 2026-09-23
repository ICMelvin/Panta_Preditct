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

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from backend.models import BuildRequest, QuoteRequest, RegisterRequest
from backend.panta_client import PantaAPIError, PantaClient
from backend.quality_gate import run_quality_gate

load_dotenv()

app = FastAPI(title="PantaPredict API")

# Lazy initialization of PantaClient to avoid import-time errors
_panta = None


def _get_panta_client():
    """Get or create the PantaClient instance."""
    global _panta
    if _panta is None:
        _panta = PantaClient()
    return _panta


@app.post("/api/quality-check")
def quality_check(payload: QuoteRequest):
    result = run_quality_gate(payload.question, source_field=payload.source)
    return result.to_dict()


@app.post("/api/quote")
def quote(payload: QuoteRequest):
    gate = run_quality_gate(payload.question, source_field=payload.source)
    if not gate.passed:
        # Don't spend a Panta quote call on a question that will just need
        # to be re-submitted — surface the gate failures first.
        raise HTTPException(status_code=422, detail=gate.to_dict())

    try:
        panta = _get_panta_client()
        quote_result = panta.quote_market(
            question=payload.question,
            deadline=payload.deadline or "",
            source=payload.source or "",
            description=payload.description or "",
            image_url=payload.image_url,
            category=payload.category,
        )
    except PantaAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    return quote_result.raw


@app.post("/api/build")
def build(payload: BuildRequest):
    # NOTE: in the real flow you'd look up the stored quote by quote_id
    # rather than re-wrapping it here. Wire this up once quoting is solid.
    from backend.panta_client import MarketQuote

    try:
        panta = _get_panta_client()
        result = panta.build_market(
            quote=MarketQuote(raw={"quoteId": payload.quote_id}),
            creator_wallet=payload.creator_wallet,
        )
    except PantaAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return result


@app.post("/api/register")
def register(payload: RegisterRequest):
    try:
        panta = _get_panta_client()
        result = panta.register_market(
            build_id=payload.build_id,
            signed_tx=payload.signed_transaction,
        )
    except PantaAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return result


@app.get("/api/markets/{market_id}")
def get_market(market_id: str):
    try:
        panta = _get_panta_client()
        return panta.get_market(market_id)
    except PantaAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# Serve the Mini App static files at /
if os.path.isdir("miniapp"):
    app.mount("/", StaticFiles(directory="miniapp", html=True), name="miniapp")
