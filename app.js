const SETTINGS_KEY = "shitcoin-scanner-settings";
const HIT_LOG_KEY = "shitcoin-hit-log";
const TOKEN_STATE_KEY = "shitcoin-token-state";
const DEFAULT_MARKET_CAP_THRESHOLD = 150000;
const DEFAULT_SCAN_INTERVAL_SECONDS = 30;
const DEFAULT_HOLD_MINUTES = 5;
const DEFAULT_TELEGRAM_BOT_TOKEN = "";
const DEFAULT_TELEGRAM_CHAT_ID = "";
const DEFAULT_CHAIN_IDS = ["solana", "base", "bsc"];
const MIN_LIQUIDITY_USD = 500;
const MIN_VOLUME_24H_USD = 1000;
const MIN_TRANSACTIONS_24H = 25;
const MIN_PAIR_AGE_MS = 10 * 60 * 1000;
const MIN_LIQUIDITY_TO_MCAP_RATIO = 0.015;
const AUTO_DISCOVERY_LIMIT = 80;
const PREVIEW_LIMIT = 24;
const TWENTY_FOUR_HOURS_MS = 24 * 60 * 60 * 1000;
const CHAIN_OPTIONS = {
  solana: {
    label: "Solana",
    dexScreenerPath: "solana",
  },
  base: {
    label: "Base",
    dexScreenerPath: "base",
    swapLabel: "Uniswap",
    swapUrl: (item) => `https://app.uniswap.org/#/swap?chain=base&outputCurrency=${item.tokenAddress}`,
  },
  bsc: {
    label: "BSC / PancakeSwap",
    dexScreenerPath: "bsc",
    swapLabel: "PancakeSwap",
    swapUrl: (item) => `https://pancakeswap.finance/swap?chain=bsc&outputCurrency=${item.tokenAddress}`,
  },
};

const state = {
  settings: loadSettings(),
  hitLog: loadJson(HIT_LOG_KEY, []),
  tokenState: loadJson(TOKEN_STATE_KEY, {}),
  previewItems: [],
  timerId: null,
};

const elements = {
  settingsForm: document.getElementById("settings-form"),
  threshold: document.getElementById("threshold"),
  interval: document.getElementById("interval"),
  holdMinutes: document.getElementById("hold-minutes"),
  chainCheckboxes: [...document.querySelectorAll("[data-chain-id]")],
  telegramBotToken: document.getElementById("telegram-bot-token"),
  telegramChatId: document.getElementById("telegram-chat-id"),
  permissionState: document.getElementById("permission-state"),
  permissionButton: document.getElementById("permission-button"),
  pollingState: document.getElementById("polling-state"),
  lastUpdated: document.getElementById("last-updated"),
  sourceState: document.getElementById("source-state"),
  resetButton: document.getElementById("reset-button"),
  hitLogEmpty: document.getElementById("hit-log-empty"),
  hitLogList: document.getElementById("hit-log-list"),
  hitLogTemplate: document.getElementById("hit-card-template"),
  previewButton: document.getElementById("preview-button"),
  previewStatus: document.getElementById("preview-status"),
  previewEmpty: document.getElementById("preview-empty"),
  previewList: document.getElementById("preview-list"),
  previewTemplate: document.getElementById("preview-card-template"),
};

init();

function init() {
  elements.settingsForm.addEventListener("submit", handleSettingsSubmit);
  elements.permissionButton.addEventListener("click", requestNotificationPermission);
  elements.previewButton.addEventListener("click", loadPreview);
  elements.resetButton.addEventListener("click", resetScannerData);

  hydrateSettingsForm();
  render();
  syncNotificationState();
  scheduleScanning();
  refreshScanner();
}

function loadJson(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch (error) {
    console.error(`Failed to parse ${key}`, error);
    return fallback;
  }
}

function loadSettings() {
  return {
    threshold: DEFAULT_MARKET_CAP_THRESHOLD,
    intervalSeconds: DEFAULT_SCAN_INTERVAL_SECONDS,
    holdMinutes: DEFAULT_HOLD_MINUTES,
    telegramBotToken: DEFAULT_TELEGRAM_BOT_TOKEN,
    telegramChatId: DEFAULT_TELEGRAM_CHAT_ID,
    chainIds: DEFAULT_CHAIN_IDS,
    ...loadJson(SETTINGS_KEY, {}),
  };
}

function saveJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function hydrateSettingsForm() {
  elements.threshold.value = state.settings.threshold;
  elements.interval.value = String(state.settings.intervalSeconds);
  elements.holdMinutes.value = String(state.settings.holdMinutes);
  elements.telegramBotToken.value = state.settings.telegramBotToken || "";
  elements.telegramChatId.value = state.settings.telegramChatId || "";
  elements.chainCheckboxes.forEach((checkbox) => {
    checkbox.checked = getEnabledChainIds().includes(checkbox.dataset.chainId);
  });
}

function handleSettingsSubmit(event) {
  event.preventDefault();

  const previousThreshold = state.settings.threshold;
  state.settings.threshold = Number(elements.threshold.value) || DEFAULT_MARKET_CAP_THRESHOLD;
  state.settings.intervalSeconds = Number(elements.interval.value) || DEFAULT_SCAN_INTERVAL_SECONDS;
  state.settings.holdMinutes = Math.max(0, Number(elements.holdMinutes.value) || DEFAULT_HOLD_MINUTES);
  state.settings.telegramBotToken = elements.telegramBotToken.value.trim();
  state.settings.telegramChatId = elements.telegramChatId.value.trim();
  state.settings.chainIds = elements.chainCheckboxes
    .filter((checkbox) => checkbox.checked)
    .map((checkbox) => checkbox.dataset.chainId);

  if (state.settings.chainIds.length === 0) {
    state.settings.chainIds = DEFAULT_CHAIN_IDS;
    hydrateSettingsForm();
  }

  if (previousThreshold !== state.settings.threshold) {
    state.tokenState = {};
    saveJson(TOKEN_STATE_KEY, state.tokenState);
  }

  saveJson(SETTINGS_KEY, state.settings);
  scheduleScanning();
  render();
  refreshScanner();
  loadPreview();
}

function resetScannerData() {
  state.hitLog = [];
  state.tokenState = {};
  state.previewItems = [];
  saveJson(HIT_LOG_KEY, state.hitLog);
  saveJson(TOKEN_STATE_KEY, state.tokenState);
  render();
  elements.previewStatus.textContent = "Scanner data reset.";
  elements.lastUpdated.textContent = "Scanner data reset.";
}

function render() {
  renderHitLog();
  renderPreview();
  const holdLabel = state.settings.holdMinutes > 0
    ? `Hold > ${state.settings.holdMinutes}m`
    : "No hold rule";
  const chainLabel = getEnabledChainIds()
    .map((chainId) => CHAIN_OPTIONS[chainId]?.label || chainId.toUpperCase())
    .join(", ");
  elements.sourceState.textContent =
    `${chainLabel} | Liquidity > ${formatCurrency(MIN_LIQUIDITY_USD)} | ${holdLabel}`;
}

function renderHitLog() {
  elements.hitLogList.innerHTML = "";
  elements.hitLogEmpty.hidden = state.hitLog.length > 0;

  state.hitLog.forEach((hit) => {
    const fragment = elements.hitLogTemplate.content.cloneNode(true);
    const imageElement = fragment.querySelector(".hit-image");
    const linkElement = fragment.querySelector(".hit-link");

    fragment.querySelector(".hit-name").textContent =
      hit.symbol ? `${hit.tokenName} (${hit.symbol})` : hit.tokenName;
    fragment.querySelector(".hit-condition").textContent =
      `Held ${formatCurrency(hit.threshold)} for ${hit.holdMinutes}m`;
    fragment.querySelector(".hit-meta").textContent =
      `${shortenAddress(hit.tokenAddress)} | ${hit.chainLabel}`;
    fragment.querySelector(".hit-marketcap").textContent = formatCurrency(hit.marketCap);
    fragment.querySelector(".hit-liquidity").textContent = formatCurrency(hit.liquidity);
    fragment.querySelector(".hit-age").textContent = formatRelativeAge(hit.pairCreatedAt);
    fragment.querySelector(".hit-pair").textContent = hit.pairLabel;
    fragment.querySelector(".hit-time").textContent = `Caught ${formatTimestamp(hit.hitAt)}`;

    if (hit.imageUrl) {
      imageElement.src = hit.imageUrl;
      imageElement.alt = `${hit.tokenName} logo`;
      imageElement.hidden = false;
    }

    linkElement.href = buildDexUrl(hit);
    elements.hitLogList.appendChild(fragment);
  });
}

