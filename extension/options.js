// BuddyBot Safety Monitor - Options Page Script

document.addEventListener("DOMContentLoaded", () => {
  const pinGate = document.getElementById("pin-gate");
  const settingsView = document.getElementById("settings-view");
  const gatePin = document.getElementById("gate-pin");
  const gateSubmit = document.getElementById("gate-submit");
  const gateError = document.getElementById("gate-error");
  const skipPin = document.getElementById("skip-pin");
  const noPinHint = document.getElementById("no-pin-hint");

  const backendUrl = document.getElementById("backend-url");
  const deviceId = document.getElementById("device-id");
  const pinField = document.getElementById("pin-field");
  const pinConfirm = document.getElementById("pin-confirm");
  const saveBtn = document.getElementById("save-btn");
  const saveStatus = document.getElementById("save-status");
  const clearDataBtn = document.getElementById("clear-data-btn");

  // Check if PIN is set
  chrome.storage.local.get("buddybot_config", (result) => {
    const config = result.buddybot_config || {};
    if (!config.pin) {
      noPinHint.style.display = "block";
    } else {
      noPinHint.style.display = "none";
    }
  });

  // PIN gate
  gateSubmit.addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "VERIFY_PIN", pin: gatePin.value }, (response) => {
      if (response && response.valid) {
        showSettings();
      } else {
        gateError.style.display = "block";
        gatePin.value = "";
        gatePin.focus();
      }
    });
  });

  gatePin.addEventListener("keydown", (e) => {
    if (e.key === "Enter") gateSubmit.click();
  });

  skipPin.addEventListener("click", () => {
    showSettings();
  });

  function showSettings() {
    pinGate.style.display = "none";
    settingsView.style.display = "block";
    loadSettings();
  }

  function loadSettings() {
    chrome.runtime.sendMessage({ type: "GET_STATUS" }, (response) => {
      if (!response) return;
      backendUrl.value = response.backendUrl || "";
      deviceId.value = response.deviceId || "Not generated yet";
    });
  }

  // Save
  saveBtn.addEventListener("click", () => {
    const pin = pinField.value;
    const confirm = pinConfirm.value;

    if (pin && pin !== confirm) {
      saveStatus.textContent = "PINs do not match!";
      saveStatus.style.color = "#ef4444";
      return;
    }

    if (pin && pin.length < 4) {
      saveStatus.textContent = "PIN must be at least 4 digits";
      saveStatus.style.color = "#ef4444";
      return;
    }

    const config = {
      backendUrl: backendUrl.value.replace(/\/$/, ""), // Remove trailing slash
    };

    if (pin) {
      config.pin = pin;
    }

    chrome.runtime.sendMessage({ type: "SAVE_CONFIG", config }, (response) => {
      if (response && response.success) {
        saveStatus.textContent = "Settings saved!";
        saveStatus.style.color = "#34d399";
        pinField.value = "";
        pinConfirm.value = "";
        deviceId.value = response.config.deviceId || deviceId.value;
      } else {
        saveStatus.textContent = "Error saving settings";
        saveStatus.style.color = "#ef4444";
      }
      setTimeout(() => { saveStatus.textContent = ""; }, 3000);
    });
  });

  // Clear data
  clearDataBtn.addEventListener("click", () => {
    if (confirm("Clear all locally stored browsing data? This cannot be undone.")) {
      chrome.storage.local.set({ buddybot_packets: [] }, () => {
        clearDataBtn.textContent = "Data Cleared!";
        setTimeout(() => { clearDataBtn.textContent = "Clear All Local Data"; }, 2000);
      });
    }
  });
});
