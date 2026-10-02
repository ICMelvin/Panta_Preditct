const bs58 = (() => {
  const ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
  function encode(bytes) {
    if (bytes.length === 0) return '';
    let digits = [0];
    for (let i = 0; i < bytes.length; i++) {
      let carry = bytes[i];
      for (let j = 0; j < digits.length; j++) {
        carry += digits[j] << 8;
        digits[j] = carry % 58;
        carry = (carry / 58) | 0;
      }
      while (carry > 0) {
        digits.push(carry % 58);
        carry = (carry / 58) | 0;
      }
    }
    let result = '';
    for (let i = 0; bytes[i] === 0 && i < bytes.length - 1; i++) result += '1';
    for (let i = digits.length - 1; i >= 0; i--) result += ALPHABET[digits[i]];
    return result;
  }
  return { encode };
})();

// Layer 5 — Mini App logic
// Complete rebuild with landing page, persistent nav, and wallet-gated flow

const tg = window.Telegram?.WebApp;
const API_BASE = ""; // same-origin, backend serves this file too

// State
let connectedWallet = null;
let categories = [];
let lastGatePassed = false;
let currentCreateId = null;

// Error tracking
const errors = [];
let debugMode = false;

// DOM elements
const navBar = document.getElementById("nav-bar");
const walletBtn = document.getElementById("wallet-btn");
const walletText = document.getElementById("wallet-text");
const walletIndicator = document.getElementById("wallet-indicator");
const walletDropdown = document.getElementById("wallet-dropdown");
const disconnectBtn = document.getElementById("disconnect-btn");
const landingPage = document.getElementById("landing-page");
const formPage = document.getElementById("form-page");
const marketView = document.getElementById("market-view");
const landingConnectBtn = document.getElementById("landing-connect-btn");
const form = document.getElementById("create-form");
const checkBtn = document.getElementById("check-btn");
const connectBtn = document.getElementById("connect-btn");
const checksEl = document.getElementById("quality-checks");
const categorySelect = document.getElementById("category");
const imageSelect = document.getElementById("image_select");
const imageUrlInput = document.getElementById("image_url");
const marketDetails = document.getElementById("market-details");
const backBtn = document.getElementById("back-btn");
const loadingOverlay = document.getElementById("loading-overlay");
const loadingText = document.getElementById("loading-text");
const toastContainer = document.getElementById("toast-container");

// Global error handlers
window.onerror = function(message, source, lineno, colno, error) {
  const errorInfo = `${message} (${source}:${lineno})`;
  errors.push(errorInfo);
  showToast(errorInfo, "error");
  if (debugMode) updateDebugPanel();
  console.error(error);
};

window.addEventListener('unhandledrejection', function(event) {
  const errorInfo = `Promise rejected: ${event.reason}`;
  errors.push(errorInfo);
  showToast(errorInfo, "error");
  if (debugMode) updateDebugPanel();
  console.error(event.reason);
});

// Toast notifications
function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);
  
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Loading overlay
function showLoading(text = "Loading...") {
  loadingText.textContent = text;
  loadingOverlay.classList.remove("hidden");
}

function hideLoading() {
  loadingOverlay.classList.add("hidden");
}

// Debug panel
function updateDebugPanel() {
  let panel = document.getElementById('debug-panel');
  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'debug-panel';
    document.body.appendChild(panel);
  }

  let html = '<strong>Debug Panel</strong><br>';
  html += `Wallet: ${connectedWallet || 'Not connected'}<br>`;
  html += `Errors (${errors.length}):<br>`;
  errors.slice(-5).forEach(err => {
    html += `- ${err}<br>`;
  });
  html += `<br>Categories: ${categories.join(', ')}`;
  panel.innerHTML = html;
}

