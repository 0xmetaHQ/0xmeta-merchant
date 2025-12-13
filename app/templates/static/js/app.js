// ============================================================================
// GLOBAL STATE
// ============================================================================

let web3 = null;
let walletAddress = null;
let CONFIG = null;
let selectedCategory = null;
let isCustomCategory = false;

const OXMETA_FEE_USDC_WEI = 10000;
const OXMETA_FEE_USDC = 0.01;

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function $(selector) {
  return document.querySelector(selector);
}

function shorten(addr) {
  if (!addr) return "";
  return addr.slice(0, 6) + "..." + addr.slice(-4);
}

function isMetaMaskInstalled() {
  return typeof window.ethereum !== "undefined" && window.ethereum.isMetaMask;
}

// Add diagnostic logging
function logStep(step, data) {
  console.log(`[STEP ${step}]`, data);
}

// ============================================================================
// CONFIG LOADING
// ============================================================================

async function loadConfig() {
  try {
    logStep(1, "Loading configuration...");
    
    const response = await fetch("/api/config");
    if (!response.ok) {
      throw new Error(`Failed to fetch config: ${response.status}`);
    }

    CONFIG = await response.json();
    logStep(2, "Config loaded successfully");
    logStep(3, { 
      network: CONFIG.network,
      treasury: CONFIG.treasury_wallet,
      merchant: CONFIG.merchant_address,
      usdc: CONFIG.usdc_address
    });

    // Validate and convert
    if (!CONFIG.facilitator_base_url) {
      throw new Error("Missing facilitator_base_url");
    }

    CONFIG.price_usdc_wei = String(CONFIG.price_usdc_wei);
    CONFIG.total_price_usdc_wei = String(
      parseInt(CONFIG.price_usdc_wei) + OXMETA_FEE_USDC_WEI
    );
    CONFIG.total_price_usdc = (
      parseFloat(CONFIG.price_usdc) + OXMETA_FEE_USDC
    ).toFixed(2);

    logStep(4, "Config validated");
    return CONFIG;
  } catch (error) {
    console.error("❌ Config loading failed:", error);
    alert("❌ Failed to load configuration: " + error.message);
    return null;
  }
}

// ============================================================================
// CATEGORY SELECTION
// ============================================================================

function initializeCategorySelection() {
  const categoryGrid = $("#categoryGrid");
  if (!categoryGrid) {
    console.warn("⚠️ Category grid not found");
    return;
  }

  logStep(10, "Initializing category selection");

  categoryGrid.addEventListener("click", (e) => {
    const option = e.target.closest(".category-option");
    if (!option) return;

    const category = option.dataset.category;
    logStep(11, `Category clicked: ${category}`);

    if (category === "other") {
      openCustomCategoryModal();
      return;
    }

    selectCategory(category, false);
  });
}

function selectCategory(category, isCustom = false) {
  logStep(12, `Selecting category: ${category}, custom: ${isCustom}`);
  
  document.querySelectorAll(".category-option").forEach((el) => {
    el.classList.remove("selected");
  });

  if (!isCustom) {
    const selectedOption = document.querySelector(
      `.category-option[data-category="${category}"]`
    );
    if (selectedOption) {
      selectedOption.classList.add("selected");
    }
  } else {
    const otherOption = document.querySelector(
      `.category-option[data-category="other"]`
    );
    if (otherOption) {
      otherOption.classList.add("selected");
    }
  }

  selectedCategory = category;
  isCustomCategory = isCustom;

  logStep(13, `Category selected: ${category}`);

  const payBtn = $("#payBtn");
  if (payBtn && walletAddress) {
    payBtn.disabled = false;
    logStep(14, "Pay button enabled");
  }
}

// ============================================================================
// CUSTOM CATEGORY MODAL
// ============================================================================

function openCustomCategoryModal() {
  const modal = $("#customCategoryModal");
  if (!modal) return;

  modal.classList.add("active");
  const input = $("#customCategoryInput");
  if (input) {
    input.value = "";
    input.focus();
  }
}

function closeCustomCategoryModal() {
  const modal = $("#customCategoryModal");
  if (modal) {
    modal.classList.remove("active");
  }
}

function confirmCustomCategory() {
  const input = $("#customCategoryInput");
  if (!input) return;

  const customCategory = input.value.trim().toLowerCase();

  if (!customCategory) {
    alert("⚠️ Please enter a category name");
    return;
  }

  if (!/^[a-z0-9_-]+$/.test(customCategory)) {
    alert("⚠️ Category name can only contain letters, numbers, hyphens, and underscores");
    return;
  }

  selectCategory(customCategory, true);
  closeCustomCategoryModal();
}

