// Layer 5 — Mini App logic.
// Robust error handling and optional dependencies

const tg = window.Telegram?.WebApp;
const API_BASE = ""; // same-origin, backend serves this file too

// DOM elements - get them first
const form = document.getElementById("create-form");
const checkBtn = document.getElementById("check-btn");
const connectBtn = document.getElementById("connect-btn");
const checksEl = document.getElementById("quality-checks");
const categorySelect = document.getElementById("category");
const imageSelect = document.getElementById("image_select");
const imageUrlInput = document.getElementById("image_url");
const marketView = document.getElementById("market-view");
const marketDetails = document.getElementById("market-details");
const backBtn = document.getElementById("back-btn");

// State
let lastGatePassed = false;
let currentCreateId = null;
let connectedWallet = null;
let categories = [];

// Error tracking
const errors = [];
let debugMode = false;

// Global error handlers
window.onerror = function(message, source, lineno, colno, error) {
  const errorInfo = `${message} (${source}:${lineno})`;
  errors.push(errorInfo);
  showErrorBanner(errorInfo);
  if (debugMode) updateDebugPanel();
  console.error(error);
};

window.addEventListener('unhandledrejection', function(event) {
  const errorInfo = `Promise rejected: ${event.reason}`;
  errors.push(errorInfo);
  showErrorBanner(errorInfo);
  if (debugMode) updateDebugPanel();
  console.error(event.reason);
});

// Show error banner
function showErrorBanner(message) {
  let banner = document.getElementById('error-banner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'error-banner';
    banner.style.cssText = 'background: #fee; color: #c33; padding: 10px; margin: 10px 0; border: 1px solid #c33; display: none;';
    document.body.insertBefore(banner, document.body.firstChild);
  }
  banner.textContent = `Error: ${message}`;
  banner.style.display = 'block';
}

// Update debug panel
function updateDebugPanel() {
  let panel = document.getElementById('debug-panel');
  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'debug-panel';
    panel.style.cssText = 'position: fixed; bottom: 0; right: 0; background: #333; color: #fff; padding: 10px; max-width: 300px; max-height: 200px; overflow-y: auto; font-size: 12px; z-index: 9999;';
    document.body.appendChild(panel);
  }

  let html = '<strong>Debug Panel</strong><br>';
  html += `API Base: ${API_BASE}<br>`;
  html += `Errors (${errors.length}):<br>`;
  errors.slice(-5).forEach(err => {
    html += `- ${err}<br>`;
  });
  html += `<br>Categories: ${categories.join(', ')}`;
  panel.innerHTML = html;
}

