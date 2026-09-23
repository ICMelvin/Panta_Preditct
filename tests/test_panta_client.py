import httpx
import pytest
import respx

from backend.panta_client import PantaAPIError, PantaClient, MarketQuote


@pytest.fixture
def client():
    return PantaClient(api_key="pk_test_dummy", base_url="https://live-api.panta.market/api/v1")


@respx.mock
def test_list_markets_uses_trailing_slash(client):
    route = respx.get("https://live-api.panta.market/api/v1/markets/").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    result = client.list_markets()
    assert route.called
    assert result == {"results": []}


@respx.mock
def test_quote_market_success(client):
    respx.post("https://live-api.panta.market/api/v1/markets/create/quote/").mock(
        return_value=httpx.Response(200, json={"quoteId": "q_123", "feeUsdc": 40})
    )
    quote = client.quote_market(
        question="Will X happen by Friday?",
        deadline="2026-10-10",
        source="https://example.com",
    )
    assert quote.raw["quoteId"] == "q_123"


@respx.mock
def test_quote_market_with_optional_fields(client):
    respx.post("https://live-api.panta.market/api/v1/markets/create/quote/").mock(
        return_value=httpx.Response(200, json={"quoteId": "q_456", "feeUsdc": 50})
    )
    quote = client.quote_market(
        question="Will Y happen?",
        deadline="2026-12-31",
        source="https://news.example.com/article",
        description="Additional context",
        image_url="https://example.com/image.jpg",
        category="politics",
    )
    assert quote.raw["quoteId"] == "q_456"


@respx.mock
def test_quote_market_handles_null_prices(client):
    """Test that null price fields are handled correctly (not treated as 0%)."""
    respx.post("https://live-api.panta.market/api/v1/markets/create/quote/").mock(
        return_value=httpx.Response(200, json={
            "quoteId": "q_789",
            "feeUsdc": 30,
            "yesPrice": None,  # Null means no price yet, not 0%
            "primaryYesPrice": None,
            "secondaryYesPrice": None
        })
    )
    quote = client.quote_market(
        question="Will Z happen?",
        deadline="2026-11-15",
        source="https://example.com",
    )
    assert quote.raw["yesPrice"] is None
    assert quote.raw["primaryYesPrice"] is None
    assert quote.raw["secondaryYesPrice"] is None


@respx.mock
def test_quote_market_error_raises(client):
    respx.post("https://live-api.panta.market/api/v1/markets/create/quote/").mock(
        return_value=httpx.Response(400, json={"detail": "bad image url"})
    )
    with pytest.raises(PantaAPIError) as exc_info:
        client.quote_market(question="x?", deadline="2026-10-10", source="https://example.com")
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == {"detail": "bad image url"}


@respx.mock
def test_build_market_success(client):
    quote = MarketQuote(raw={"quoteId": "q_123"})
    respx.post("https://live-api.panta.market/api/v1/markets/create/build/").mock(
        return_value=httpx.Response(200, json={
            "buildId": "b_456",
            "transaction": "base64_encoded_tx"
        })
    )
    result = client.build_market(quote, creator_wallet="test_wallet_address")
    assert result["buildId"] == "b_456"
    assert "transaction" in result


@respx.mock
def test_register_market_success(client):
    respx.post("https://live-api.panta.market/api/v1/markets/create/register/").mock(
        return_value=httpx.Response(200, json={
            "marketId": "m_789",
            "status": "registered"
        })
    )
    result = client.register_market(build_id="b_456", signed_tx="signed_base64_tx")
    assert result["marketId"] == "m_789"
    assert result["status"] == "registered"


@respx.mock
def test_register_market_error_on_invalid_signature(client):
    respx.post("https://live-api.panta.market/api/v1/markets/create/register/").mock(
        return_value=httpx.Response(400, json={"detail": "Invalid signature"})
    )
    with pytest.raises(PantaAPIError):
        client.register_market(build_id="b_456", signed_tx="invalid_signature")


@respx.mock
def test_get_market_success(client):
    respx.get("https://live-api.panta.market/api/v1/markets/m_123/").mock(
        return_value=httpx.Response(200, json={"marketId": "m_123", "question": "Test?"})
    )
    result = client.get_market("m_123")
    assert result["marketId"] == "m_123"


def test_client_requires_api_key():
    """Test that client raises error if no API key is provided."""
    import os
    # Temporarily clear env var
    old_key = os.environ.get("PANTA_API_KEY")
    os.environ.pop("PANTA_API_KEY", None)
    try:
        with pytest.raises(ValueError, match="PANTA_API_KEY is not set"):
            PantaClient()
    finally:
        if old_key:
            os.environ["PANTA_API_KEY"] = old_key


@respx.mock
def test_register_account_static():
    """Test static method for account registration."""
    respx.post("https://live-api.panta.market/api/v1/auth/register/").mock(
        return_value=httpx.Response(200, json={"userId": "u_123", "email": "test@example.com"})
    )
    result = PantaClient.register_account(email="test@example.com")
    assert result["userId"] == "u_123"


@respx.mock
def test_create_api_key(client):
    """Test creating an API key for an existing account."""
    respx.post("https://live-api.panta.market/api/v1/account/keys/").mock(
        return_value=httpx.Response(200, json={"apiKey": "pk_test_new_key", "label": "pantapredict"})
    )
    result = client.create_api_key(label="pantapredict")
    assert result["apiKey"] == "pk_test_new_key"


@respx.mock
def test_end_to_end_market_creation_flow(client):
    """Test the complete quote -> build -> register flow (sandbox scenario)."""
    # Step 1: Quote
    respx.post("https://live-api.panta.market/api/v1/markets/create/quote/").mock(
        return_value=httpx.Response(200, json={
            "quoteId": "q_e2e_123",
            "feeUsdc": 45,
            "yesPrice": None
        })
    )
    quote = client.quote_market(
        question="Will Bitcoin reach $100k by end of 2026?",
        deadline="2026-12-31",
        source="https://coindesk.com/markets"
    )
    assert quote.raw["quoteId"] == "q_e2e_123"
    
    # Step 2: Build
    respx.post("https://live-api.panta.market/api/v1/markets/create/build/").mock(
        return_value=httpx.Response(200, json={
            "buildId": "b_e2e_456",
            "transaction": "base64_encoded_unsigned_tx"
        })
    )
    build_result = client.build_market(quote, creator_wallet="test_wallet_solana")
    assert build_result["buildId"] == "b_e2e_456"
    assert "transaction" in build_result
    
    # Step 3: Register
    respx.post("https://live-api.panta.market/api/v1/markets/create/register/").mock(
        return_value=httpx.Response(200, json={
            "marketId": "m_e2e_789",
            "status": "registered",
            "question": "Will Bitcoin reach $100k by end of 2026?"
        })
    )
    register_result = client.register_market(
        build_id=build_result["buildId"],
        signed_tx="signed_base64_tx"
    )
    assert register_result["marketId"] == "m_e2e_789"
    assert register_result["status"] == "registered"