function renderPreview() {
  elements.previewList.innerHTML = "";
  elements.previewEmpty.hidden = state.previewItems.length > 0;

  state.previewItems.forEach((item) => {
    const fragment = elements.previewTemplate.content.cloneNode(true);
    const imageElement = fragment.querySelector(".preview-image");
    const matchElement = fragment.querySelector(".preview-match");
    const linkElement = fragment.querySelector(".preview-link");

    fragment.querySelector(".preview-name").textContent =
      item.symbol ? `${item.tokenName} (${item.symbol})` : item.tokenName;
    fragment.querySelector(".preview-chain").textContent = item.chainLabel;
    fragment.querySelector(".preview-address").textContent = shortenAddress(item.tokenAddress);
    fragment.querySelector(".preview-marketcap").textContent = formatCurrency(item.marketCap);
    fragment.querySelector(".preview-liquidity").textContent = formatCurrency(item.liquidity);
    fragment.querySelector(".preview-age").textContent = formatRelativeAge(item.pairCreatedAt);
    fragment.querySelector(".preview-pair").textContent = item.pairLabel;
    matchElement.textContent = getPreviewLabel(item);
    matchElement.className = `status-pill ${item.previewEligible ? "status-fired" : "status-ok"}`;

    if (item.imageUrl) {
      imageElement.src = item.imageUrl;
      imageElement.alt = `${item.tokenName} logo`;
      imageElement.hidden = false;
    }

    linkElement.href = buildDexUrl(item);
    elements.previewList.appendChild(fragment);
  });
}

function syncNotificationState() {
  if (!("Notification" in window)) {
    elements.permissionState.textContent = "Unsupported";
    elements.permissionButton.disabled = true;
    return;
  }

  elements.permissionState.textContent = Notification.permission;
  elements.permissionButton.disabled = Notification.permission === "granted";
}

async function requestNotificationPermission() {
  if (!("Notification" in window)) {
    return;
  }

  const permission = await Notification.requestPermission();
  elements.permissionState.textContent = permission;
  elements.permissionButton.disabled = permission === "granted";
}

function scheduleScanning() {
  if (state.timerId) {
    clearInterval(state.timerId);
  }

  elements.pollingState.textContent = `Every ${state.settings.intervalSeconds}s`;
  state.timerId = window.setInterval(refreshScanner, state.settings.intervalSeconds * 1000);
}

async function refreshScanner() {
  elements.lastUpdated.textContent = "Scanning DEX Screener...";

  try {
    const discoveredPairs = await loadAutoDexPairs();
    pruneHitLog(discoveredPairs);

    for (const pair of discoveredPairs) {
      const tokenKey = `${pair.chainId}:${pair.pairAddress}`;
      const previous = state.tokenState[tokenKey] || {
        lastMarketCap: 0,
        pinged: false,
        aboveSince: null,
      };
      const isAboveThreshold = pair.marketCap >= state.settings.threshold;
      const aboveSince = isAboveThreshold
        ? (previous.aboveSince || new Date().toISOString())
        : null;
      const shouldPing = !previous.pinged && hasHeldLongEnoughForAlert(aboveSince);

      state.tokenState[tokenKey] = {
        lastMarketCap: pair.marketCap,
        pinged: previous.pinged || shouldPing,
        aboveSince,
        lastSeenAt: new Date().toISOString(),
      };

      if (shouldPing) {
        const hit = {
          ...pair,
          threshold: state.settings.threshold,
          holdMinutes: state.settings.holdMinutes,
          aboveSince,
          hitAt: new Date().toISOString(),
        };

        state.hitLog.unshift(hit);
        state.hitLog = dedupeHits(state.hitLog).slice(0, 100);
        saveJson(HIT_LOG_KEY, state.hitLog);

        await Promise.allSettled([
          showNotification(hit),
          sendTelegramNotification(hit),
        ]);
      }
    }

    saveJson(TOKEN_STATE_KEY, state.tokenState);
    elements.lastUpdated.textContent = `Last scan ${new Date().toLocaleTimeString()}`;
  } catch (error) {
    console.error("Scanner refresh failed", error);
    elements.lastUpdated.textContent = error.message;
  }

  renderHitLog();
}

async function loadPreview() {
  elements.previewButton.disabled = true;
  elements.previewStatus.textContent = "Loading recent 24h preview...";

  try {
    const discoveredPairs = await loadAutoDexPairs();
    state.previewItems = discoveredPairs
      .filter((pair) => Date.now() - Number(pair.pairCreatedAt || 0) <= TWENTY_FOUR_HOURS_MS)
      .map((pair) => {
        const tokenKey = `${pair.chainId}:${pair.pairAddress}`;
        const previous = state.tokenState[tokenKey] || { aboveSince: null };
        const previewAboveSince = pair.marketCap >= state.settings.threshold
          ? (previous.aboveSince || new Date().toISOString())
          : null;

        return {
          ...pair,
          previewAboveSince,
          previewEligible: pair.marketCap >= state.settings.threshold &&
            hasHeldLongEnoughForAlert(previewAboveSince),
        };
      })
      .sort((left, right) => right.marketCap - left.marketCap)
      .slice(0, PREVIEW_LIMIT);

    elements.previewStatus.textContent = state.previewItems.length > 0
      ? `Showing ${state.previewItems.length} recent coins from the last 24 hours.`
      : "No recent qualifying coins found in the last 24 hours right now.";
  } catch (error) {
    console.error("Preview failed", error);
    state.previewItems = [];
    elements.previewStatus.textContent = error.message;
  } finally {
    elements.previewButton.disabled = false;
    renderPreview();
  }
}

