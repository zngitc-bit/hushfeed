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
  const TEXT_BLOCKS = new Set(["ARTICLE", "DIV", "P", "SECTION", "HEADER", "FOOTER", "BLOCKQUOTE", "LI", "H1", "H2", "H3"]);
  const POST_SELECTOR = 'article[data-testid="tweet"], [role="link"][data-href*="/status/"] > article';

  function postLink(article) {
    const parent = article.parentElement;
    return parent && parent.matches('[role="link"][data-href*="/status/"]') ? parent : null;
  }

  function postCell(article) {
    return article.closest('[data-testid="cellInnerDiv"]') || postLink(article) || article;
  }

  let settings = HF.sanitize(null);
  let rules = [];
  let allow = [];
  let version = 0;
  let scanTimer = null;
  let scanning = false;
  let rescan = false;
  let statsEpoch = 0;
  let ready = false;

  const seen = new Set(); // hidden posts on this page, shown in the badge
  const counted = new Set(); // posts already added to the lifetime total

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
    const link = postLink(article);
    const author = link && link.getAttribute("data-href").match(/^\/([A-Za-z0-9_]{1,15})\/status\/\d+/);
    if (author) return author[1].toLowerCase();
    const links = article.querySelectorAll('[data-testid="User-Name"] a[href^="/"]');
    for (const a of links) {
      const m = (a.getAttribute("href") || "").match(/^\/([A-Za-z0-9_]{1,15})$/);
      if (m) return m[1].toLowerCase();
    }
    return null;
  }

  function tweetKey(article) {
    const link = postLink(article);
    const id = link && link.getAttribute("data-href").match(/\/status\/(\d+)/);
    if (id) return id[1];
    const time = article.querySelector('a[href*="/status/"] time');
    const href = time && time.parentElement && time.parentElement.getAttribute("href");
    const m = href && href.match(/\/status\/(\d+)/);
    return m ? m[1] : null;
  }

  // Text of a node, with emoji (rendered by X as <img alt="...">) kept in place.
  function textOf(el, separateBlocks = false) {
    let out = "";
    const lineBreak = () => { if (out && !out.endsWith("\n")) out += "\n"; };
    const walk = (n) => {
      if (n.nodeType === 3) out += n.nodeValue;
      else if (n.nodeType === 1) {
        if (n.tagName === "IMG") out += n.alt || "";
        else if (n.tagName === "BR") out += "\n";
        else {
          const block = separateBlocks && TEXT_BLOCKS.has(n.tagName);
          if (block) lineBreak();
          n.childNodes.forEach(walk);
          if (block) lineBreak();
        }
      }
    };
    walk(el);
    return out;
  }

  function isPromoted(article) {
    if (article.querySelector('[data-testid="promotedIndicator"]')) return true;
    // Labels live outside post text, author names, quoted posts and link cards.
    return Array.from(article.querySelectorAll("span, div")).some((node) =>
      node.childElementCount === 0 && PROMO_LABELS.has(node.textContent.trim()) &&
      !node.closest('[data-testid="tweetText"], [lang][dir="auto"], [data-testid="User-Name"], a, [data-testid="card.wrapper"], [data-testid="quoteTweet"]') &&
      (!node.closest('[role="link"]') || node.closest('[role="link"]') === postLink(article))
    );
  }

  function snapshot(article) {
    const legacyText = article.querySelectorAll('[data-testid="tweetText"]');
    const textNodes = legacyText.length ? legacyText : article.querySelectorAll('[lang][dir="auto"]');
    const text = Array.from(textNodes).map((node) => textOf(node)).join("\n");
    const handle = authorHandle(article);
    return {
      text,
      // Keep block boundaries even when our CSS hides the article. innerText
      // changes behavior for hidden elements and can make matching oscillate.
      full: textOf(article, true),
      handle,
      promoted: isPromoted(article),
      key: tweetKey(article) || JSON.stringify([handle, text])
    };
  }

  // Evaluate regex away from the page's main thread. Plain keyword rules stay local.
  async function evaluate(post, place, revision) {
    if (!settings.enabled || !settings.places[place]) return null;
    const text = post.text;

    if (allow.length) {
      const lower = text.toLowerCase();
      if (allow.some((a) => lower.includes(a))) return null;
    }

    if (settings.accounts.length) {
      const handle = post.handle;
      if (handle && settings.accounts.includes(handle)) return "@" + handle;
    }

    if (settings.hidePromoted && post.promoted) return "Promoted";

    for (const { k, re } of rules) {
      if (revision !== version) return null;
      const hay = k.scope === "all" ? post.full : text;
      const matched = k.regex ? await HFRegex.test(k, hay) : re.test(hay);
      if (matched) return "“" + k.text + "”";
    }
    return null;
  }

  function clear(cell) {
    cell.classList.remove("hf-hide");
    if (cell.matches("article")) {
      cell.classList.remove("hf-blur", "hf-collapsed");
      cell.removeAttribute("title");
    }
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

  function apply(article, reason, key) {
    const cell = postCell(article);

    if (cell.__hfArticle !== article || cell.__hfKey !== key) {
      clear(cell);
      cell.__hfArticle = article;
      cell.__hfKey = key;
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
      const r = chrome.runtime.sendMessage({ type: "hf:count", count: seen.size, regexWarning: HFRegex.warning });
      if (r && r.catch) r.catch(() => {});
    } catch (_) {}
  }

  async function scan() {
    if (!ready) return;
    scanning = true;
    const place = currentPlace();
    const revision = version;
    const route = location.href;
    const current = new Set();
    const newlyCounted = new Set();
    try {
      for (const article of document.querySelectorAll(POST_SELECTOR)) {
        // Quoted articles belong to their enclosing post, not a separate feed row.
        if (article.parentElement.closest("article")) continue;
        const post = snapshot(article);
        const content = JSON.stringify(post);
        const sig = revision + "|" + route + "|" + content;
        let reason = article.__hfReason;
        if (article.__hfSig !== sig) {
          reason = await evaluate(post, place, revision);
          if (revision !== version || route !== location.href) { rescan = true; return; }
          if (!article.isConnected || JSON.stringify(snapshot(article)) !== content) { rescan = true; continue; }
          article.__hfSig = sig;
          article.__hfReason = reason;
          apply(article, reason, post.key);
        }
        if (reason) {
          const cell = postCell(article);
          if (cell.dataset.hfState !== "revealed") current.add(post.key);
          if (!counted.has(post.key)) newlyCounted.add(post.key);
        }
      }
      seen.clear();
      current.forEach((key) => seen.add(key));
      notify();
      if (newlyCounted.size) {
        newlyCounted.forEach((key) => counted.add(key));
        chrome.runtime.sendMessage({ type: "hf:stats", count: newlyCounted.size, epoch: statsEpoch }).catch(() => {});
      }
    } finally {
      scanning = false;
      if (rescan) { rescan = false; schedule(0); }
    }
  }

  function schedule(delay = 150) {
    if (scanning) { rescan = true; return; }
    if (scanTimer !== null) return;
    scanTimer = setTimeout(() => { scanTimer = null; scan(); }, delay);
  }

  async function refresh() {
    const revision = ++version;
    ready = false;
    const stored = await chrome.storage.local.get([HF.KEY, "stats"]);
    if (revision !== version) return;
    settings = HF.sanitize(stored[HF.KEY]);
    const epoch = stored.stats && stored.stats.epoch || 0;
    if (epoch !== statsEpoch) counted.clear();
    statsEpoch = epoch;
    compile();
    ready = true;
    seen.clear(); // the page count is rebuilt from the posts that match the new settings
    notify();
    schedule(0);
  }

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    const reset = changes.stats && (changes.stats.newValue && changes.stats.newValue.epoch || 0) !== statsEpoch;
    if (changes[HF.KEY] || reset) refresh();
  });

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg && msg.type === "hf:get-state") sendResponse({ count: seen.size, regexWarning: HFRegex.warning });
  });

  new MutationObserver(() => schedule()).observe(document.body, {
    childList: true, subtree: true, characterData: true,
    attributes: true, attributeFilter: ["alt", "href", "data-href", "data-testid", "lang", "dir"]
  });
  // X changes routes without loading a new document.
  if (window.navigation) window.navigation.addEventListener("currententrychange", () => schedule(0));
  window.addEventListener("popstate", () => schedule(0));

  notify();
  refresh();
})();