function initializeCustomCategoryModal() {
  const closeBtn = $("#closeModal");
  const cancelBtn = $("#cancelCustomCategory");
  const confirmBtn = $("#confirmCustomCategory");
  const modal = $("#customCategoryModal");
  const input = $("#customCategoryInput");

  if (closeBtn) closeBtn.addEventListener("click", closeCustomCategoryModal);
  if (cancelBtn) cancelBtn.addEventListener("click", closeCustomCategoryModal);
  if (confirmBtn) confirmBtn.addEventListener("click", confirmCustomCategory);

  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeCustomCategoryModal();
    });
  }

  if (input) {
    input.addEventListener("keypress", (e) => {
      if (e.key === "Enter") confirmCustomCategory();
    });
  }
}

// ============================================================================
// WALLET CONNECTION
// ============================================================================

async function connectWallet() {
  try {
    logStep(20, "Starting wallet connection");
    
    if (!isMetaMaskInstalled()) {
      alert("❌ MetaMask not found. Please install it.");
      return;
    }

    if (!CONFIG) {
      logStep(21, "Config not loaded, loading now");
      CONFIG = await loadConfig();
      if (!CONFIG) return;
    }

    logStep(22, "Requesting MetaMask accounts");
    
    const accounts = await window.ethereum.request({
      method: "eth_requestAccounts",
    });

    if (!accounts || accounts.length === 0) {
      alert("❌ No accounts found");
      return;
    }

    walletAddress = accounts[0];
    logStep(23, `Wallet connected: ${shorten(walletAddress)}`);
    
    // Initialize Web3 AFTER getting the address
    web3 = new Web3(window.ethereum);
    logStep(24, "Web3 initialized");

    // Update UI
    const connectBtn = $("#connectBtn");
    const walletInfo = $("#walletInfo");
    const walletAddressEl = $("#walletAddress");
    const payBtn = $("#payBtn");

    if (connectBtn) connectBtn.style.display = "none";
    if (walletInfo) walletInfo.style.display = "flex";
    if (walletAddressEl) walletAddressEl.textContent = shorten(walletAddress);

    if (payBtn) {
      payBtn.style.display = "block";
      if (selectedCategory) {
        payBtn.disabled = false;
        logStep(25, "Pay button enabled (category already selected)");
      }
    }

    logStep(26, "Switching to correct network");
    await switchToNetwork();
    
    logStep(27, "Wallet connection complete");
  } catch (err) {
    console.error("❌ Wallet connection error:", err);
    alert("❌ Failed to connect: " + err.message);
  }
}

async function switchToNetwork() {
  if (!window.ethereum || !CONFIG) return;

  try {
    await window.ethereum.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: CONFIG.chain_id }],
    });
    logStep(28, `Switched to ${CONFIG.network}`);
  } catch (switchError) {
    if (switchError.code === 4902) {
      const networkParams = {
        chainId: CONFIG.chain_id,
        chainName: CONFIG.network === "base" ? "Base" : "Base Sepolia",
        nativeCurrency: { name: "ETH", symbol: "ETH", decimals: 18 },
        rpcUrls: [CONFIG.rpc_url],
        blockExplorerUrls: [CONFIG.block_explorer],
      };

      await window.ethereum.request({
        method: "wallet_addEthereumChain",
        params: [networkParams],
      });
    }
  }
}

// ============================================================================
// EIP-3009 AUTHORIZATION - WITH DIAGNOSTIC LOGGING
// ============================================================================

