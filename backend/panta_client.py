"""
Layer 1 — Panta API client.

Thin wrapper around https://live-api.panta.market/api/v1.

Known quirks to handle (confirm/adjust against the live API as you test):
- GET /markets/ requires the trailing slash.
- Price fields (yesPrice / primaryYesPrice / secondaryYesPrice) can come
  back as null — that means "no live price yet", NOT 0%.
- Timestamps are unix seconds (not ISO strings).
- Image URLs are validated at both the quote and build steps; not every
  public image host is accepted.
- API key creation requires an "env" field in the JSON body ("test" or "live").
- Register endpoint is /markets/register/ (not /markets/create/register/).

CONFIRMED ENDPOINT PATHS (verified against live API):
- POST /markets/create/quote/ — returns {"createId": "...", "paymentUsdc": "...", ...}
- POST /markets/create/build/ — returns {"transaction": "...", "buildFingerprint": "...", ...}
- POST /markets/register/ — returns {"status": "registered", "marketId": "...", ...}

REAL RESPONSE SHAPES (from live API calls):
Quote response:
{
  "createId": "cr_sandbox_test",
  "userId": "usr_...",
  "apiKeyId": "key_...",
  "expectedEventPda": "TestMarket...",
  "paymentUsdc": "50000000",
  "liquidityInjectionUsdc": "10000000",
  "platformRevenueUsdc": "40000000",
  "marketType": "standard",
  "expiresAt": "2099-01-01T00:00:00Z",
  "blockhashExpiryHintSec": 60,
  "disclaimer": "Test mode: this response uses sandbox fixtures..."
}

Build response:
{
  "transaction": "",
  "buildFingerprint": "sandbox",
  "expectedEventPda": "TestMarket...",
  "recentBlockhash": "SandboxBlockhash...",
  "lastValidBlockHeight": 0,
  "expiresAt": "2099-01-01T00:00:00Z",
  "disclaimer": "Test mode: this response uses sandbox fixtures..."
}

Register response:
{
  "status": "registered",
  "marketId": "TestMarket...",
  "createId": "cr_sandbox_test",
  "signature": "sandboxSignature...",
  "paymentUsdc": "50.00",
  "paymentUsdcBase": "50000000",
  "category": "crypto",
  "title": "Sandbox test market",
  "images": [],
  "disclaimer": "Test mode: this response uses sandbox fixtures..."
}
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx

DEFAULT_BASE_URL = "https://live-api.panta.market/api/v1"


class PantaAPIError(Exception):
    """Raised when Panta's API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Panta API error {status_code}: {detail}")


@dataclass
class MarketQuote:
    raw: dict
    # TODO: once you've seen a real quote response, promote the fields you
    # actually use (fees, expected liquidity, etc.) to typed attributes
    # instead of reading `raw` everywhere.


class PantaClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 15.0,
    ):
        self.api_key = api_key or os.getenv("PANTA_API_KEY")
        if not self.api_key:
            raise ValueError("PANTA_API_KEY is not set (env or constructor arg)")
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "X-Api-Key": self.api_key,
                "Content-Type": "application/json",
            },
        )

    # ---- auth / account (only needed once, to obtain a key) ----

    @staticmethod
    def register_account(email: str, base_url: str = DEFAULT_BASE_URL) -> dict:
        """POST /auth/register/ — one-time account creation."""
        resp = httpx.post(f"{base_url.rstrip('/')}/auth/register/", json={"email": email})
        _raise_for_status(resp)
        return resp.json()

    def create_api_key(self, label: str = "pantapredict", env: str = "test") -> dict:
        """POST /account/keys/ — issue a pk_test_/pk_live_ key for this account."""
        resp = self._client.post("/account/keys/", json={"label": label, "env": env})
        _raise_for_status(resp)
        return resp.json()

    # ---- markets ----

    def list_markets(self, **params) -> dict:
        """GET /markets/ — trailing slash is required."""
        resp = self._client.get("/markets/", params=params)
        _raise_for_status(resp)
        return resp.json()

    def get_market(self, market_id: str) -> dict:
        resp = self._client.get(f"/markets/{market_id}/")
        _raise_for_status(resp)
        return resp.json()

    def get_categories(self) -> list[str]:
        """GET /markets/categories/ — get the allowlist of valid category values."""
        try:
            resp = self._client.get("/markets/categories/")
            _raise_for_status(resp)
            data = resp.json()
            # Handle different response formats
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "category" in data:
                return [data["category"]]
            else:
                # Fallback to extracting from markets
                markets = self.list_markets()
                categories = set()
                if "items" in markets:
                    for market in markets["items"]:
                        if "category" in market:
                            categories.add(market["category"])
                return list(categories)
        except Exception as e:
            # Fallback to hardcoded categories if API fails
            return ["crypto"]

    # ---- market creation flow: quote -> build -> register ----

    def quote_market(
        self,
        question: str,
        resolution_rule: str,
        sources_of_truth: list[str],
        description: str = "",
        image_url: Optional[str] = None,
        category: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        resolution_time: Optional[int] = None,
    ) -> MarketQuote:
        """POST /markets/create/quote/ — get pricing/fee quote for a new market."""
        payload = {
            "question": question,
            "resolutionRule": resolution_rule,
            "sourcesOfTruth": sources_of_truth,
            "description": description,
        }
        if image_url:
            payload["imageUrl"] = image_url
        if category:
            payload["category"] = category
        if start_time is not None:
            payload["startTime"] = start_time
        if end_time is not None:
            payload["endTime"] = end_time
        if resolution_time is not None:
            payload["resolutionTime"] = resolution_time

        resp = self._client.post("/markets/create/quote/", json=payload)
        _raise_for_status(resp)
        return MarketQuote(raw=resp.json())

    def build_market(self, create_id: str, wallet: str) -> dict:
        """
        POST /markets/create/build/ — returns an unsigned transaction for the
        creator's wallet to sign. Backend must never sign this itself.
        """
        payload = {"createId": create_id, "wallet": wallet}
        resp = self._client.post("/markets/create/build/", json=payload)
        _raise_for_status(resp)
        return resp.json()

    def register_market(self, create_id: str, signature: str) -> dict:
        """
        POST /markets/register/ — submit the broadcast transaction signature
        to finalize market creation.
        """
        payload = {"createId": create_id, "signature": signature}
        resp = self._client.post("/markets/register/", json=payload)
        _raise_for_status(resp)
        return resp.json()

    def close(self):
        self._client.close()


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise PantaAPIError(resp.status_code, detail)