async function loadAutoDexPairs() {
  const tokenAddresses = await fetchAutoDexTokenAddresses();
  if (tokenAddresses.length === 0) {
    return [];
  }

  const results = await Promise.all(tokenAddresses.map(fetchDexTokenPair));
  return dedupePairs(results.filter(Boolean));
}

async function fetchAutoDexTokenAddresses() {
  const [profilesResponse, boostsResponse, topBoostsResponse] = await Promise.all([
    fetch("/api/dex/token-profiles"),
    fetch("/api/dex/token-boosts"),
    fetch("/api/dex/token-boosts-top"),
  ]);

  if (!profilesResponse.ok || !boostsResponse.ok || !topBoostsResponse.ok) {
    throw new Error("DEX discovery feeds responded with an error.");
  }

  const [profiles, boosts, topBoosts] = await Promise.all([
    profilesResponse.json(),
    boostsResponse.json(),
    topBoostsResponse.json(),
  ]);
  const combined = [
    ...(Array.isArray(profiles) ? profiles : []),
    ...(Array.isArray(boosts) ? boosts : []),
    ...(Array.isArray(topBoosts) ? topBoosts : []),
  ];

  return [...new Set(
    combined
      .filter((item) => getEnabledChainIds().includes(item?.chainId))
      .map((item) => item?.tokenAddress)
      .filter(Boolean)
  )].slice(0, AUTO_DISCOVERY_LIMIT);
}

async function fetchDexTokenPair(tokenAddress) {
  const url = new URL("/api/dex/tokens", window.location.origin);
  url.searchParams.set("tokenAddress", tokenAddress);

  const response = await fetch(url);
  if (!response.ok) {
    return null;
  }

  const payload = await response.json();
  const pairs = Array.isArray(payload?.pairs) ? payload.pairs : [];
  if (pairs.length === 0) {
    return null;
  }

  const bestPair = pairs
    .filter((pair) => {
      const liquidity = Number(pair.liquidity?.usd || 0);
      const marketCap = Number(pair.marketCap || 0);
      const volume24h = Number(pair.volume?.h24 || 0);
      const buys24h = Number(pair.txns?.h24?.buys || 0);
      const sells24h = Number(pair.txns?.h24?.sells || 0);
      const pairCreatedAt = Number(pair.pairCreatedAt || 0);
      const ageMs = pairCreatedAt ? Date.now() - pairCreatedAt : Number.POSITIVE_INFINITY;
      const liquidityRatio = marketCap > 0 ? liquidity / marketCap : 0;

      return (
        liquidity > MIN_LIQUIDITY_USD &&
        Number.isFinite(marketCap) &&
        marketCap > 0 &&
        volume24h >= MIN_VOLUME_24H_USD &&
        buys24h + sells24h >= MIN_TRANSACTIONS_24H &&
        ageMs >= MIN_PAIR_AGE_MS &&
        liquidityRatio >= MIN_LIQUIDITY_TO_MCAP_RATIO
      );
    })
    .sort((left, right) => scoreDexPair(right) - scoreDexPair(left))[0];

  if (!bestPair) {
    return null;
  }

  return {
    source: "dex",
    pairAddress: bestPair.pairAddress || tokenAddress,
    tokenAddress,
    tokenName: bestPair.baseToken?.name || tokenAddress,
    symbol: bestPair.baseToken?.symbol || "",
    imageUrl: bestPair.info?.imageUrl || "",
    marketCap: Number(bestPair.marketCap || 0),
    liquidity: Number(bestPair.liquidity?.usd || 0),
    chainId: bestPair.chainId || "solana",
    chainLabel: getChainLabel(bestPair.chainId),
    pairCreatedAt: Number(bestPair.pairCreatedAt || 0),
    pairLabel: `${bestPair.baseToken?.symbol || "?"}/${bestPair.quoteToken?.symbol || "?"}`,
  };
}