async function createEIP3009Authorization() {
  try {
    logStep(40, "Starting EIP-3009 authorization");
    
    if (!web3) {
      throw new Error("Web3 not initialized");
    }
    if (!walletAddress) {
      throw new Error("Wallet address not set");
    }
    if (!CONFIG) {
      throw new Error("Config not loaded");
    }

    logStep(41, "Checksumming addresses");
    
    // CRITICAL: Checksum ALL addresses
    const fromAddress = web3.utils.toChecksumAddress(walletAddress);
    const toAddress = web3.utils.toChecksumAddress(CONFIG.treasury_wallet);
    const tokenAddress = web3.utils.toChecksumAddress(CONFIG.usdc_address);

    logStep(42, {
      from: fromAddress,
      to: toAddress,
      token: tokenAddress,
    });

    logStep(43, "Creating USDC contract instance");
    
    const usdcContract = new web3.eth.Contract(
      [
        {
          constant: true,
          inputs: [],
          name: "name",
          outputs: [{ name: "", type: "string" }],
          type: "function",
        },
        {
          constant: true,
          inputs: [],
          name: "version",
          outputs: [{ name: "", type: "string" }],
          type: "function",
        },
      ],
      tokenAddress
    );

    logStep(44, "Fetching token metadata");
    
    const [tokenName, tokenVersion] = await Promise.all([
      usdcContract.methods.name().call(),
      usdcContract.methods.version().call(),
    ]);

    logStep(45, `Token: ${tokenName} v${tokenVersion}`);

    // Generate nonce
    const nonceBytes = new Uint8Array(32);
    window.crypto.getRandomValues(nonceBytes);
    const nonce =
      "0x" +
      Array.from(nonceBytes)
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");

    logStep(46, `Nonce generated: ${nonce.substring(0, 20)}...`);

    const domain = {
      name: tokenName,
      version: tokenVersion,
      chainId: parseInt(CONFIG.chain_id, 16),
      verifyingContract: tokenAddress,
    };

    const types = {
      TransferWithAuthorization: [
        { name: "from", type: "address" },
        { name: "to", type: "address" },
        { name: "value", type: "uint256" },
        { name: "validAfter", type: "uint256" },
        { name: "validBefore", type: "uint256" },
        { name: "nonce", type: "bytes32" },
      ],
    };

    const validAfter = "0";
    const validBefore = String(Math.floor(Date.now() / 1000) + 86400);

    const message = {
      from: fromAddress,
      to: toAddress,
      value: CONFIG.total_price_usdc_wei,
      validAfter: validAfter,
      validBefore: validBefore,
      nonce: nonce,
    };

    logStep(47, "Authorization message created");
    logStep(48, "Requesting signature from MetaMask");

    const signature = await window.ethereum.request({
      method: "eth_signTypedData_v4",
      params: [
        fromAddress,
        JSON.stringify({
          types: {
            EIP712Domain: [
              { name: "name", type: "string" },
              { name: "version", type: "string" },
              { name: "chainId", type: "uint256" },
              { name: "verifyingContract", type: "address" },
            ],
            TransferWithAuthorization: types.TransferWithAuthorization,
          },
          primaryType: "TransferWithAuthorization",
          domain: domain,
          message: message,
        }),
      ],
    });

    logStep(49, "Signature received");

    return {
      authorization: {
        from: fromAddress,
        to: toAddress,
        value: CONFIG.total_price_usdc_wei,
        validAfter: String(validAfter),
        validBefore: String(validBefore),
        nonce: nonce,
        token: tokenAddress,
      },
      signature: signature,
    };
  } catch (error) {
    console.error("❌ ERROR IN createEIP3009Authorization:", error);
    console.error("Error stack:", error.stack);
    throw error;
  }
}

// ============================================================================
// PAYMENT FLOW
// ============================================================================