// Detect if we're on mobile
function isMobile() {
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

function isSessionStartParam(value) {
  if (!value) return false;
  return value.startsWith('session_') || /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$/.test(value);
}

// Phantom deep-link connection for mobile using backend-mediated flow
async function connectPhantomDeepLink() {
  try {
    showLoading("Initializing wallet connection...");
    
    // Check if required libraries are loaded
    if (typeof solanaWeb3 === 'undefined') {
      throw new Error("Solana web3.js library not loaded. Check CDN.");
    }
    if (typeof bs58 === 'undefined') {
      throw new Error("bs58 library not loaded. Check CDN.");
    }
    
    // Generate ephemeral keypair for session encryption
    console.log("Generating ephemeral keypair...");
    const dappKeyPair = nacl.box.keyPair();
    console.log("Keypair generated:", dappKeyPair);
    
    const dappPublicKey = bs58.encode(dappKeyPair.publicKey);
    console.log("Public key:", dappPublicKey);
    
    // Solana secretKey is 64 bytes (32-byte private key + 32-byte public key)
    // PyNaCl expects only the 32-byte private key, so slice to first 32 bytes
    const dappSecretKey = bs58.encode(dappKeyPair.secretKey);
    console.log("Secret key encoded (first 32 bytes):", dappSecretKey.substring(0, 10) + "...");
    
    // Initialize wallet session on backend with both public and secret key
    console.log("Calling /api/wallet-session-init...");
    const initRes = await fetch(`${API_BASE}/api/wallet-session-init`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dapp_encryption_public_key: dappPublicKey,
        dapp_secret_key: dappSecretKey
      }),
    });
    
    console.log("Response status:", initRes.status);
    
    if (!initRes.ok) {
      const errorText = await initRes.text();
      console.error("Backend error:", errorText);
      throw new Error(`Backend returned ${initRes.status}: ${errorText}`);
    }
    
    const { session_id } = await initRes.json();
    console.log("Session initialized:", session_id);
    
    // Store session_id in localStorage for later retrieval
    localStorage.setItem('phantom_session_id', session_id);
    
    // Get current URL for redirect
    const currentUrl = window.location.href.split('?')[0]; // Remove existing params
    
    // Build Phantom deep link URL with session_id in redirect_link
    // Phantom will redirect to our backend callback page with this session_id
    const callbackUrl = `${currentUrl.replace(/\/$/, '')}/wallet-callback?session_id=${session_id}`;
    const phantomUrl = `https://phantom.app/ul/v1/connect?app_url=${encodeURIComponent(currentUrl)}&dapp_encryption_public_key=${dappPublicKey}&redirect_link=${encodeURIComponent(callbackUrl)}&cluster=mainnet-beta`;
    
    console.log("Opening Phantom deep link...");
    
    // Open Phantom deep link using Telegram's openLink method
    hideLoading();
    if (tg && tg.openLink) {
      tg.openLink(phantomUrl);
    } else {
      // Fallback to window.location.href if Telegram WebApp not available
      window.location.href = phantomUrl;
    }
  } catch (error) {
    console.error("Phantom deep-link connection failed:", error);
    hideLoading();
    showToast(`Failed to initialize wallet connection: ${error.message}`, "error");
  }
}

// Wallet connection
async function connectWallet() {
  // Try window.solana first (desktop extension)
  if (window.solana && window.solana.isPhantom) {
    try {
      showLoading("Connecting wallet...");
      const resp = await window.solana.connect();
      connectedWallet = resp.publicKey.toString();
      updateWalletUI();
      showLanding(false);
      showToast("Wallet connected successfully!", "success");
      return;
    } catch (error) {
      console.error("Wallet connection failed:", error);
      showToast(`Wallet connection failed: ${error.message}`, "error");
      hideLoading();
      return;
    }
  }
  
  // Fall back to deep-link for mobile
  if (isMobile()) {
    showToast("Opening Phantom wallet...", "info");
    connectPhantomDeepLink();
    return;
  }
  
  // Neither extension nor mobile - show error
  showToast("Phantom wallet not detected. Please install Phantom wallet extension on desktop or Phantom app on mobile.", "error");
}

function disconnectWallet() {
  connectedWallet = null;
  updateWalletUI();
  walletDropdown.classList.add("hidden");
  showLanding(true);
  showToast("Wallet disconnected", "info");
}

function updateWalletUI() {
  if (connectedWallet) {
    // Truncate address
    const truncated = `${connectedWallet.slice(0, 4)}...${connectedWallet.slice(-4)}`;
    walletText.textContent = truncated;
    walletBtn.classList.add("connected");
    walletIndicator.style.opacity = "1";
  } else {
    walletText.textContent = "Connect Wallet";
    walletBtn.classList.remove("connected");
    walletIndicator.style.opacity = "0";
  }
}

// Navigation
function showLanding(show) {
  if (show) {
    landingPage.classList.remove("hidden");
    formPage.classList.add("hidden");
    marketView.classList.add("hidden");
  } else {
    landingPage.classList.add("hidden");
    formPage.classList.remove("hidden");
    marketView.classList.add("hidden");
  }
}

function showMarketView() {
  landingPage.classList.add("hidden");
  formPage.classList.add("hidden");
  marketView.classList.remove("hidden");
}

// Attach DOM event listeners
landingConnectBtn.addEventListener("click", connectWallet);
walletBtn.addEventListener("click", () => {
  if (connectedWallet) {
    walletDropdown.classList.toggle("hidden");
  } else {
    connectWallet();
  }
});
disconnectBtn.addEventListener("click", disconnectWallet);

