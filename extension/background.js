// Badge counter + keyboard shortcut + first-run welcome.

chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg && msg.type === "hf:count" && sender.tab) {
    const n = Number(msg.count) || 0;
    const text = n > 99 ? "99+" : n > 0 ? String(n) : "";
    chrome.action.setBadgeText({ tabId: sender.tab.id, text });
    chrome.action.setBadgeBackgroundColor({ tabId: sender.tab.id, color: "#0b7a75" });
  }
});

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "toggle-enabled") return;
  const got = await chrome.storage.local.get("settings");
  const settings = got.settings || {};
  settings.enabled = settings.enabled === false; // flips the current value
  await chrome.storage.local.set({ settings });
});

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") chrome.runtime.openOptionsPage();
});
