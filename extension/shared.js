// Shared by the content script, the popup and the options page.
const HF = (() => {
  const KEY = "settings";

  const DEFAULTS = {
    enabled: true,
    mode: "hide", // hide | collapse | blur
    keywords: [], // { id, text, on, regex, wholeWord, caseSensitive, scope: "text" | "all" }
    accounts: [], // lowercase handles, without @
    allow: [], // exception phrases
    hidePromoted: false,
    places: { home: true, search: true, profile: true, thread: false, other: true }
  };

  const LIMITS = { keywords: 500, accounts: 500, allow: 200, text: 200 };
  const MODES = ["hide", "collapse", "blur"];

  const uid = () => Math.random().toString(36).slice(2, 10);

  function cleanKeyword(k) {
    if (!k || typeof k.text !== "string") return null;
    const text = k.text.trim().slice(0, LIMITS.text);
    if (!text) return null;
    return {
      id: typeof k.id === "string" ? k.id : uid(),
      text,
      on: k.on !== false,
      regex: !!k.regex,
      wholeWord: !!k.wholeWord,
      caseSensitive: !!k.caseSensitive,
      scope: k.scope === "all" ? "all" : "text"
    };
  }

  function cleanHandle(h) {
    if (typeof h !== "string") return null;
    const v = h.trim().replace(/^@/, "").toLowerCase();
    return /^[a-z0-9_]{1,15}$/.test(v) ? v : null;
  }

  function cleanPhrase(p) {
    if (typeof p !== "string") return null;
    const v = p.trim().slice(0, LIMITS.text);
    return v || null;
  }

  const uniq = (arr) => Array.from(new Set(arr));

  function sanitize(raw) {
    const r = raw && typeof raw === "object" ? raw : {};
    const places = {};
    for (const key of Object.keys(DEFAULTS.places)) {
      const v = r.places && typeof r.places === "object" ? r.places[key] : undefined;
      places[key] = typeof v === "boolean" ? v : DEFAULTS.places[key];
    }
    const list = (v) => (Array.isArray(v) ? v : []);
    return {
      enabled: r.enabled !== false,
      mode: MODES.includes(r.mode) ? r.mode : DEFAULTS.mode,
      keywords: list(r.keywords).map(cleanKeyword).filter(Boolean).slice(0, LIMITS.keywords),
      accounts: uniq(list(r.accounts).map(cleanHandle).filter(Boolean)).slice(0, LIMITS.accounts),
      allow: uniq(list(r.allow).map(cleanPhrase).filter(Boolean)).slice(0, LIMITS.allow),
      hidePromoted: !!r.hidePromoted,
      places
    };
  }

  async function load() {
    const got = await chrome.storage.local.get(KEY);
    return sanitize(got[KEY]);
  }

  function save(settings) {
    return chrome.storage.local.set({ [KEY]: sanitize(settings) });
  }

  const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  function compileKeyword(k) {
    try {
      if (k.regex) return new RegExp(k.text, k.caseSensitive ? "" : "i");
      let src = escapeRe(k.text);
      if (k.wholeWord) src = `(?<![\\p{L}\\p{N}_])${src}(?![\\p{L}\\p{N}_])`;
      return new RegExp(src, k.caseSensitive ? "u" : "iu");
    } catch {
      return null;
    }
  }

  function validateRegex(text) {
    try {
      new RegExp(text);
      return true;
    } catch {
      return false;
    }
  }

  return { KEY, DEFAULTS, LIMITS, uid, sanitize, load, save, cleanKeyword, cleanHandle, cleanPhrase, compileKeyword, validateRegex };
})();
