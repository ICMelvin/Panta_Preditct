"""
Tests for Layer 3 - Bot handlers.

Tests the /predict flow, quality gate integration, and callback handling.
Uses mocking to avoid actual Telegram API calls.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.handlers import predict, start, quote_callback, _pending_quotes, _active_markets, _get_panta_client
from backend.quality_gate import run_quality_gate


@pytest.fixture(autouse=True)
def setup_env():
    """Set up environment variables for tests."""
    # Set a dummy API key to avoid import errors
    os.environ["PANTA_API_KEY"] = "pk_test_dummy_key"
    yield
    # Clean up
    os.environ.pop("PANTA_API_KEY", None)


@pytest.fixture
def mock_update():
    """Create a mock Telegram Update object."""
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    update.callback_query = MagicMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Create a mock Telegram Context object."""
    context = MagicMock()
    context.args = []
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


@pytest.mark.asyncio
async def test_predict_no_args(mock_update, mock_context):
    """Test /predict with no arguments shows usage."""
    mock_context.args = []
    await predict(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "Usage:" in call_args
    assert "/predict" in call_args


@pytest.mark.asyncio
async def test_predict_with_good_question(mock_update, mock_context):
    """Test /predict with a good question passes quality gate."""
    good_question = "Will Bitcoin reach $100k by 2026-12-31? per CoinDesk"
    mock_context.args = good_question.split()
    
    # Mock the Panta client to avoid actual API calls
    with patch('bot.handlers._get_panta_client') as mock_get_client:
        mock_panta = MagicMock()
        mock_quote = MagicMock()
        mock_quote.raw = {
            "quoteId": "q_test_123",
            "feeUsdc": 40
        }
        mock_panta.quote_market.return_value = mock_quote
        mock_get_client.return_value = mock_panta
        
        await predict(mock_update, mock_context)
        
        # Should have called reply_text with quote details
        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Quality check passed" in call_args
        assert "Quote ID" in call_args


@pytest.mark.asyncio
async def test_predict_with_bad_question(mock_update, mock_context):
    """Test /predict with a bad question fails quality gate."""
    bad_question = "X might happen"  # No deadline, no source, not yes/no
    mock_context.args = bad_question.split()
    
    await predict(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "needs a bit more" in call_args


@pytest.mark.asyncio
async def test_predict_quality_gate_deadline_failure(mock_update, mock_context):
    """Test that missing deadline is caught by quality gate."""
    question = "Will Bitcoin reach $100k? per CoinDesk"  # Missing deadline
    mock_context.args = question.split()
    
    await predict(mock_update, mock_context)
    
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "deadline" in call_args.lower()


@pytest.mark.asyncio
async def test_predict_quality_gate_source_failure(mock_update, mock_context):
    """Test that missing source is caught by quality gate."""
    question = "Will Bitcoin reach $100k by end of 2026?"  # Missing source
    mock_context.args = question.split()
    
    await predict(mock_update, mock_context)
    
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "source" in call_args.lower()


@pytest.mark.asyncio
async def test_predict_quality_gate_binary_failure(mock_update, mock_context):
    """Test that non-binary phrasing is caught by quality gate."""
    question = "Bitcoin might reach $100k by end of 2026? per CoinDesk"  # "might" is hedging
    mock_context.args = question.split()
    
    await predict(mock_update, mock_context)
    
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "binary" in call_args.lower() or "yes/no" in call_args.lower()


@pytest.mark.asyncio
async def test_quote_callback_cancel(mock_update, mock_context):
    """Test canceling a quote via callback."""
    mock_update.callback_query.data = "cancel_quote"
    
    # Set up a pending quote
    _pending_quotes[12345] = {
        "question": "Test question",
        "quote": MagicMock(),
        "timestamp": None
    }
    
    await quote_callback(mock_update, mock_context)
    
    assert 12345 not in _pending_quotes
    mock_update.callback_query.edit_message_text.assert_called_once()
    call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
    assert "cancelled" in call_args.lower()


@pytest.mark.asyncio
async def test_quote_callback_confirm_success(mock_update, mock_context):
    """Test confirming a quote successfully creates a market."""
    mock_update.callback_query.data = "confirm_quote"
    
    # Set up a pending quote
    mock_quote = MagicMock()
    mock_quote.raw = {"quoteId": "q_test_123"}
    _pending_quotes[12345] = {
        "question": "Test question",
        "quote": mock_quote,
        "timestamp": None
    }
    
    with patch('bot.handlers._get_panta_client') as mock_get_client:
        mock_panta = MagicMock()
        # Mock build_market
        mock_panta.build_market.return_value = {
            "buildId": "b_test_456",
            "transaction": "base64_tx"
        }
        
        # Mock register_market
        mock_panta.register_market.return_value = {
            "marketId": "m_test_789",
            "status": "registered"
        }
        mock_get_client.return_value = mock_panta
        
        await quote_callback(mock_update, mock_context)
        
        # Verify market was created
        assert 12345 not in _pending_quotes
        assert "m_test_789" in _active_markets
        
        # Verify success message
        call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
        assert "successfully" in call_args.lower()
        assert "m_test_789" in call_args


@pytest.mark.asyncio
async def test_quote_callback_confirm_expired(mock_update, mock_context):
    """Test confirming a quote that has expired."""
    mock_update.callback_query.data = "confirm_quote"
    
    # No pending quote set up
    if 12345 in _pending_quotes:
        del _pending_quotes[12345]
    
    await quote_callback(mock_update, mock_context)
    
    mock_update.callback_query.edit_message_text.assert_called_once()
    call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
    assert "expired" in call_args.lower() or "not found" in call_args.lower()


@pytest.mark.asyncio
async def test_start_command(mock_update, mock_context):
    """Test /start command shows help message."""
    await start(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "PantaPredict" in call_args
    assert "/predict" in call_args


def test_quality_gate_integration():
    """Test that the quality gate works correctly in isolation."""
    # Good question
    good = "Will X happen by Friday? per example.com"
    result = run_quality_gate(good)
    assert result.passed
    
    # Bad question - no deadline
    bad1 = "Will X happen? per example.com"
    result = run_quality_gate(bad1)
    assert not result.passed
    assert not result.deadline.passed
    
    # Bad question - no source
    bad2 = "Will X happen by Friday?"
    result = run_quality_gate(bad2)
    assert not result.passed
    assert not result.source.passed
    
    # Bad question - not binary
    bad3 = "X might happen by Friday? per example.com"
    result = run_quality_gate(bad3)
    assert not result.passed
    assert not result.binary.passed
