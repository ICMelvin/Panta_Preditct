"""
Layer 1 — Panta API client.

Thin wrapper around https://live-api.panta.market/api/v1.

Known quirks to handle (confirm/adjust against the live API as you test):
- GET /markets/ requires the trailing slash.
- Price fields (yesPrice / primaryYesPrice / secondaryYesPrice) can come
  back as null — that means "no live price yet", NOT 0%.
- Timestamps may be unix seconds (live) vs ISO strings (sandbox).
- Image URLs are validated at both the quote and build steps; not every
  public image host is accepted.
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

    def create_api_key(self, label: str = "pantapredict") -> dict:
        """POST /account/keys/ — issue a pk_test_/pk_live_ key for this account."""
        resp = self._client.post("/account/keys/", json={"label": label})
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

    # ---- market creation flow: quote -> build -> register ----

    def quote_market(
        self,
        question: str,
        deadline: str,
        source: str,
        description: str = "",
        image_url: Optional[str] = None,
        category: Optional[str] = None,
    ) -> MarketQuote:
        """POST /markets/create/quote/ — get pricing/fee quote for a new market."""
        payload = {
            "question": question,
            "deadline": deadline,
            "source": source,
            "description": description,
        }
        if image_url:
            payload["imageUrl"] = image_url
        if category:
            payload["category"] = category

        resp = self._client.post("/markets/create/quote/", json=payload)
        _raise_for_status(resp)
        return MarketQuote(raw=resp.json())

    def build_market(self, quote: MarketQuote, creator_wallet: str) -> dict:
        """
        POST /markets/create/build/ — returns an unsigned transaction for the
        creator's wallet to sign. Backend must never sign this itself.
        """
        payload = {"quoteId": quote.raw.get("quoteId"), "creatorWallet": creator_wallet}
        resp = self._client.post("/markets/create/build/", json=payload)
        _raise_for_status(resp)
        return resp.json()

    def register_market(self, build_id: str, signed_tx: str) -> dict:
        """
        POST /markets/create/register/ — submit the signed transaction to
        finalize market creation.
        """
        payload = {"buildId": build_id, "signedTransaction": signed_tx}
        resp = self._client.post("/markets/create/register/", json=payload)
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
