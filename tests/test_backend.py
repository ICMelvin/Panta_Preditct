from fastapi.testclient import TestClient
from backend.main import app
import logging

client = TestClient(app)


def test_logging_config_redacts_token():
    """Test that httpx logging is set to WARNING to prevent token leaks."""
    # Import bot to trigger its logging configuration
    import bot.bot
    
    # httpx should be set to WARNING level, not INFO
    httpx_logger = logging.getLogger("httpx")
    assert httpx_logger.getEffectiveLevel() >= logging.WARNING, "httpx logger should be WARNING or higher to prevent token leaks"
    
    # httpcore should also be suppressed
    httpcore_logger = logging.getLogger("httpcore")
    assert httpcore_logger.getEffectiveLevel() >= logging.WARNING, "httpcore logger should be WARNING or higher to prevent token leaks"
    
    # telegram.request should be suppressed
    telegram_request_logger = logging.getLogger("telegram.request")
    assert telegram_request_logger.getEffectiveLevel() >= logging.WARNING, "telegram.request logger should be WARNING or higher to prevent token leaks"


def test_get_root():
    """Test that the root endpoint returns the Mini App HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "PantaPredict" in response.text


def test_get_app_js():
    """Test that app.js is served correctly."""
    response = client.get("/app.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "API_BASE" in response.text


def test_get_style_css():
    """Test that style.css is served correctly."""
    response = client.get("/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


def test_healthz():
    """Test the health check endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "mode" in data
    assert data["mode"] in ["sandbox", "live", "unknown"]


def test_quality_check_with_valid_question():
    """Test quality check with a valid question."""
    response = client.post(
        "/api/quality-check",
        json={
            "question": "Will Bitcoin reach $100,000 by December 31, 2026? per CoinMarketCap",
            "resolution_rule": "To be determined",
            "sources_of_truth": ["https://coinmarketcap.com"]
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is True
    assert data["checks"]["deadline"]["passed"] is True
    assert data["checks"]["source"]["passed"] is True
    assert data["checks"]["binary"]["passed"] is True

# Note: The Panta API in sandbox mode accepts any signature and returns fixture data.
# This is expected sandbox behavior. The Mini App no longer sends fabricated signatures,
# which is the key security fix. In production with live keys, only real signatures
# from signed transactions will be accepted.