// Close dropdown when clicking outside
document.addEventListener("click", (e) => {
  if (!walletBtn.contains(e.target) && !walletDropdown.contains(e.target)) {
    walletDropdown.classList.add("hidden");
  }
});

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
    
    if (data.passed) {
      showToast("Quality checks passed! You can now create the market.", "success");
    } else {
      showToast("Quality checks failed. Please fix the issues above.", "error");
    }
  } catch (error) {
    showToast(`Quality check failed: ${error.message}`, "error");
    console.error("Quality check error:", error);
  }
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!lastGatePassed) {
    showToast("Please pass quality checks first", "error");
    return;
  }

  if (!connectedWallet) {
    showToast("Please connect your wallet first", "error");
    return;
  }

  try {
    connectBtn.disabled = true;
    connectBtn.textContent = "Creating market...";
    showLoading("Creating market...");

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

    // 2. Call POST /api/build with the already-connected wallet
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

    // 3. Have the wallet sign the returned unsigned transaction
    if (!buildData.transaction) {
      throw new Error("No transaction returned from build step");
    }

    // Decode base64 transaction
    const transactionBytes = Uint8Array.from(atob(buildData.transaction), c => c.charCodeAt(0));

    // Sign using Phantom's signTransaction method
    const signedTransaction = await window.solana.signTransaction(transactionBytes);
    const signature = bs58.encode(signedTransaction.signature);

    // 4. Call POST /api/register with the signature
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

    // 5. Show success
    showToast(`Market created successfully! Create ID: ${currentCreateId}`, "success");
    tg?.close();

  } catch (error) {
    console.error("Market creation failed:", error);
    let errorMessage = error.message;
    
    // Provide specific error messages
    if (error.message.includes("signTransaction")) {
      errorMessage = "Transaction signing failed. Please approve the transaction in your wallet.";
    } else if (error.message.includes("No transaction")) {
      errorMessage = "No transaction was returned from the build step. Please try again.";
    }
    
    showToast(`Error: ${errorMessage}`, "error");
    connectBtn.disabled = false;
    connectBtn.textContent = "Create Market";
  } finally {
    hideLoading();
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
  showLanding(false);
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
      categorySelect.innerHTML = '<option value="">Select a category</option>';
      categories.forEach(cat => {
        const option = document.createElement("option");
        option.value = cat;
        option.textContent = cat.charAt(0).toUpperCase() + cat.slice(1);
        categorySelect.appendChild(option);
      });
    }
  } catch (error) {
    console.error("Failed to load categories:", error);
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

// Initialize app
async function initApp() {
  // Check for debug mode
  const urlParams = new URLSearchParams(window.location.search);
  debugMode = urlParams.has('debug');

  // Check for wallet session from start_param (returning from Phantom connection)
  const startParam = tg?.initDataUnsafe?.start_param || urlParams.get('tgWebAppStartParam');
  if (startParam && isSessionStartParam(startParam)) {
    // Query backend for wallet session
    try {
      showLoading("Checking wallet connection...");
      const sessionRes = await fetch(`${API_BASE}/api/wallet-session/${startParam}`);
      if (sessionRes.ok) {
        const sessionData = await sessionRes.json();
        if (sessionData.wallet_address && !sessionData.expired) {
          connectedWallet = sessionData.wallet_address;
          updateWalletUI();
          showLanding(false);
          showToast("Wallet connected!", "success");
        } else {
          showToast("Wallet session expired or not found. Please connect again.", "error");
        }
      }
      hideLoading();
    } catch (error) {
      console.error("Failed to fetch wallet session:", error);
      hideLoading();
      showToast(`Failed to check wallet connection: ${error.message}`, "error");
    }
  }

  // Load categories
  loadCategories();

  // Check if wallet is already connected ( Phantom persists session)
  if (window.solana && window.solana.isPhantom) {
    window.solana.connect({ onlyIfTrusted: false }).then(resp => {
      if (resp) {
        connectedWallet = resp.publicKey.toString();
        updateWalletUI();
        showLanding(false);
      }
    }).catch(() => {
      // Not connected, show landing
      showLanding(true);
      
    });
  } else {
    showLanding(true);
  }

  // Pre-fill question from Telegram start_param or URL parameter
  const questionParam = urlParams.get('q');
  if (questionParam) {
    document.getElementById("question").value = questionParam;
  } else if (tg?.initDataUnsafe?.start_param && !isSessionStartParam(tg.initDataUnsafe.start_param)) {
    document.getElementById("question").value = tg.initDataUnsafe.start_param;
  }

  // Check if opened via trade button (market parameter)
  const marketId = urlParams.get('market');
  if (marketId) {
    showMarketView();
    loadMarketDetails(marketId);
  }

  // Initialize Telegram WebApp (optional)
  try {
    if (tg) {
      tg.ready();
      tg.expand();
    }
  } catch (error) {
    console.warn("Telegram WebApp initialization failed:", error);
  }

  // Show debug panel if in debug mode
  if (debugMode) {
    updateDebugPanel();
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => initApp());
} else {
  initApp();
}
