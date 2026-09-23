"""Layer 3 — bot entrypoint."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from bot.handlers import predict, start, quote_callback

load_dotenv()


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("predict", predict))
    app.add_handler(CallbackQueryHandler(quote_callback, pattern="^(confirm_quote|cancel_quote)$"))

    print("PantaPredict bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
