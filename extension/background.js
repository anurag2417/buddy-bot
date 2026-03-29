// BuddyBot Safety Monitor - Background Service Worker (Manifest V3)

// ============================================================
// CONFIGURATION
// ============================================================
const DEFAULT_CONFIG = {
  backendUrl: "",
  deviceId: "",
  pin: "",
  isActive: true,
  syncInterval: 30, // seconds
  filterAds: true,
};

// Ad/tracking/irrelevant domains to filter out
const FILTERED_DOMAINS = [
  "doubleclick.net", "googlesyndication.com", "googleadservices.com",
  "google-analytics.com", "analytics.google.com", "adnxs.com",
  "adsrvr.org", "facebook.com/tr", "pixel.facebook.com",
  "amazon-adsystem.com", "criteo.com", "outbrain.com", "taboola.com",
  "scorecardresearch.com", "quantserve.com", "bluekai.com",
  "adsymptotic.com", "moatads.com", "rubiconproject.com",
  "pubmatic.com", "openx.net", "bidswitch.net", "casalemedia.com",
  "rlcdn.com", "sharethrough.com", "spotxchange.com",
  "serving-sys.com", "smaato.net", "mopub.com", "inmobi.com",
  // Tracking
  "hotjar.com", "mouseflow.com", "crazyegg.com", "fullstory.com",
  "mixpanel.com", "segment.io", "amplitude.com", "heapanalytics.com",
  // CDN / static assets
  "fonts.googleapis.com", "fonts.gstatic.com", "cdn.jsdelivr.net",
  "cdnjs.cloudflare.com", "unpkg.com", "maxcdn.bootstrapcdn.com",
  // Browser internals
  "chrome-extension://", "chrome://", "about:", "edge://",
];

const FILTERED_EXTENSIONS = [
  ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
  ".woff", ".woff2", ".ttf", ".eot", ".map", ".webp", ".avif",
];

// Search engine patterns for extracting queries
const SEARCH_ENGINES = {
  "google.com": { param: "q", name: "Google" },
  "bing.com": { param: "q", name: "Bing" },
  "yahoo.com": { param: "p", name: "Yahoo" },
  "duckduckgo.com": { param: "q", name: "DuckDuckGo" },
  "youtube.com": { param: "search_query", name: "YouTube" },
};

// ============================================================
// HELPER FUNCTIONS
// ============================================================
function generateDeviceId() {
  return "dev-" + crypto.randomUUID();
}

function isFilteredUrl(url) {
  if (!url) return true;
  const lowerUrl = url.toLowerCase();
  // Filter browser internal URLs
  if (lowerUrl.startsWith("chrome") || lowerUrl.startsWith("about:") ||
      lowerUrl.startsWith("edge://") || lowerUrl.startsWith("brave://")) {
    return true;
  }
  // Filter ad/tracking domains
  for (const domain of FILTERED_DOMAINS) {
    if (lowerUrl.includes(domain)) return true;
  }
  // Filter static assets
  for (const ext of FILTERED_EXTENSIONS) {
    const pathname = new URL(url).pathname.toLowerCase();
    if (pathname.endsWith(ext)) return true;
  }
  return false;
}

function extractSearchQuery(url) {
  try {
    const urlObj = new URL(url);
    const hostname = urlObj.hostname.replace("www.", "");
    for (const [domain, config] of Object.entries(SEARCH_ENGINES)) {
      if (hostname.includes(domain)) {
        const query = urlObj.searchParams.get(config.param);
        if (query) {
          return { query, engine: config.name };
        }
      }
    }
  } catch (e) { /* ignore */ }
  return null;
}

function extractDomain(url) {
  try {
    return new URL(url).hostname;
  } catch (e) {
    return "unknown";
  }
}

// ============================================================
// PACKET STORAGE & SYNC
// ============================================================
let packetQueue = [];

async function getConfig() {
  const result = await chrome.storage.local.get("buddybot_config");
  return { ...DEFAULT_CONFIG, ...result.buddybot_config };
}

async function saveConfig(config) {
  await chrome.storage.local.set({ buddybot_config: config });
}

async function queuePacket(packet) {
  const config = await getConfig();
  if (!config.isActive) return;

  packetQueue.push(packet);

  // Store in local storage as backup
  const stored = await chrome.storage.local.get("buddybot_packets");
  const packets = stored.buddybot_packets || [];
  packets.push(packet);
  // Keep max 500 packets locally
  if (packets.length > 500) packets.splice(0, packets.length - 500);
  await chrome.storage.local.set({ buddybot_packets: packets });
}

