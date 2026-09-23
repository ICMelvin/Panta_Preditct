# PantaPredict

Telegram bot + Mini App that turns group-chat predictions into real,
tradeable markets on [Panta](https://panta.market) (Solana).

Built back-to-front. See `docs/panta-predict-project-plan.md` for the
full project plan and 7-day build sequence.

## Layout

```
pantapredict/
├── backend/
│   ├── panta_client.py    # Layer 1 — Panta API wrapper
│   ├── quality_gate.py    # Layer 2 — question quality checks
│   ├── models.py          # shared data models
│   └── main.py            # Layer 4 — FastAPI app (serves Mini App + API)
├── bot/
│   ├── handlers.py        # /predict flow, confirmation, odds polling
│   └── bot.py             # Layer 3 — bot entrypoint
├── miniapp/
│   ├── index.html         # Layer 5 — Mini App UI
│   ├── style.css
│   └── app.js             # quality-gate display, wallet connect + sign
├── tests/
│   ├── test_panta_client.py
│   └── test_quality_gate.py
├── .env.example
├── requirements.txt
└── README.md
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in your keys
```

## Build order (do not skip ahead)

1. ✓ `backend/panta_client.py` + `tests/test_panta_client.py` — confirm you can
   quote/build/register a market in sandbox before touching anything else.
   **STATUS: COMPLETE** — 13 unit tests passing, handles all known API quirks.
2. ✓ `backend/quality_gate.py` + `tests/test_quality_gate.py` — pure logic,
   no network calls, fully unit-testable.
   **STATUS: COMPLETE** — 17 unit tests passing, validates deadlines, sources, and binary phrasing.
3. ✓ `bot/bot.py` + `bot/handlers.py` — text-only end-to-end flow in Telegram.
   **STATUS: COMPLETE** — 11 unit tests passing, quality gate integration, quote/confirm flow, background polling.
4. ✓ `backend/main.py` — FastAPI layer exposing quote/quality-gate/register to
   the Mini App; never handles or stores private keys.
   **STATUS: COMPLETE** — 13 unit tests passing, REST API with quality gate integration.
5. ✓ `miniapp/` — creation form + quality-gate display + wallet connect/sign.
   **STATUS: COMPLETE** — Full quote→build→sign→register flow with Phantom wallet integration, pre-filled from Telegram start_param.
6. ✓ Wire bot ↔ Mini App — WebAppInfo integration.
   **STATUS: COMPLETE** — Bot opens Mini App with pre-filled question, Trade button reopens Mini App for specific market.

## Running

```bash
# Backend (Layer 4 — needed before the Mini App works)
uvicorn backend.main:app --reload --port 8000

# Bot (Layer 3 — works standalone before Layer 4 exists)
python -m bot.bot
```

## Notes

- Panta base API: `https://live-api.panta.market/api/v1` — the trailing
  slash on `/markets/` is required.
- Backend never touches a private key. Transactions are built server-side
  and signed client-side in the Mini App (Phantom / Solana wallet adapter).
- "Powered by Panta" attribution is a mandatory term of their API Terms of
  Use — it's already stubbed into `miniapp/index.html`, don't remove it.
