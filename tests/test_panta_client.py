import httpx
import pytest
import respx

from backend.panta_client import PantaAPIError, PantaClient


@pytest.fixture
def client():
    return PantaClient(api_key="pk_test_dummy", base_url="https://live-api.panta.market/api/v1")


@respx.mock
def test_list_markets_uses_trailing_slash(client):
    route = respx.get("https://live-api.panta.market/api/v1/markets/").mock(
        return_value=httpx.Response(200, json={"items": [], "nextCursor": None, "disclaimer": "test"})
    )
    result = client.list_markets()
    assert route.called
    assert "items" in result


@respx.mock
def test_quote_market_success(client):
    # Real response shape from live API
    respx.post("https://live-api.panta.market/api/v1/markets/create/quote/").mock(
        return_value=httpx.Response(200, json={
            "createId": "cr_sandbox_test",
            "userId": "usr_14dfGk-atVbnFZhZiRC-sw",
            "apiKeyId": "key_mDfklkg_sb2pSzzJP5Jgyg",
            "expectedEventPda": "TestMarket1111111111111111111111111111111",
            "paymentUsdc": "50000000",
            "liquidityInjectionUsdc": "10000000",
            "platformRevenueUsdc": "40000000",
            "marketType": "standard",
            "expiresAt": "2099-01-01T00:00:00Z",
            "blockhashExpiryHintSec": 60,
            "disclaimer": "Test mode: this response uses sandbox fixtures and does not access Solana mainnet."
        })
    )
    quote = client.quote_market(
        question="Will X happen by Friday?",
        resolution_rule="X will happen if condition is met",
        sources_of_truth=["https://example.com"],
    )
    assert quote.raw["createId"] == "cr_sandbox_test"
    assert "paymentUsdc" in quote.raw
    assert "marketType" in quote.raw


@respx.mock
def test_quote_market_error_raises(client):
    respx.post("https://live-api.panta.market/api/v1/markets/create/quote/").mock(
        return_value=httpx.Response(400, json={"detail": "bad image url"})
    )
    with pytest.raises(PantaAPIError):
        client.quote_market(
            question="x?",
            resolution_rule="x rule",
            sources_of_truth=["https://example.com"],
        )


@respx.mock
def test_get_categories(client):
    respx.get("https://live-api.panta.market/api/v1/markets/categories/").mock(
        return_value=httpx.Response(200, json=["Crypto", "Sports", "Politics"])
    )
    categories = client.get_categories()
    assert categories == ["Crypto", "Sports", "Politics"]


@respx.mock
def test_get_categories_fallback(client):
    # Test fallback when categories endpoint fails
    respx.get("https://live-api.panta.market/api/v1/markets/categories/").mock(
        return_value=httpx.Response(404, text="Not Found")
    )
    respx.get("https://live-api.panta.market/api/v1/markets/").mock(
        return_value=httpx.Response(200, json={"items": [{"category": "crypto"}], "nextCursor": None, "disclaimer": "test"})
    )
    categories = client.get_categories()
    assert "crypto" in categories


@respx.mock
def test_register_market_success(client):
    # Real response shape from live API
    respx.post("https://live-api.panta.market/api/v1/markets/register/").mock(
        return_value=httpx.Response(200, json={
            "status": "registered",
            "marketId": "TestMarket1111111111111111111111111111111",
            "createId": "cr_sandbox_test",
            "signature": "sandboxSignature1111111111111111111111111111111111111111111",
            "paymentUsdc": "50.00",
            "paymentUsdcBase": "50000000",
            "category": "crypto",
            "title": "Sandbox test market",
            "images": [],
            "disclaimer": "Test mode: this response uses sandbox fixtures and does not access Solana mainnet."
        })
    )
    result = client.register_market(create_id="test_id", signature="test_sig")
    assert result["status"] == "registered"
    assert "marketId" in result
    assert "paymentUsdc" in result


@respx.mock
def test_build_market(client):
    # Real response shape from live API
    respx.post("https://live-api.panta.market/api/v1/markets/create/build/").mock(
        return_value=httpx.Response(200, json={
            "transaction": "",
            "buildFingerprint": "sandbox",
            "expectedEventPda": "TestMarket1111111111111111111111111111111",
            "recentBlockhash": "SandboxBlockhash11111111111111111111111111111",
            "lastValidBlockHeight": 0,
            "expiresAt": "2099-01-01T00:00:00Z",
            "disclaimer": "Test mode: this response uses sandbox fixtures and does not access Solana mainnet."
        })
    )
    result = client.build_market(create_id="c_123", wallet="wallet_123")
    assert result["buildFingerprint"] == "sandbox"
    assert "recentBlockhash" in result
    assert "lastValidBlockHeight" in result
