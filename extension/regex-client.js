const HFRegex = (() => {
  let connection;
  let serial = 0;
  const pending = new Map();
  const blocked = new Set();
  let warning = "";

  function connect() {
    if (connection) return connection;
    connection = new Promise((resolve) => {
      const frame = document.createElement("iframe");
      frame.hidden = true;
      frame.setAttribute("aria-hidden", "true");
      frame.src = chrome.runtime.getURL("regex-frame.html");
      const channel = new MessageChannel();
      const timer = setTimeout(() => {
        warning = "Regular expressions are unavailable on this page. Reload to try again.";
        resolve(null);
      }, 4000);
      channel.port1.onmessage = ({ data }) => {
        if (data.ready) {
          clearTimeout(timer);
          resolve(channel.port1);
          return;
        }
        const done = pending.get(data.id);
        if (done) { pending.delete(data.id); done(data); }
      };
      frame.addEventListener("load", () => {
        frame.contentWindow.postMessage("hf:regex-connect", new URL(frame.src).origin, [channel.port2]);
      }, { once: true });
      document.documentElement.append(frame);
    });
    return connection;
  }

  async function test(rule, text) {
    const key = JSON.stringify([rule.text, rule.caseSensitive]);
    if (blocked.has(key)) return false;
    const port = await connect();
    if (!port) return false;
    const id = ++serial;
    const result = await new Promise((resolve) => {
      const timer = setTimeout(() => resolve({ matched: false, timedOut: true }), 4500);
      pending.set(id, (value) => { clearTimeout(timer); resolve(value); });
      port.postMessage({ id, pattern: rule.text, flags: rule.caseSensitive ? "" : "i", text });
    });
    pending.delete(id);
    if (result.timedOut) {
      blocked.add(key);
      warning = "A slow regular expression was skipped on this page. Review your regex rules in All settings.";
    }
    return result.matched;
  }

  return { test, get warning() { return warning; } };
})();
