# PantaPredict

Telegram bot + Mini App that turns group-chat predictions into real,
tradeable markets on [Panta](https://panta.market) (Solana).

## What it does

PantaPredict solves two key problems in prediction markets:

1. **Resolution-trust gap**: Traditional prediction markets often suffer from ambiguous resolution criteria. PantaPredict's quality gate ensures every market has clear deadlines, verifiable sources, and unambiguous binary outcomes.

2. **Distribution-stuck-on-a-destination gap**: Prediction markets are hard to discover. PantaPredict brings market creation directly into Telegram conversations where people already debate outcomes, making it frictionless to turn arguments into tradeable markets.

## How it works

1. Users type `/predict Will Bitcoin reach $100k by end of 2026?` in a Telegram group
2. The bot runs the question through a quality gate (deadline check, source verification, binary phrasing)
3. If quality checks pass, users tap a button to open the Mini App
4. In the Mini App, users complete market details (resolution rule, sources, category, image)
5. Users connect their Phantom wallet and sign the transaction
6. The market is created on Panta and a "Trade" button is posted back to the group
7. Other group members can tap the trade button to view market details and current odds

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
│   ├── test_quality_gate.py
│   └── test_backend.py    # FastAPI endpoint tests
├── .env.example           # Environment variable template
├── .dockerignore          # Docker build exclusions
├── Dockerfile             # Container build instructions
├── Procfile               # Render deployment config
├── start.sh               # Startup script for bot + backend
├── DEPLOY.md              # Deployment guide
├── requirements.txt       # Pinned Python dependencies
└── README.md
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in your keys
```

## Running

### Local Development

```bash
# Backend (Layer 4 — needed before the Mini App works)
uvicorn backend.main:app --reload --port 8000

# Bot (Layer 3 — works standalone before Layer 4 exists)
python -m bot.bot
```

### Production Deployment

For deployment to Render or other cloud platforms, see [DEPLOY.md](DEPLOY.md) for step-by-step instructions.

The deployment uses:
- Docker containerization
- Single service running both FastAPI backend and Telegram bot
- Environment variables for all secrets (no .env in production)
- Automatic startup script (start.sh)

## Testing

```bash
# Run all tests
pytest tests/ -q

# Current test coverage: 12/12 passing
```

## Features

- ✅ Quality gate with deadline, source, and binary checks
- ✅ Real-time category fetching from Panta API
- ✅ Phantom wallet integration for transaction signing
- ✅ Image selection with pre-approved options
- ✅ Market creation flow (quote → build → register)
- ✅ Bot integration with Mini App via WebApp
- ✅ Trade command to view market details and live odds
- ✅ Null price handling (markets without live trading yet)
- ✅ "Powered by Panta" attribution (mandatory per API terms)

## Technical Notes

- Panta base API: `https://live-api.panta.market/api/v1` — the trailing slash on `/markets/` is required
- Register endpoint: `/markets/register/` (not `/markets/create/register/`)
- Backend never touches a private key. Transactions are built server-side and signed client-side in the Mini App (Phantom / Solana wallet adapter)
- Test mode (`pk_test_` keys) uses sandbox fixtures and does not access Solana mainnet
- API field names confirmed against real Panta documentation: `createId`, `resolutionRule`, `sourcesOfTruth`, `signature`
- "Powered by Panta" attribution is a mandatory term of their API Terms of Use — it's already stubbed into `miniapp/index.html`, don't remove it

## API Endpoints (Verified)

All endpoints have been tested against the live Panta API:

- `POST /markets/create/quote/` — Get pricing/fee quote for new market
- `POST /markets/create/build/` — Get unsigned transaction for wallet signing
- `POST /markets/register/` — Submit signed transaction to finalize market creation

Response shapes are documented in `backend/panta_client.py` with real API examples.

## Telegram Bot Connectivity

The bot code is correct and functional. Basic connectivity tests show:
- ✅ HTTP connectivity to `api.telegram.org` works (302 redirect)
- ✅ Bot API calls work (getMe returns bot info successfully)
- ✅ python-telegram-bot library initializes correctly
- ⚠️ Long-polling may timeout in restricted network environments

The bot uses 60-second timeouts for all operations. If experiencing connectivity issues in production, consider:
1. Using webhooks instead of long-polling
2. Deploying to a network with reliable internet access
3. Checking firewall/proxy settings

## Hackathon Submission

**Built for:** Colosseum Arena Hackathon
**Tracks:** Panta API Sidetrack, Solana Ecosystem Track, University Prize
**Timeline:** Solo build, 1 week
