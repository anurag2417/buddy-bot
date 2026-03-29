// BuddyBot Safety Monitor - Popup Script

document.addEventListener("DOMContentLoaded", () => {
  const mainView = document.getElementById("main-view");
  const pinView = document.getElementById("pin-view");
  const toggleBtn = document.getElementById("toggle-btn");
  const syncBtn = document.getElementById("sync-btn");
  const settingsBtn = document.getElementById("settings-btn");
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");
  const pendingCount = document.getElementById("pending-count");
  const syncStatus = document.getElementById("sync-status");
  const recentList = document.getElementById("recent-list");
  const pinInput = document.getElementById("pin-input");
  const pinSubmit = document.getElementById("pin-submit");
  const pinCancel = document.getElementById("pin-cancel");
  const pinError = document.getElementById("pin-error");

  let currentStatus = {};

  // Load status
  function loadStatus() {
    chrome.runtime.sendMessage({ type: "GET_STATUS" }, (response) => {
      if (!response) return;
      currentStatus = response;

      pendingCount.textContent = response.pendingPackets || 0;

      if (response.syncStatus === "success") {
        syncStatus.textContent = "OK";
        syncStatus.style.color = "#34d399";
      } else if (response.syncStatus === "error") {
        syncStatus.textContent = "Err";
        syncStatus.style.color = "#f87171";
      } else {
        syncStatus.textContent = "--";
      }

      if (!response.isConfigured) {
        statusDot.className = "status-dot error";
        statusText.textContent = "Not configured";
        toggleBtn.textContent = "Pause Monitoring";
        toggleBtn.disabled = true;
      } else if (response.isActive) {
        statusDot.className = "status-dot active";
        statusText.textContent = "Active & Monitoring";
        toggleBtn.textContent = "Pause Monitoring";
        toggleBtn.disabled = false;
      } else {
        statusDot.className = "status-dot paused";
        statusText.textContent = "Paused";
        toggleBtn.textContent = "Resume Monitoring";
        toggleBtn.disabled = true;
      }
    });

    // Load recent packets
    chrome.runtime.sendMessage({ type: "GET_RECENT_PACKETS" }, (response) => {
      if (!response || !response.packets || response.packets.length === 0) {
        recentList.innerHTML = '<p class="empty-msg">No recent activity</p>';
        return;
      }

      recentList.innerHTML = response.packets.slice(0, 8).map((p) => {
        const typeBadge = p.packet_type === "search_query"
          ? '<span class="type-badge search">Search</span>'
          : '<span class="type-badge visit">Visit</span>';
        const incognitoBadge = p.tab_type === "incognito"
          ? ' <span class="type-badge incognito">Incognito</span>'
          : '';
        const mainText = p.search_query || p.title || p.domain;
        return `
          <div class="recent-item">
            ${typeBadge}${incognitoBadge}
            <strong>${escapeHtml(mainText)}</strong>
            <span class="url-text">${escapeHtml(p.domain)}</span>
          </div>
        `;
      }).join("");
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // Toggle active state (requires PIN)
  // toggleBtn.addEventListener("click", () => {
  //   showPinView("toggle");
  // });

  // Sync now
  syncBtn.addEventListener("click", () => {
    syncBtn.textContent = "Syncing...";
    syncBtn.disabled = true;
    chrome.runtime.sendMessage({ type: "FORCE_SYNC" }, () => {
      setTimeout(() => {
        syncBtn.textContent = "Sync Now";
        syncBtn.disabled = false;
        loadStatus();
      }, 1500);
    });
  });

  // Settings (requires PIN)
  settingsBtn.addEventListener("click", () => {
    showPinView("settings");
  });

  // PIN View
  let pinAction = null;

  function showPinView(action) {
    // Check if PIN is set
    chrome.storage.local.get("buddybot_config", (result) => {
      const config = result.buddybot_config || {};
      if (!config.pin) {
        // No PIN set, go directly to action
        executePinAction(action);
        return;
      }
      pinAction = action;
      mainView.style.display = "none";
      pinView.style.display = "block";
      pinInput.value = "";
      pinError.style.display = "none";
      pinInput.focus();
    });
  }

  pinSubmit.addEventListener("click", () => {
    const pin = pinInput.value;
    chrome.runtime.sendMessage({ type: "VERIFY_PIN", pin }, (response) => {
      if (response && response.valid) {
        pinView.style.display = "none";
        mainView.style.display = "block";
        executePinAction(pinAction);
      } else {
        pinError.style.display = "block";
        pinInput.value = "";
        pinInput.focus();
      }
    });
  });

  pinInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") pinSubmit.click();
  });

  pinCancel.addEventListener("click", () => {
    pinView.style.display = "none";
    mainView.style.display = "block";
  });

  function executePinAction(action) {
    if (action === "toggle") {
      chrome.runtime.sendMessage(
        { type: "TOGGLE_ACTIVE", value: !currentStatus.isActive },
        () => loadStatus()
      );
    } else if (action === "settings") {
      chrome.runtime.openOptionsPage();
    }
  }

  // Initialize
  loadStatus();
});
