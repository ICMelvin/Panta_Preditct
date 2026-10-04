# PantaPredict

Turn a group-chat argument into a real, tradeable prediction market — right inside Telegram, built on [Panta](https://panta.market) (Solana).

Built for Colosseum's Crypto World's Fair hackathon — Panta API Sidetrack.

## The problem

Panta is a permissionless prediction market protocol — anyone can create a market on anything. Two real gaps:

1. **Resolution trust** — nothing checks *before* a market is created whether the question is actually resolvable (clear deadline, checkable source, unambiguous yes/no). Vague questions lead to disputed resolutions.
2. **Distribution** — markets only live on Panta's own site. The real behavior already happens in group chats, where people argue and never formalize the bet.

## The solution

A Telegram bot + Mini App that:
- Lets anyone type `/predict <question>` in a group chat
- Runs it through a **quality gate** before any market gets created — checking for a deadline, a real source, and clear yes/no phrasing
- Opens a Mini App for wallet connection (Phantom, desktop extension or mobile deep link) and final market creation
- Creates the market for real via Panta's API — quote → build → sign → broadcast → register
- Posts the live market back into the chat

## Status

Fully working end-to-end on Panta's sandbox (`pk_test_`) environment — quote, build, sign, and register all succeed against the real Panta API. A visible **SANDBOX MODE** badge shows whenever running on a test key. Live-key (`pk_live_`) testing intentionally avoided during development to prevent unnecessary spend.

## Tech stack

- **Bot**: Python, `python-telegram-bot`
- **Backend**: FastAPI, proxies Panta's API and hosts the Mini App
- **Mini App**: HTML/CSS/JS, Telegram WebApp SDK, Phantom wallet integration (browser extension + mobile deep link, with NaCl box encryption for the connection handshake)
- **Deployed on**: Render

## Setup

See `DEPLOY.md` for full deployment instructions. Quick local setup:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
uvicorn backend.main:app --reload --port 8000   # backend
python -m bot.bot                                # bot (separate terminal)
```

## Attribution

Powered by [Panta](https://panta.market).
