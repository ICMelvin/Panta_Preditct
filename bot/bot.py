"""Layer 3 — bot entrypoint."""

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path

# Add parent directory to path to load backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file with override=True to win over stale shell variables
# In production (Render), environment variables come from the platform, not from .env
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    logger.info(f"Loaded .env from: {env_path}")
else:
    logger.info("Using environment variables from platform (no .env file)")

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.request import HTTPXRequest
from telegram.error import NetworkError, TimedOut
import httpx

from bot.handlers import predict, start, trade, handle_webapp_data

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def error_handler(update, context):
    """Handle network errors gracefully without crashing."""
    if isinstance(context.error, (NetworkError, TimedOut)):
        logger.warning(f"Network error (will retry): {type(context.error).__name__}")
    else:
        logger.error(f"Unexpected error: {context.error}", exc_info=True)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    # Normalize and validate TELEGRAM_MINIAPP_URL
    miniapp_url = os.getenv("TELEGRAM_MINIAPP_URL", "")
    if miniapp_url:
        # Strip whitespace and quotes
        miniapp_url = miniapp_url.strip().strip('"').strip("'")
        # Remove trailing slash
        miniapp_url = miniapp_url.rstrip('/')

        if not miniapp_url.startswith("https://"):
            raise RuntimeError(
                f"TELEGRAM_MINIAPP_URL must use HTTPS (Telegram requirement). "
                f"Got: {miniapp_url}. Please use https:// instead of http://"
            )

        # Log the resolved host (for debugging, no secrets)
        from urllib.parse import urlparse
        parsed = urlparse(miniapp_url)
        logger.info(f"Mini App URL host: {parsed.netloc}")

    # Configure with explicit HTTPXRequest objects for normal API calls and get_updates
    # Force IPv4 only if FORCE_IPV4=1 is set (for environments where IPv6 fails)
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)

    if os.getenv("FORCE_IPV4", "0") == "1":
        transport = httpx.AsyncHTTPTransport(
            retries=3,
            limits=limits,
            local_address="0.0.0.0"  # Force IPv4
        )
        logger.info("IPv4 forcing enabled (FORCE_IPV4=1)")
    else:
        transport = httpx.AsyncHTTPTransport(retries=3, limits=limits)

    normal_request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=20.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=20.0,
        httpx_kwargs={"transport": transport}
    )

    get_updates_request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=20.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=20.0,
        httpx_kwargs={"transport": transport}
    )

    app = (
        Application.builder()
        .token(token)
        .request(normal_request)
        .get_updates_request(get_updates_request)
        .build()
    )

    # Register error handler
    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("predict", predict))
    app.add_handler(CommandHandler("trade", trade))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))

    print("PantaPredict bot running...")
    print("Note: Bot requires network connectivity to api.telegram.org for polling")
    print("If in a restricted environment, consider using webhooks instead of polling")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
