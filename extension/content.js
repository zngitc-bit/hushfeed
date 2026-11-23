(() => {
  "use strict";

  const PROMO_LABELS = new Set([
    "Ad", "Promoted", "Promovat", "Anuncio", "Promocionado", "Annonce", "Sponsorisé",
    "Gesponsert", "Anzeige", "Promosso", "Patrocinado", "Реклама", "広告", "광고", "推广", "Reklam", "Reclame", "Reklama"
  ]);
  const RESERVED = new Set([
    "home", "explore", "notifications", "messages", "i", "settings", "compose", "search",
    "hashtag", "bookmarks", "lists", "communities", "jobs", "premium", "tos", "privacy"
  ]);

  let settings = HF.sanitize(null);
  let rules = [];
  let allow = [];
  let version = 0;
  let scheduled = false;

  const seen = new Set(); // hidden posts on this page, shown in the badge
  const counted = new Set(); // posts already added to the lifetime total
  let pending = 0;
  let flushTimer;

  function compile() {
    rules = settings.keywords
      .filter((k) => k.on)
      .map((k) => ({ k, re: HF.compileKeyword(k) }))
      .filter((r) => r.re);
    allow = settings.allow.map((a) => a.toLowerCase());
  }

  function currentPlace() {
    const p = location.pathname;
    if (p === "/" || p === "/home") return "home";
    if (p.startsWith("/search") || p.startsWith("/hashtag/")) return "search";
    if (/^\/[^/]+\/status\//.test(p)) return "thread";
    const first = p.split("/")[1] || "";
    if (/^[A-Za-z0-9_]{1,15}$/.test(first) && !RESERVED.has(first.toLowerCase())) return "profile";
    return "other";
  }

  function authorHandle(article) {
    const links = article.querySelectorAll('[data-testid="User-Name"] a[href^="/"]');
    for (const a of links) {
      const m = (a.getAttribute("href") || "").match(/^\/([A-Za-z0-9_]{1,15})$/);
      if (m) return m[1].toLowerCase();
    }
    return null;
  }

  function tweetKey(article) {
    const time = article.querySelector('a[href*="/status/"] time');
    const href = time && time.parentElement && time.parentElement.getAttribute("href");
    const m = href && href.match(/\/status\/(\d+)/);
    return m ? m[1] : null;
  }

  // Text of a node, with emoji (rendered by X as <img alt="...">) kept in place.
  function textOf(el) {
    let out = "";
    const walk = (n) => {
      if (n.nodeType === 3) out += n.nodeValue;
      else if (n.nodeType === 1) {
        if (n.tagName === "IMG") out += n.alt || "";
        else if (n.tagName === "BR") out += "\n";
        else n.childNodes.forEach(walk);
      }
    };
    walk(el);
    return out;
  }

  function emojiOf(el) {
    return Array.from(el.querySelectorAll("img[alt]"), (i) => i.alt).join(" ");
  }

  // Cheap fingerprint of a string, used to skip posts whose content did not change.
  function sigOf(s) {
    let h = 0;
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
    return s.length + ":" + h;
  }

  function isPromoted(article) {
    return article.innerText.split("\n").some((line) => PROMO_LABELS.has(line.trim()));
  }

  // Returns a short reason string when the post should be hidden, otherwise null.
  function evaluate(article, place) {
    if (!settings.enabled || !settings.places[place]) return null;

    const text = Array.from(article.querySelectorAll('[data-testid="tweetText"]'))
      .map(textOf)
      .join("\n");

    if (allow.length) {
      const lower = text.toLowerCase();
      if (allow.some((a) => lower.includes(a))) return null;
    }

    if (settings.accounts.length) {
      const handle = authorHandle(article);
      if (handle && settings.accounts.includes(handle)) return "@" + handle;
    }

    if (settings.hidePromoted && isPromoted(article)) return "Promoted";

    let full = null;
    for (const { k, re } of rules) {
      let hay = text;
      if (k.scope === "all") hay = full === null ? (full = article.innerText + "\n" + emojiOf(article)) : full;
      if (re.test(hay)) return "“" + k.text + "”";
    }
    return null;
  }

  function clear(cell) {
    cell.classList.remove("hf-hide");
    cell.querySelectorAll("article.hf-blur, article.hf-collapsed").forEach((a) => {
      a.classList.remove("hf-blur", "hf-collapsed");
      a.removeAttribute("title");
    });
    cell.querySelectorAll(":scope > .hf-note").forEach((n) => n.remove());
    delete cell.dataset.hfState;
    delete cell.dataset.hfReveal;
  }

  function reveal(cell) {
    cell.dataset.hfReveal = "1";
    if (cell.__hfArticle) cell.__hfArticle.__hfSig = null;
    schedule(0);
  }

  function bindBlurClick(cell) {
    if (cell.__hfBound) return;
    cell.__hfBound = true;
    cell.addEventListener(
      "click",
      (e) => {
        if (cell.dataset.hfState !== "blur") return;
        e.preventDefault();
        e.stopPropagation();
        reveal(cell);
      },
      true
    );
  }

  function apply(article, reason) {
    const cell = article.closest('[data-testid="cellInnerDiv"]') || article;

    if (cell.__hfArticle !== article) {
      clear(cell);
      cell.__hfArticle = article;
    }
    if (!reason) {
      if (cell.dataset.hfState) clear(cell);
      return;
    }

    let want = cell.dataset.hfReveal === "1" ? "revealed" : settings.mode;
    if (cell === article && want === "collapse") want = "hide";
    if (cell.dataset.hfState === want) return;

    const keepReveal = cell.dataset.hfReveal;
    clear(cell);
    if (keepReveal) cell.dataset.hfReveal = keepReveal;
    cell.dataset.hfState = want;

    if (want === "hide") {
      cell.classList.add("hf-hide");
    } else if (want === "blur") {
      article.classList.add("hf-blur");
      article.title = "Hidden by Hushfeed: " + reason + " (click to show)";
      bindBlurClick(cell);
    } else if (want === "collapse") {
      article.classList.add("hf-collapsed");
      const note = document.createElement("div");
      note.className = "hf-note";
      const label = document.createElement("span");
      label.textContent = "Hidden by Hushfeed · " + reason;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "Show";
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        reveal(cell);
      });
      note.append(label, btn);
      cell.prepend(note);
    }
  }

  function notify() {
    try {
      const r = chrome.runtime.sendMessage({ type: "hf:count", count: seen.size });
      if (r && r.catch) r.catch(() => {});
    } catch (_) {}
  }

  async function flush() {
    const n = pending;
    pending = 0;
    if (!n) return;
    try {
      const { stats } = await chrome.storage.local.get("stats");
      await chrome.storage.local.set({ stats: { total: ((stats && stats.total) || 0) + n } });
    } catch (_) {}
  }

  function track(article, reason) {
    const key = tweetKey(article) || reason + "|" + article.textContent.slice(0, 80);
    if (!seen.has(key)) {
      seen.add(key);
      notify();
    }
    if (!counted.has(key)) {
      counted.add(key);
      pending++;
      clearTimeout(flushTimer);
      flushTimer = setTimeout(flush, 2000);
    }
  }

  function scan() {
    scheduled = false;
    const place = currentPlace();
    document.querySelectorAll('article[data-testid="tweet"]').forEach((article) => {
      const sig = version + "|" + place + "|" + sigOf(article.textContent);
      if (article.__hfSig === sig) return;
      article.__hfSig = sig;
      const reason = evaluate(article, place);
      apply(article, reason);
      if (reason) track(article, reason);
    });
  }

  function schedule(delay = 150) {
    if (scheduled) return;
    scheduled = true;
    setTimeout(scan, delay);
  }

  async function refresh() {
    settings = await HF.load();
    compile();
    version++;
    seen.clear(); // the page count is rebuilt from the posts that match the new settings
    notify();
    schedule(0);
  }

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "local" && changes[HF.KEY]) refresh();
  });

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg && msg.type === "hf:get-state") sendResponse({ count: seen.size });
  });

  new MutationObserver(() => schedule()).observe(document.body, { childList: true, subtree: true });

  notify();
  refresh();
})();
