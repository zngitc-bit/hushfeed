// Badge counter + keyboard shortcut + first-run welcome.
importScripts("shared.js");

// Serialize increments and resets so tabs cannot overwrite each other's totals.
let storageQueue = Promise.resolve();

chrome.runtime.onMessage.addListener((msg, sender, respond) => {
  if (!msg || !["hf:stats", "hf:reset"].includes(msg.type)) return;
  if (msg.type === "hf:reset" && sender.url?.split(/[?#]/)[0] !== chrome.runtime.getURL("options.html")) return;
  if (msg.type === "hf:stats" && (!sender.tab || sender.frameId !== 0)) return;
  const operation = storageQueue.then(async () => {
    const { stats } = await chrome.storage.local.get("stats");
    const epoch = stats && stats.epoch || 0;
    if (msg.type === "hf:reset") {
      await chrome.storage.local.set({ settings: HF.sanitize(null), stats: { total: 0, epoch: epoch + 1 } });
    } else if (msg.epoch === epoch && Number.isSafeInteger(msg.count) && msg.count > 0) {
      await chrome.storage.local.set({ stats: { total: (stats && stats.total || 0) + msg.count, epoch } });
    }
    return { ok: true };
  });
  storageQueue = operation.catch(() => {});
  operation.then(respond, () => respond({ ok: false }));
  return true;
});

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