async function initiatePayment() {
  try {
    logStep(50, "Payment initiated");
    
    if (!selectedCategory) {
      alert("❌ Please select a category first");
      return;
    }

    if (!walletAddress || !web3) {
      alert("❌ Connect wallet first");
      return;
    }

    if (!CONFIG) {
      CONFIG = await loadConfig();
      if (!CONFIG) return;
    }

    const payBtn = $("#payBtn");
    if (payBtn) {
      payBtn.disabled = true;
      payBtn.innerHTML = '<span class="spinner"></span> Processing...';
    }

    const paymentFlow = $("#paymentFlow");
    if (paymentFlow) {
      paymentFlow.classList.add("active");
    }

    updateFlowStep(1, "active", "🔐 Creating EIP-3009 authorization...");
    const { authorization, signature } = await createEIP3009Authorization();
    
    logStep(51, "Authorization created successfully");
    updateFlowStep(1, "completed", "✅ Authorization signed!");
    await delay(500);

    updateFlowStep(2, "active", "📦 Building X-Payment header...");
    await delay(800);

    const paymentPayload = {
      x402Version: 1,
      scheme: "exact",
      network: CONFIG.network,
      payload: {
        authorization: authorization,
        signature: signature,
      },
    };

    const xPaymentHeader = btoa(JSON.stringify(paymentPayload));
    updateFlowStep(2, "completed", "✅ Payment header created!");
    await delay(500);

    updateFlowStep(3, "active", "⚡ Verifying and settling payment...");
    logStep(52, `Fetching /news/${selectedCategory}`);

    const response = await fetch(`/news/${selectedCategory}`, {
      headers: {
        "X-Payment": xPaymentHeader,
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || "Payment verification failed");
    }

    const newsData = await response.json();
    logStep(53, "News data received");
    updateFlowStep(3, "completed", "✅ Payment settled successfully!");
    await delay(500);

    updateFlowStep(4, "active", "📰 Loading news...");
    await delay(500);
    displayNews(newsData);
    updateFlowStep(4, "completed", "✅ Enjoy your premium content!");

    setTimeout(() => {
      if (paymentFlow) {
        paymentFlow.style.display = "none";
      }
    }, 2000);
  } catch (error) {
    console.error("❌ PAYMENT ERROR:", error);
    console.error("Error stack:", error.stack);
    
    const flowMessage = $("#flowMessage");
    if (flowMessage) {
      flowMessage.innerHTML = `<span style="color: var(--error);">❌ ${error.message}</span>`;
    }

    const payBtn = $("#payBtn");
    if (payBtn && CONFIG) {
      payBtn.disabled = false;
      payBtn.innerHTML = "💰 Pay " + CONFIG.total_price_usdc + " USDC";
    }
  }
}

function updateFlowStep(step, status, message) {
  const stepEl = $(`#step${step}`);
  if (stepEl) {
    stepEl.className = `flow-step ${status}`;
  }

  const flowMessage = $("#flowMessage");
  if (flowMessage) {
    flowMessage.textContent = message;
  }
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ============================================================================
// NEWS DISPLAY
// ============================================================================

function displayNews(data) {
  const newsContent = $("#newsContent");
  if (!newsContent) return;

  const newsItems = data.cryptonews || [];
  const twitterItems = data.twitter || [];
  const allItems = [...newsItems, ...twitterItems];

  if (allItems.length === 0) {
    newsContent.innerHTML =
      '<p style="text-align: center; color: var(--text-secondary);">No news found for this category.</p>';
    newsContent.style.display = "block";
    return;
  }

  allItems.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));

  const html = allItems
    .slice(0, 20)
    .map(
      (item) => `
    <div class="news-item">
      <span class="news-source ${item.source}">${item.source}</span>
      <h3 class="news-title">${
        item.title || item.text.substring(0, 100) + "..."
      }</h3>
      <p class="news-text">${
        (item.long_context || item.text || item.short_context || "").substring(
          0,
          200
        ) + "..."
      }</p>
      <div class="news-meta">
        <span>${new Date(item.timestamp * 1000).toLocaleString()}</span>
        ${
          item.tokens && item.tokens.length > 0
            ? `
          <div>
            ${item.tokens
              .slice(0, 3)
              .map((token) => `<span class="token-tag">${token}</span>`)
              .join("")}
          </div>
        `
            : ""
        }
      </div>
    </div>
  `
    )
    .join("");

  newsContent.innerHTML = `<div class="news-grid">${html}</div>`;
  newsContent.style.display = "block";
}

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener("DOMContentLoaded", async () => {
  console.log("========================================");
  console.log("0xMeta News App - Diagnostic Version");
  console.log("========================================");
  
  logStep(0, "DOM loaded, initializing app");

  await loadConfig();

  initializeCategorySelection();
  initializeCustomCategoryModal();

  if (!isMetaMaskInstalled()) {
    console.warn("⚠️ MetaMask not installed");
    alert("❌ MetaMask not found. Please install it.");
    const connectBtn = $("#connectBtn");
    if (connectBtn) connectBtn.disabled = true;
  }

  const connectBtn = $("#connectBtn");
  if (connectBtn) {
    connectBtn.addEventListener("click", connectWallet);
    logStep(100, "Connect button bound");
  }

  const payBtn = $("#payBtn");
  if (payBtn) {
    payBtn.addEventListener("click", initiatePayment);
    logStep(101, "Pay button bound");
  }

  if (isMetaMaskInstalled()) {
    window.ethereum.on("accountsChanged", (accounts) => {
      if (accounts.length === 0) {
        walletAddress = null;
        const connectBtn = $("#connectBtn");
        const walletInfo = $("#walletInfo");
        if (connectBtn) connectBtn.style.display = "block";
        if (walletInfo) walletInfo.style.display = "none";
      } else {
        walletAddress = accounts[0];
        const walletAddressEl = $("#walletAddress");
        if (walletAddressEl) {
          walletAddressEl.textContent = shorten(walletAddress);
        }
      }
    });

    window.ethereum.on("chainChanged", () => {
      window.location.reload();
    });
  }

  logStep(102, "App initialization complete");
});

window.connectWallet = connectWallet;
window.initiatePayment = initiatePayment;