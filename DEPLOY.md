# Deploy PantaPredict to Render

This guide will help you deploy PantaPredict to Render as a single service that runs both the FastAPI backend and the Telegram bot.

## Prerequisites

1. A Render account (free tier is sufficient)
2. A Telegram bot token from BotFather
3. A Panta API key (pk_test_ or pk_live_)
4. A GitHub account with your PantaPredict code pushed to a public repository

## Step 1: Prepare Your GitHub Repository

1. Push your PantaPredict code to a public GitHub repository
2. Make sure these files are in the repository root:
   - `Dockerfile`
   - `Procfile`
   - `requirements.txt`
   - `start.sh`
   - `backend/` (FastAPI backend)
   - `bot/` (Telegram bot)
   - `miniapp/` (Mini App frontend)

## Step 2: Create a New Web Service on Render

1. Log in to [Render](https://render.com)
2. Click **New +** → **Web Service**
3. Connect your GitHub repository
4. Render will detect your Dockerfile automatically

## Step 3: Configure the Web Service

### Build & Deploy Settings

- **Name**: `pantapredict` (or any name you prefer)
- **Region**: Choose a region close to your users
- **Branch**: `main` (or your default branch)
- **Runtime**: Docker (should be auto-detected)
- **Root Directory**: Leave blank (root of repository)
- **Instance Type**: Free (for development) or paid (for production)

**Note:** Render automatically sets the `PORT` environment variable. The `start.sh` script uses this variable to bind uvicorn to the correct port (defaulting to 8000 if not set).

### Environment Variables

Add these environment variables in the **Environment** section:

1. **PANTA_API_KEY**
   - Your Panta API key (e.g., `pk_test_...` or `pk_live_...`)
   - Get this from the Panta dashboard

2. **TELEGRAM_BOT_TOKEN**
   - Your Telegram bot token from BotFather
   - Format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

3. **TELEGRAM_MINIAPP_URL**
   - Your Render service URL (you'll get this after deployment)
   - Format: `https://pantapredict.onrender.com`
   - **Important**: After you deploy, you'll get a URL like `https://pantapredict-xxxx.onrender.com`
   - Update this environment variable with that URL

**Optional Environment Variables:**

4. **FORCE_IPV4**
   - Set to `1` only if you experience IPv6 connectivity issues
   - Default: `0` (unset or `0` means use system default)

## Step 4: Deploy

1. Click **Create Web Service**
2. Render will build your Docker image and deploy it
3. Wait for the deployment to complete (usually 2-5 minutes)
4. You'll see a URL like `https://pantapredict-xxxx.onrender.com`

## Step 5: Update TELEGRAM_MINIAPP_URL

1. Copy your Render service URL (e.g., `https://pantapredict-xxxx.onrender.com`)
2. Go back to your Render web service
3. Click **Environment** tab
4. Update **TELEGRAM_MINIAPP_URL** with your Render URL
5. Click **Save Changes**
6. Render will automatically redeploy with the new URL

## Step 6: Set Up Your Telegram Bot Webhook (Optional)

The bot uses long-polling by default, which works fine on Render. However, for better reliability, you can set up a webhook:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://pantapredict-xxxx.onrender.com/telegram/webhook"
```

Note: You'll need to implement a webhook endpoint in `bot/bot.py` if you want to use webhooks instead of long-polling. The current implementation uses long-polling, which works fine.

## Step 7: Test Your Deployment

1. Open your Render URL in a browser: `https://pantapredict-xxxx.onrender.com`
2. You should see the Mini App interface
3. Test the health endpoint: `https://pantapredict-xxxx.onrender.com/healthz`
4. In Telegram, send `/start` to your bot
5. Try a prediction: `/predict Will Bitcoin reach $100k by end of 2026? per CoinMarketCap`
6. Tap the "Create Market" button
7. Complete the form in the Mini App
8. Connect your Phantom wallet and sign the transaction

## Troubleshooting

### Bot not responding?

- Check the Render logs for errors
- Make sure `TELEGRAM_BOT_TOKEN` is set correctly
- Make sure `TELEGRAM_MINIAPP_URL` is set to your Render URL

### Mini App not loading?

- Check that `TELEGRAM_MINIAPP_URL` is set correctly
- Make sure it starts with `https://`
- Check the Render logs for backend errors

### Wallet signing failing?

- Make sure you have Phantom wallet installed
- Make sure you're on a mobile device or have Phantom browser extension
- Check the on-page error message for specific details

### Build failed?

- Check the Render build logs
- Make sure `requirements.txt` is complete
- Make sure `Dockerfile` is in the repository root

## Monitoring

- View logs in the Render dashboard under **Logs** tab
- Check metrics under **Metrics** tab
- Set up alerts in Render for uptime monitoring

## Cost

- Render Free Tier: $0/month (sufficient for development and light usage)
- Paid plans start at $7/month for better performance and uptime

## Security Notes

- Never commit real secrets to your repository
- Always use environment variables for sensitive data
- Use `pk_test_` keys for development
- Only use `pk_live_` keys in production
- Keep your Render URL updated in `TELEGRAM_MINIAPP_URL`

## Support

If you encounter issues:
1. Check the Render logs
2. Review this guide
3. Check the Panta documentation: https://docs.panta.market
4. Check the Telegram Bot API documentation: https://core.telegram.org/bots/api