async function showNotification(hit) {
  if (!("Notification" in window) || Notification.permission !== "granted") {
    return;
  }

  new Notification(`${hit.tokenName} held ${formatCurrency(hit.threshold)}`, {
    body:
      `${hit.symbol ? `${hit.symbol} ` : ""}${hit.chainLabel} held above target for ${hit.holdMinutes}m. ` +
      `Market cap is ${formatCurrency(hit.marketCap)}.`,
    icon: hit.imageUrl || undefined,
  });
}

async function sendTelegramNotification(hit) {
  if (!state.settings.telegramBotToken || !state.settings.telegramChatId) {
    return;
  }

  const url = new URL("/api/telegram/send", window.location.origin);
  url.searchParams.set("token", state.settings.telegramBotToken);
  url.searchParams.set("chatId", state.settings.telegramChatId);
  url.searchParams.set(
    "message",
    [
      `${hit.tokenName}${hit.symbol ? ` (${hit.symbol})` : ""} held ${formatCurrency(hit.threshold)} for ${hit.holdMinutes}m`,
      `Market Cap: ${formatCurrency(hit.marketCap)}`,
      `Liquidity: ${formatCurrency(hit.liquidity)}`,
      `Pair Age: ${formatRelativeAge(hit.pairCreatedAt)}`,
      `Chain: ${hit.chainLabel}`,
      `DEX: ${buildDexUrl(hit)}`,
      ...buildSwapLines(hit),
    ].join("\n")
  );

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("Telegram alert failed to send.");
  }
}

function dedupeHits(items) {
  const seen = new Set();
  return items.filter((item) => {
    const key = `${item.chainId}:${item.pairAddress}:${item.threshold}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function dedupePairs(items) {
  const seen = new Set();
  return items.filter((item) => {
    const key = `${item.chainId}:${item.pairAddress}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function pruneHitLog(currentPairs) {
  const allowed = new Map(currentPairs.map((pair) => [`${pair.chainId}:${pair.pairAddress}`, pair]));
  state.hitLog = state.hitLog.filter((item) => allowed.has(`${item.chainId}:${item.pairAddress}`));
  saveJson(HIT_LOG_KEY, state.hitLog);
}

function hasHeldLongEnoughForAlert(aboveSince) {
  if (!aboveSince) {
    return false;
  }

  if (state.settings.holdMinutes <= 0) {
    return true;
  }

  return Date.now() - Date.parse(aboveSince) >= state.settings.holdMinutes * 60 * 1000;
}

function getPreviewLabel(item) {
  if (item.previewEligible) {
    return `Would Ping (${state.settings.holdMinutes}m held)`;
  }

  if (item.marketCap < state.settings.threshold) {
    return "Below Target";
  }

  if (state.settings.holdMinutes <= 0) {
    return "Would Ping";
  }

  return `Needs ${state.settings.holdMinutes}m hold`;
}

function buildDexUrl(item) {
  const chain = CHAIN_OPTIONS[item.chainId] || CHAIN_OPTIONS.solana;
  return `https://dexscreener.com/${chain.dexScreenerPath}/${item.pairAddress}`;
}

function buildSwapLines(item) {
  const chain = CHAIN_OPTIONS[item.chainId];
  if (!chain?.swapUrl) {
    return [];
  }

  return [`${chain.swapLabel}: ${chain.swapUrl(item)}`];
}

function getEnabledChainIds() {
  const configuredChains = Array.isArray(state.settings.chainIds)
    ? state.settings.chainIds
    : DEFAULT_CHAIN_IDS;
  const validChains = configuredChains.filter((chainId) => CHAIN_OPTIONS[chainId]);
  return validChains.length > 0 ? validChains : DEFAULT_CHAIN_IDS;
}

function getChainLabel(chainId) {
  return CHAIN_OPTIONS[chainId]?.label || String(chainId || "solana").toUpperCase();
}

function scoreDexPair(pair) {
  return Number(pair.marketCap || 0) + Number(pair.liquidity?.usd || 0);
}

function formatCurrency(value) {
  if (value == null) {
    return "-";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: value >= 1000000 ? "compact" : "standard",
    maximumFractionDigits: value >= 1 ? 0 : 6,
  }).format(value);
}

function formatTimestamp(value) {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString();
}

function formatRelativeAge(value) {
  if (!value) {
    return "-";
  }

  const hours = Math.max(0, (Date.now() - value) / (60 * 60 * 1000));
  if (hours < 1) {
    return `${Math.max(1, Math.round(hours * 60))}m ago`;
  }

  return `${hours.toFixed(1)}h ago`;
}

function shortenAddress(address) {
  if (!address || address.length < 12) {
    return address || "-";
  }

  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}
