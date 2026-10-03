"""
Layer 3 — Bot handlers.

Text-only end-to-end flow: /predict runs a question through the quality
gate, and on success, launches the Mini App for the actual creation +
wallet signing (Layers 4-5). Keeps a bare quote-and-confirm text path too,
so the bot works even before the Mini App exists.
"""

from __future__ import annotations
from dotenv import load_dotenv
from backend.quality_gate import run_quality_gate
from backend.panta_client import PantaClient
from telegram.error import NetworkError, TimedOut
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo

import os
import sys
import asyncio
import logging
import uuid
from pathlib import Path
from functools import wraps
from urllib.parse import quote

# Add parent directory to path to load backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))


# Load environment variables before evaluating MINIAPP_URL
# This is needed because handlers.py is imported before bot.py loads the environment
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

MINIAPP_URL = os.getenv("TELEGRAM_MINIAPP_URL", "")

# Configure logging
logger = logging.getLogger(__name__)

# Log which path will be used
if MINIAPP_URL:
    logger.info(
        f"MINIAPP_URL is set: {MINIAPP_URL} -> Using Mini App button path")
else:
    logger.info("MINIAPP_URL is not set -> Using fallback quote_market path")

# Initialize Panta client lazily to ensure env vars are loaded
_panta = None


def get_panta_client():
    global _panta
    if _panta is None:
        _panta = PantaClient()
    return _panta


def retry_on_network_error(max_attempts=3, backoff=1.0):
    """Decorator to retry functions on NetworkError or TimedOut."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except (NetworkError, TimedOut) as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Network error on attempt {attempt + 1}/{max_attempts}, retrying in {backoff}s...")
                        await asyncio.sleep(backoff)
                    else:
                        logger.error(
                            f"Failed after {max_attempts} attempts: {e}")
                        raise
            raise last_error
        return wrapper
    return decorator


# Apply retry wrapper to common message methods
@retry_on_network_error(max_attempts=3, backoff=1.0)
async def safe_reply_text(message, *args, **kwargs):
    """Wrapper for message.reply_text with retry logic."""
    return await message.reply_text(*args, **kwargs)


async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = " ".join(context.args) if context.args else ""
    if not question:
        await safe_reply_text(
            update.message,
            "Usage: /predict <your yes/no question>\n"
            "e.g. /predict Will Bitcoin reach $100k by end of 2026? per CoinDesk"
        )
        return

    gate = run_quality_gate(question)

    if not gate.passed:
        failed = [
            f"- {name}: {check.message}"
            for name, check in [
                ("deadline", gate.deadline),
                ("source", gate.source),
                ("binary", gate.binary),
            ]
            if not check.passed
        ]
        await safe_reply_text(
            update.message,
            "That question needs a bit more before it's marketable:\n"
            + "\n".join(failed)
        )
        return

    if MINIAPP_URL:
        # URL-encode the question (preserve safe chars like /)
        encoded_question = quote(question, safe='/')
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(
                "Create Market",
                web_app=WebAppInfo(url=f"{MINIAPP_URL}?q={encoded_question}"),
            )]]
        )
        await safe_reply_text(
            update.message,
            "Looks good. Tap below to finish creating the market:",
            reply_markup=keyboard,
        )
    else:
        # Fallback path for before the Mini App / wallet signing exists —
        # gets you a real end-to-end test using quote() alone.
        panta = get_panta_client()
        market_quote = panta.quote_market(
            question=question,
            resolution_rule="To be determined",
            sources_of_truth=["https://example.com"],
        )
        await safe_reply_text(update.message, f"Quote received: {market_quote.raw}")


def is_uuid_like(value: str | None) -> bool:
    """Return True for a UUID-shaped session ID, which is how wallet sessions are created."""
    if not value:
        return False
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payload = context.args[0] if context.args else None

    if payload and is_uuid_like(payload):
        session_id = str(payload)
        encoded_start_param = quote(session_id, safe='')
        mini_app_url = f"{MINIAPP_URL}?tgWebAppStartParam={encoded_start_param}"
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(
                "Open Mini App",
                web_app=WebAppInfo(url=mini_app_url),
            )]]
        )
        await safe_reply_text(
            update.message,
            "Wallet connected! Tap below to continue creating your market:",
            reply_markup=keyboard,
        )
        return

    await safe_reply_text(
        update.message,
        "PantaPredict — turn a chat argument into a real market.\n"
        "Use /predict <question> to get started.\n"
        "Example: /predict Will Bitcoin reach $100k by end of 2026? per CoinDesk"
    )


async def trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /trade command to view market details."""
    if not context.args or len(context.args) < 1:
        await safe_reply_text(
            update.message,
            "Usage: /trade <market_id>\n"
            "e.g. /trade market_123"
        )
        return

    market_id = context.args[0]
    try:
        panta = get_panta_client()
        market = panta.get_market(market_id)
        # Handle null price fields (no live price yet)
        yes_price = market.get("yesPrice") or market.get("primaryYesPrice")
        no_price = market.get("noPrice") or market.get("primaryNoPrice")

        price_text = "No live price yet" if yes_price is None else f"Yes: {yes_price} | No: {no_price}"

        await safe_reply_text(
            update.message,
            f"📊 Market: {market.get('question', 'Unknown')}\n"
            f"📈 Price: {price_text}\n"
            f"🏷️ Category: {market.get('category', 'N/A')}\n"
            f"📅 End: {market.get('endTime', 'N/A')}\n"
            f"🆔 ID: {market_id}"
        )
    except Exception as e:
        await safe_reply_text(update.message, f"Error fetching market: {e}")


async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle data sent from Mini App when market is created."""
    if update.message and update.message.web_app_data:
        try:
            import json
            data = json.loads(update.message.web_app_data.data)
            if data.get("action") == "market_created":
                create_id = data.get("create_id")
                question = data.get("question")

                # Send a trade button for the newly created market
                # URL-encode the create_id (preserve safe chars)
                encoded_create_id = quote(create_id, safe='/')
                keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(
                        "Trade this market",
                        web_app=WebAppInfo(
                            url=f"{MINIAPP_URL}?market={encoded_create_id}"),
                    )]]
                )
                await safe_reply_text(
                    update.message,
                    f"✅ Market created: {question}\n"
                    f"🆔 Create ID: {create_id}\n"
                    f"Tap below to trade:",
                    reply_markup=keyboard,
                )
        except Exception as e:
            await safe_reply_text(update.message, f"Error processing market creation: {e}")
