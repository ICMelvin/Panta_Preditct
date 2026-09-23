"""
Layer 3 — Bot handlers.

Text-only end-to-end flow: /predict runs a question through the quality
gate, quotes a market, and on confirmation, builds/registers in sandbox.
Also includes background polling for market price updates.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes, ConversationHandler

from backend.panta_client import PantaClient, PantaAPIError
from backend.quality_gate import run_quality_gate

MINIAPP_URL = os.getenv("TELEGRAM_MINIAPP_URL", "")

# Conversation states
CONFIRM_QUOTE = 1

# Store pending quotes for confirmation (chat_id -> quote data)
_pending_quotes = {}

# Store active markets for polling (market_id -> chat_id)
_active_markets = {}

# Lazy initialization of PantaClient to avoid import-time errors
_panta = None


def _get_panta_client():
    """Get or create the PantaClient instance."""
    global _panta
    if _panta is None:
        _panta = PantaClient()
    return _panta


async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /predict command - run quality gate and quote a market."""
    question = " ".join(context.args) if context.args else ""
    if not question:
        await update.message.reply_text(
            "Usage: /predict <your yes/no question>\n"
            "e.g. /predict Will Team X win by Friday? per official results at example.com"
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
        await update.message.reply_text(
            "❌ That question needs a bit more before it's marketable:\n"
            + "\n".join(failed)
        )
        return

    # Quality gate passed - try to get a quote
    try:
        # If Mini App URL is configured, use it instead of text-only flow
        if MINIAPP_URL:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "📱 Create Market",
                    web_app=WebAppInfo(url=f"{MINIAPP_URL}?q={question}")
                )]
            ])
            await update.message.reply_text(
                f"✅ Quality check passed!\n\n"
                f"📝 Question: {question}\n\n"
                f"Tap below to finish creating the market in the Mini App:",
                reply_markup=keyboard
            )
            return

        # Fallback: text-only flow for when Mini App is not configured
        # Extract deadline and source from question (simplified for now)
        # In production, these would be parsed more carefully or entered separately
        panta = _get_panta_client()
        quote = panta.quote_market(
            question=question,
            deadline="2026-12-31T23:59:59Z",  # Default deadline for testing
            source="https://example.com",  # Default source for testing
            description="Created via PantaPredict Telegram bot"
        )
        
        # Store for confirmation
        chat_id = update.effective_chat.id
        _pending_quotes[chat_id] = {
            "question": question,
            "quote": quote,
            "timestamp": datetime.now()
        }
        
        # Show quote details and ask for confirmation
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Confirm & Create", callback_data="confirm_quote"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_quote")
            ]
        ])
        
        await update.message.reply_text(
            f"✅ Quality check passed!\n\n"
            f"📝 Question: {question}\n"
            f"💰 Fee: {quote.raw.get('feeUsdc', 'N/A')} USDC\n"
            f"📊 Quote ID: {quote.raw.get('quoteId', 'N/A')}\n\n"
            f"Create this market on Panta (sandbox)?",
            reply_markup=keyboard
        )
        
    except PantaAPIError as e:
        await update.message.reply_text(
            f"❌ Failed to get quote from Panta API: {e.detail}"
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Unexpected error: {str(e)}"
        )


async def quote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle quote confirmation/cancellation callback."""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    
    if query.data == "cancel_quote":
        if chat_id in _pending_quotes:
            del _pending_quotes[chat_id]
        await query.edit_message_text("❌ Market creation cancelled.")
        return
    
    if query.data == "confirm_quote":
        if chat_id not in _pending_quotes:
            await query.edit_message_text("❌ Quote expired or not found.")
            return
        
        quote_data = _pending_quotes[chat_id]
        quote = quote_data["quote"]
        question = quote_data["question"]
        
        # For sandbox testing, we'll use a dummy wallet address
        # In production, this would come from wallet connection
        dummy_wallet = "test_wallet_sandbox_address"
        
        try:
            panta = _get_panta_client()
            # Build the transaction
            build_result = panta.build_market(quote, creator_wallet=dummy_wallet)
            build_id = build_result.get("buildId")
            
            # In sandbox, we can simulate signing (normally done client-side)
            # For this text-only demo, we'll use a dummy signed transaction
            dummy_signed_tx = "simulated_signed_transaction_for_sandbox"
            
            # Register the market
            register_result = panta.register_market(
                build_id=build_id,
                signed_tx=dummy_signed_tx
            )
            
            market_id = register_result.get("marketId")
            
            # Clean up pending quote
            del _pending_quotes[chat_id]
            
            # Store for polling
            _active_markets[market_id] = chat_id
            
            await query.edit_message_text(
                f"🎉 Market created successfully!\n\n"
                f"📝 Question: {question}\n"
                f"🆔 Market ID: {market_id}\n\n"
                f"I'll post price updates to this chat periodically."
            )
            
            # Add a "Trade" button to reopen Mini App for this market (Layer 6)
            if MINIAPP_URL:
                trade_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "📊 Trade",
                        web_app=WebAppInfo(url=f"{MINIAPP_URL}?market={market_id}")
                    )]
                ])
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="Tap below to trade this market:",
                    reply_markup=trade_keyboard
                )
            
            # Start background polling for this market
            asyncio.create_task(poll_market_price(market_id, chat_id, context))
            
        except PantaAPIError as e:
            await query.edit_message_text(
                f"❌ Failed to create market: {e.detail}"
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Unexpected error during market creation: {str(e)}"
            )


async def poll_market_price(market_id: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Background task to poll market price and post updates."""
    panta = _get_panta_client()
    while market_id in _active_markets:
        try:
            # Poll every 5 minutes for demo purposes
            await asyncio.sleep(300)
            
            if market_id not in _active_markets:
                break
                
            market_data = panta.get_market(market_id)
            
            # Extract price (handle null values)
            yes_price = market_data.get("yesPrice")
            price_str = f"{yes_price}%" if yes_price is not None else "No price yet"
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"📊 Market Update ({market_id}):\n"
                     f"Current Yes Price: {price_str}"
            )
            
        except PantaAPIError as e:
            print(f"Error polling market {market_id}: {e}")
            # Don't break on API errors, keep trying
        except Exception as e:
            print(f"Unexpected error polling market {market_id}: {e}")
            break


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.message.reply_text(
        "🎯 PantaPredict — turn chat arguments into real markets on Panta.\n\n"
        "Commands:\n"
        "/predict <question> - Create a prediction market\n"
        "/start - Show this help message\n\n"
        "Example: /predict Will Bitcoin reach $100k by end of 2026? per CoinDesk"
    )
