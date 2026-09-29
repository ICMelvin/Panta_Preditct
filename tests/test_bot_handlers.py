"""Tests for bot handlers."""

import sys
from pathlib import Path

# Add parent directory to path to import bot modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import Mock, AsyncMock, patch
import pytest
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes
import os

# Set environment variable before importing handlers
os.environ["TELEGRAM_MINIAPP_URL"] = "https://test.example.com"

# Import handlers after environment is set
from bot import handlers


@pytest.fixture
def mock_update():
    """Create a mock Update object for testing."""
    update = Mock(spec=Update)
    update.message = Mock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.message.from_user = Mock(spec=User)
    update.message.from_user.id = 12345
    update.message.chat = Mock(spec=Chat)
    update.message.chat.id = 12345
    return update


@pytest.fixture
def mock_context():
    """Create a mock Context object for testing."""
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    return context


@pytest.mark.asyncio
async def test_predict_handler_no_args(mock_update, mock_context):
    """Test that predict handler with no args shows usage message."""
    mock_context.args = []
    
    await handlers.predict(mock_update, mock_context)
    
    # Should reply with usage message
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "Usage: /predict" in call_args


@pytest.mark.asyncio
async def test_predict_handler_with_question_no_unboundlocalerror(mock_update, mock_context):
    """Test that predict handler with a valid question does NOT raise UnboundLocalError."""
    mock_context.args = ["Will", "Bitcoin", "reach", "$100k", "by", "end", "of", "2026?", "per", "CoinDesk"]
    
    # This should NOT raise UnboundLocalError
    try:
        await handlers.predict(mock_update, mock_context)
        # If we get here, no UnboundLocalError was raised
        assert True
    except UnboundLocalError as e:
        pytest.fail(f"UnboundLocalError raised: {e}")


@pytest.mark.asyncio
async def test_predict_handler_invalid_question(mock_update, mock_context):
    """Test that predict handler with invalid question (no deadline) shows quality gate failure."""
    mock_context.args = ["Will", "crypto", "go", "up", "soon?"]
    
    await handlers.predict(mock_update, mock_context)
    
    # Should reply with quality gate failure message
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "needs a bit more" in call_args or "deadline" in call_args.lower()