async function syncPackets() {
  const config = await getConfig();
  if (!config.backendUrl || !config.deviceId) return;

  const stored = await chrome.storage.local.get("buddybot_packets");
  const packets = stored.buddybot_packets || [];
  if (packets.length === 0) return;

  try {
    const response = await fetch(`${config.backendUrl}/api/extension/packets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        device_id: config.deviceId,
        packets: packets.slice(0, 50), // Send in batches of 50
      }),
    });

    if (response.ok) {
      // Remove synced packets
      const remaining = packets.slice(50);
      await chrome.storage.local.set({ buddybot_packets: remaining });

      // Update sync status
      await chrome.storage.local.set({
        buddybot_last_sync: new Date().toISOString(),
        buddybot_sync_status: "success",
      });
    }
  } catch (e) {
    await chrome.storage.local.set({ buddybot_sync_status: "error" });
  }
}

// ============================================================
// EVENT LISTENERS
// ============================================================

// Track URL visits via webNavigation
chrome.webNavigation.onCompleted.addListener(async (details) => {
  // Only track main frame navigations
  if (details.frameId !== 0) return;

  const url = details.url;
  if (isFilteredUrl(url)) return;

  const tab = await chrome.tabs.get(details.tabId).catch(() => null);
  if (!tab) return;

  const config = await getConfig();
  const searchData = extractSearchQuery(url);

  const packet = {
    id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    device_id: config.deviceId,
    tab_type: tab.incognito ? "incognito" : "normal",
    url: url,
    domain: extractDomain(url),
    title: tab.title || "",
    packet_type: searchData ? "search_query" : "url_visit",
    search_query: searchData?.query || null,
    search_engine: searchData?.engine || null,
  };

  await queuePacket(packet);

  // Update badge with packet count
  const stored = await chrome.storage.local.get("buddybot_packets");
  const count = (stored.buddybot_packets || []).length;
  chrome.action.setBadgeText({ text: count > 0 ? String(count) : "" });
  chrome.action.setBadgeBackgroundColor({ color: "#38bdf8" });
});

// Track tab title updates (catches SPA navigations)
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete") return;
  if (!tab.url || isFilteredUrl(tab.url)) return;

  // Only track if this is a search query we haven't captured
  const searchData = extractSearchQuery(tab.url);
  if (!searchData) return;

  const config = await getConfig();

  const packet = {
    id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    device_id: config.deviceId,
    tab_type: tab.incognito ? "incognito" : "normal",
    url: tab.url,
    domain: extractDomain(tab.url),
    title: tab.title || "",
    packet_type: "search_query",
    search_query: searchData.query,
    search_engine: searchData.engine,
  };

  await queuePacket(packet);
});

// ============================================================
// ALARMS (periodic sync)
// ============================================================
chrome.alarms.create("syncPackets", { periodInMinutes: 0.5 }); // Every 30 seconds

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "syncPackets") {
    syncPackets();
  }
});

// ============================================================
// MESSAGE HANDLING (popup & options communication)
// ============================================================
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "GET_STATUS") {
    (async () => {
      const config = await getConfig();
      const stored = await chrome.storage.local.get(["buddybot_packets", "buddybot_last_sync", "buddybot_sync_status"]);
      sendResponse({
        isActive: config.isActive,
        isConfigured: !!config.backendUrl && !!config.deviceId,
        pendingPackets: (stored.buddybot_packets || []).length,
        lastSync: stored.buddybot_last_sync || null,
        syncStatus: stored.buddybot_sync_status || "never",
        backendUrl: config.backendUrl,
        deviceId: config.deviceId,
      });
    })();
    return true; // async response
  }

  if (message.type === "TOGGLE_ACTIVE") {
    (async () => {
      const config = await getConfig();
      config.isActive = message.value;
      await saveConfig(config);
      sendResponse({ isActive: config.isActive });
    })();
    return true;
  }

  if (message.type === "VERIFY_PIN") {
    (async () => {
      const config = await getConfig();
      sendResponse({ valid: config.pin === message.pin });
    })();
    return true;
  }

  if (message.type === "SAVE_CONFIG") {
    (async () => {
      const config = await getConfig();
      Object.assign(config, message.config);
      if (!config.deviceId) config.deviceId = generateDeviceId();
      await saveConfig(config);
      sendResponse({ success: true, config });
    })();
    return true;
  }

  if (message.type === "FORCE_SYNC") {
    syncPackets().then(() => sendResponse({ success: true }));
    return true;
  }

  if (message.type === "GET_RECENT_PACKETS") {
    (async () => {
      const stored = await chrome.storage.local.get("buddybot_packets");
      const packets = (stored.buddybot_packets || []).slice(-20).reverse();
      sendResponse({ packets });
    })();
    return true;
  }
});

// ============================================================
// INITIALIZATION
// ============================================================
chrome.runtime.onInstalled.addListener(async () => {
  const config = await getConfig();
  if (!config.deviceId) {
    config.deviceId = generateDeviceId();
    await saveConfig(config);
  }
});