// Attach DOM event listeners FIRST (before any optional work)
checkBtn.addEventListener("click", async () => {
  const question = document.getElementById("question").value;
  const sourcesText = document.getElementById("sources_of_truth").value;
  const sources = sourcesText.split('\n').map(s => s.trim()).filter(s => s.length > 0);

  try {
    const res = await fetch(`${API_BASE}/api/quality-check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        resolution_rule: document.getElementById("resolution_rule").value,
        sources_of_truth: sources,
      }),
    });
    const data = await res.json();

    renderChecks(data.checks);
    lastGatePassed = data.passed;
    connectBtn.disabled = !data.passed;
  } catch (error) {
    showErrorBanner(`Quality check failed: ${error.message}`);
    console.error("Quality check error:", error);
  }
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!lastGatePassed) return;

  try {
    connectBtn.disabled = true;
    connectBtn.textContent = "Creating market...";

    // 1. Get a quote from POST /api/quote
    const question = document.getElementById("question").value;
    const resolutionRule = document.getElementById("resolution_rule").value;
    const sourcesText = document.getElementById("sources_of_truth").value;
    const sourcesOfTruth = sourcesText.split('\n').map(s => s.trim()).filter(s => s.length > 0);
    const category = document.getElementById("category").value;
    const imageUrl = imageUrlInput.value || imageSelect.value || null;
    const endDate = document.getElementById("end_date").value;
    const resolutionDate = document.getElementById("resolution_date").value;

    // Convert dates to unix timestamps
    const endTime = new Date(endDate).getTime() / 1000;
    const resolutionTime = new Date(resolutionDate).getTime() / 1000;
    const startTime = Math.floor(Date.now() / 1000);

    const quoteRes = await fetch(`${API_BASE}/api/quote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        resolution_rule: resolutionRule,
        sources_of_truth: sourcesOfTruth,
        category,
        image_url: imageUrl,
        start_time: startTime,
        end_time: endTime,
        resolution_time: resolutionTime,
      }),
    });

    if (!quoteRes.ok) {
      const error = await quoteRes.json();
      throw new Error(error.detail || "Quote request failed");
    }

    const quoteData = await quoteRes.json();
    currentCreateId = quoteData.createId;

    // 2. Connect wallet using Phantom deep link
    if (!window.solana || !window.solana.isPhantom) {
      // Open Phantom deep link if wallet not connected
      const dappUrl = window.location.href;
      const phantomLink = `https://phantom.app/ul/browse/${encodeURIComponent(dappUrl)}?ref=${encodeURIComponent(dappUrl)}`;
      window.open(phantomLink, "_blank");
      throw new Error("Phantom wallet not connected. Please install Phantom, connect it, and try again.");
    }

    let resp;
    try {
      resp = await window.solana.connect();
    } catch (connectError) {
      throw new Error("Wallet connection cancelled or failed. Please connect your Phantom wallet and try again.");
    }
    connectedWallet = resp.publicKey.toString();

    // 3. Call POST /api/build with the connected wallet address
    const buildRes = await fetch(`${API_BASE}/api/build`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        create_id: currentCreateId,
        wallet: connectedWallet,
      }),
    });

    if (!buildRes.ok) {
      const error = await buildRes.json();
      throw new Error(error.detail || "Build request failed");
    }

    const buildData = await buildRes.json();

    // 4. Have the wallet sign the returned unsigned transaction
    // Note: The transaction is base64 encoded from Panta
    if (!buildData.transaction) {
      throw new Error("No transaction returned from build step");
    }

    // Decode base64 transaction
    const transactionBytes = Uint8Array.from(atob(buildData.transaction), c => c.charCodeAt(0));

    // Sign using Phantom's signTransaction method
    const signedTransaction = await window.solana.signTransaction(transactionBytes);
    const signature = bs58.encode(signedTransaction.signature);

    // 5. Call POST /api/register with the signature
    const registerRes = await fetch(`${API_BASE}/api/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        create_id: currentCreateId,
        signature: signature,
      }),
    });

    if (!registerRes.ok) {
      const error = await registerRes.json();
      throw new Error(error.detail || "Register request failed");
    }

    const registerData = await registerRes.json();

    // 6. Show confirmation
    alert(`Market created successfully!\n\nCreate ID: ${currentCreateId}\nWallet: ${connectedWallet}\n\nUse /trade ${currentCreateId} in Telegram to view market details.`);

    tg?.close();

  } catch (error) {
    console.error("Market creation failed:", error);
    let errorMessage = error.message;
    
    // Provide more specific error messages for common failures
    if (error.message.includes("Phantom wallet not connected")) {
      errorMessage = "Phantom wallet not connected. Please install Phantom wallet, connect it, and try again.";
    } else if (error.message.includes("Wallet connection cancelled")) {
      errorMessage = "Wallet connection was cancelled. Please connect your Phantom wallet and try again.";
    } else if (error.message.includes("signTransaction")) {
      errorMessage = "Transaction signing failed. Please approve the transaction in your wallet and try again.";
    } else if (error.message.includes("No transaction returned")) {
      errorMessage = "No transaction was returned from the build step. Please try again.";
    }
    
    showErrorBanner(`Error: ${errorMessage}`);
    connectBtn.disabled = false;
    connectBtn.textContent = "Connect wallet & create";
  }
});

// Handle image selection dropdown
imageSelect.addEventListener("change", () => {
  if (imageSelect.value) {
    imageUrlInput.value = imageSelect.value;
  }
});

// Handle back button
backBtn.addEventListener("click", () => {
  marketView.hidden = true;
  form.hidden = false;
});

// Helper functions
function renderChecks(checks) {
  checksEl.innerHTML = "";
  for (const [name, result] of Object.entries(checks)) {
    const div = document.createElement("div");
    div.className = result.passed ? "check-pass" : "check-fail";
    div.textContent = `${result.passed ? "✓" : "✗"} ${name}: ${result.message}`;
    checksEl.appendChild(div);
  }
}

// Load categories from API
async function loadCategories() {
  try {
    const res = await fetch(`${API_BASE}/api/categories`);
    if (res.ok) {
      categories = await res.json();
      // Clear existing options except the default
      categorySelect.innerHTML = '<option value="">Select a category</option>';
      // Add categories from API
      categories.forEach(cat => {
        const option = document.createElement("option");
        option.value = cat;
        option.textContent = cat.charAt(0).toUpperCase() + cat.slice(1); // Capitalize
        categorySelect.appendChild(option);
      });
    }
  } catch (error) {
    console.error("Failed to load categories:", error);
    // Fallback to hardcoded categories if API fails
    categorySelect.innerHTML = `
      <option value="">Select a category</option>
      <option value="crypto">Crypto</option>
    `;
    categories = ["crypto"];
  }
}

// Load market details for trading view
async function loadMarketDetails(marketId) {
  try {
    const res = await fetch(`${API_BASE}/api/markets/${marketId}`);
    if (res.ok) {
      const market = await res.json();
      // Handle null price fields
      const yesPrice = market.yesPrice || market.primaryYesPrice;
      const noPrice = market.noPrice || market.primaryNoPrice;
      const priceText = yesPrice ? `Yes: ${yesPrice} | No: ${noPrice}` : "No live price yet";

      marketDetails.innerHTML = `
        <p><strong>Question:</strong> <span id="market-question"></span></p>
        <p><strong>Price:</strong> ${priceText}</p>
        <p><strong>Category:</strong> ${market.category || "N/A"}</p>
        <p><strong>End Time:</strong> ${market.endTime || "N/A"}</p>
        <p><strong>Status:</strong> ${market.status || "Unknown"}</p>
      `;
      // Use textContent for user-provided question to prevent XSS
      const questionSpan = document.getElementById("market-question");
      if (questionSpan) {
        questionSpan.textContent = market.question || "Unknown";
      }
    } else {
      marketDetails.innerHTML = "<p>Error loading market details</p>";
    }
  } catch (error) {
    console.error("Failed to load market details:", error);
    marketDetails.innerHTML = "<p>Error loading market details</p>";
  }
}

// Optional Telegram WebApp initialization (safe)
function initTelegram() {
  try {
    if (tg) {
      tg.ready();
      tg.expand();
    }
  } catch (error) {
    console.warn("Telegram WebApp initialization failed:", error);
  }
}

// Initialize app
function initApp() {
  // Attach DOM listeners first (already done above)

  // Load categories
  loadCategories();

  // Pre-fill question from Telegram start_param or URL parameter
  const urlParams = new URLSearchParams(window.location.search);
  const questionParam = urlParams.get('q');

  if (questionParam) {
    // URLSearchParams automatically decodes, use .value to prevent XSS
    document.getElementById("question").value = questionParam;
  } else if (tg?.initDataUnsafe?.start_param) {
    // Fallback to Telegram's start_param (not URL-encoded)
    document.getElementById("question").value = tg.initDataUnsafe.start_param;
  }

  // Check if opened via trade button (market parameter)
  const marketId = urlParams.get('market');

  if (marketId) {
    // URLSearchParams automatically decodes
    // Show market view instead of create form
    form.hidden = true;
    marketView.hidden = false;
    loadMarketDetails(marketId);
  }

  // Initialize Telegram WebApp (optional)
  initTelegram();

  // Show debug panel if in debug mode
  if (debugMode) {
    updateDebugPanel();
  }
}

// Check for debug mode
const urlParams = new URLSearchParams(window.location.search);
debugMode = urlParams.has('debug');

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}
