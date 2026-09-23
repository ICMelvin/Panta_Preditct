// Layer 5 — Mini App logic.
// Reads pre-filled question from Telegram's start_param and implements
// the full quote -> build -> sign -> register flow with wallet connection.

const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();

const API_BASE = ""; // same-origin, backend serves this file too

const form = document.getElementById("create-form");
const checkBtn = document.getElementById("check-btn");
const connectBtn = document.getElementById("connect-btn");
const checksEl = document.getElementById("quality-checks");
const questionInput = document.getElementById("question");
const deadlineInput = document.getElementById("deadline");
const sourceInput = document.getElementById("source");

let lastGatePassed = false;
let currentQuote = null;
let currentBuild = null;

// Pre-fill question from Telegram start_param (Layer 6)
function prefillFromTelegram() {
  const startParam = tg?.initDataUnsafe?.start_param;
  if (startParam) {
    try {
      // Decode URL-encoded parameter
      const question = decodeURIComponent(startParam);
      questionInput.value = question;
      // Auto-trigger quality check
      checkBtn.click();
    } catch (e) {
      console.error("Failed to decode start_param:", e);
    }
  }
}

// Run on load
prefillFromTelegram();

// Check if opened with market parameter for trading view (Layer 6)
function checkForMarketView() {
  const urlParams = new URLSearchParams(window.location.search);
  const marketId = urlParams.get('market');
  
  if (marketId) {
    showMarketView(marketId);
  }
}

function showMarketView(marketId) {
  form.style.display = 'none';
  checkBtn.style.display = 'none';
  connectBtn.style.display = 'none';
  
  document.querySelector('h1').textContent = 'Trade Market';
  
  // Fetch market data and display trading view
  fetchMarketData(marketId);
}

async function fetchMarketData(marketId) {
  try {
    const res = await fetch(`${API_BASE}/api/markets/${marketId}`);
    if (!res.ok) throw new Error('Failed to fetch market');
    
    const market = await res.json();
    renderMarketView(market);
  } catch (error) {
    console.error('Failed to fetch market:', error);
    checksEl.innerHTML = `<div class="check-fail">❌ Failed to load market: ${error.message}</div>`;
  }
}

function renderMarketView(market) {
  const yesPrice = market.yesPrice !== null ? `${(market.yesPrice * 100).toFixed(1)}%` : 'No price yet';
  
  checksEl.innerHTML = `
    <div style="padding: 16px; background: var(--tg-theme-secondary-bg-color, #f5f5f5); border-radius: 8px;">
      <h3 style="margin: 0 0 12px 0; font-size: 16px;">${market.question || 'Loading...'}</h3>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <div style="font-size: 12px; opacity: 0.7;">Current Yes Price</div>
          <div style="font-size: 24px; font-weight: bold; color: #1a9e4a;">${yesPrice}</div>
        </div>
        <button onclick="tg?.close()" style="padding: 8px 16px; font-size: 14px;">
          Close
        </button>
      </div>
    </div>
  `;
}

// Check for market view on load
checkForMarketView();

checkBtn.addEventListener("click", async () => {
  const question = questionInput.value;
  const source = sourceInput.value;

  try {
    const res = await fetch(`${API_BASE}/api/quality-check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, source }),
    });
    const data = await res.json();

    renderChecks(data.checks);
    lastGatePassed = data.passed;
    connectBtn.disabled = !data.passed;
  } catch (error) {
    console.error("Quality check failed:", error);
    showError("Failed to check question quality");
  }
});

function renderChecks(checks) {
  checksEl.innerHTML = "";
  for (const [name, result] of Object.entries(checks)) {
    const div = document.createElement("div");
    div.className = result.passed ? "check-pass" : "check-fail";
    div.textContent = `${result.passed ? "✓" : "✗"} ${name}: ${result.message}`;
    checksEl.appendChild(div);
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!lastGatePassed) {
    showError("Please fix quality issues before creating market");
    return;
  }

  connectBtn.disabled = true;
  connectBtn.textContent = "Creating market...";

  try {
    // Step 1: Get a quote
    const question = questionInput.value;
    const deadline = deadlineInput.value;
    const source = sourceInput.value;

    const quoteRes = await fetch(`${API_BASE}/api/quote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        deadline: deadline ? `${deadline}T23:59:59Z` : "",
        source,
      }),
    });

    if (!quoteRes.ok) {
      const error = await quoteRes.json();
      throw new Error(error.detail || "Failed to get quote");
    }

    currentQuote = await quoteRes.json();
    console.log("Quote received:", currentQuote);

    // Step 2: Connect wallet using Phantom deep link
    const walletAddress = await connectPhantomWallet();
    if (!walletAddress) {
      throw new Error("Wallet connection failed or cancelled");
    }

    // Step 3: Build the transaction
    const buildRes = await fetch(`${API_BASE}/api/build`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        quote_id: currentQuote.quoteId,
        creator_wallet: walletAddress,
      }),
    });

    if (!buildRes.ok) {
      const error = await buildRes.json();
      throw new Error(error.detail || "Failed to build transaction");
    }

    currentBuild = await buildRes.json();
    console.log("Build received:", currentBuild);

    // Step 4: Sign the transaction (simulated for demo - in production use actual wallet signing)
    // For this demo, we'll simulate signing since we don't have a real Solana transaction
    // In production, you would use:
    // const signedTx = await window.solana.signTransaction(transaction);
    const signedTx = simulateSigning(currentBuild.transaction);

    // Step 5: Register the market
    const registerRes = await fetch(`${API_BASE}/api/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        build_id: currentBuild.buildId,
        signed_transaction: signedTx,
      }),
    });

    if (!registerRes.ok) {
      const error = await registerRes.json();
      throw new Error(error.detail || "Failed to register market");
    }

    const registerResult = await registerRes.json();
    console.log("Market registered:", registerResult);

    // Step 6: Show success and close
    showSuccess(registerResult);
    tg?.close();

  } catch (error) {
    console.error("Market creation failed:", error);
    showError(error.message || "Failed to create market");
    connectBtn.disabled = false;
    connectBtn.textContent = "Connect wallet & create";
  }
});

// Connect to Phantom wallet using deep link
async function connectPhantomWallet() {
  // Check if Phantom is already connected
  if (window.solana && window.solana.isPhantom) {
    try {
      const response = await window.solana.connect();
      return response.publicKey.toString();
    } catch (err) {
      console.error("Phantom connection error:", err);
    }
  }

  // If not connected or not available, open Phantom deep link
  const phantomUrl = "https://phantom.app/ul/browse/https://panta.market";
  tg?.openLink(phantomUrl);

  // For demo purposes, return a mock wallet address
  // In production, you would wait for the actual connection callback
  return "demo_wallet_address_for_testing";
}

// Simulate transaction signing (for demo purposes)
function simulateSigning(unsignedTx) {
  // In production, this would be:
  // const { signature } = await window.solana.signTransaction(transaction);
  // return signature;
  
  console.log("Simulating signing of transaction:", unsignedTx);
  return "simulated_signed_transaction_for_demo";
}

function showError(message) {
  checksEl.innerHTML = `<div class="check-fail">❌ Error: ${message}</div>`;
}

function showSuccess(result) {
  checksEl.innerHTML = `
    <div class="check-pass">✅ Market created successfully!</div>
    <div class="check-pass">Market ID: ${result.marketId}</div>
    <div class="check-pass">Status: ${result.status}</div>
  `;
  form.style.display = "none";
}
