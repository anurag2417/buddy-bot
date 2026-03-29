// BuddyBot Safety Monitor - Content Script
// Runs on search engine result pages to capture search queries

(function () {
  // Notify user that BuddyBot is active (visible indicator)
  function showSafetyIndicator() {
    if (document.getElementById("buddybot-indicator")) return;

    const indicator = document.createElement("div");
    indicator.id = "buddybot-indicator";
    indicator.innerHTML = `
      <div style="
        position: fixed;
        bottom: 16px;
        left: 16px;
        z-index: 99999;
        display: flex;
        align-items: center;
        gap: 8px;
        background: linear-gradient(135deg, #e0f2fe, #d1fae5);
        border: 2px solid #bae6fd;
        border-radius: 50px;
        padding: 8px 16px;
        font-family: 'Quicksand', 'Nunito', -apple-system, sans-serif;
        font-size: 13px;
        font-weight: 600;
        color: #0c4a6e;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        cursor: default;
        user-select: none;
        transition: opacity 0.3s;
      ">
        <span style="font-size: 18px;">&#x1F6E1;</span>
        BuddyBot is keeping you safe
      </div>
    `;
    document.body.appendChild(indicator);

    // Fade out after 5 seconds, show on hover
    setTimeout(() => {
      const el = indicator.firstElementChild;
      if (el) {
        el.style.opacity = "0.4";
        el.addEventListener("mouseenter", () => (el.style.opacity = "1"));
        el.addEventListener("mouseleave", () => (el.style.opacity = "0.4"));
      }
    }, 5000);
  }

  // Extract search query from current page
  function extractCurrentQuery() {
    const url = window.location.href;
    const urlObj = new URL(url);
    const hostname = urlObj.hostname.replace("www.", "");

    const engines = {
      "google.com": "q",
      "bing.com": "q",
      "yahoo.com": "p",
      "duckduckgo.com": "q",
      "youtube.com": "search_query",
    };

    for (const [domain, param] of Object.entries(engines)) {
      if (hostname.includes(domain)) {
        return urlObj.searchParams.get(param);
      }
    }
    return null;
  }

  // Initialize
  chrome.storage.local.get("buddybot_config", (result) => {
    const config = result.buddybot_config || {};
    if (config.isActive !== false) {
      showSafetyIndicator();
    }
  });

  // Watch for dynamic search query changes (SPA-like behavior on Google)
  let lastQuery = extractCurrentQuery();
  const observer = new MutationObserver(() => {
    const currentQuery = extractCurrentQuery();
    if (currentQuery && currentQuery !== lastQuery) {
      lastQuery = currentQuery;
      // The background script handles actual packet creation via webNavigation
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });
})();
