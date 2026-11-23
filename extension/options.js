const $ = (s) => document.querySelector(s);
let S = HF.sanitize(null);

function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k === "checked") n.checked = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  n.append(...kids);
  return n;
}

async function commit() {
  await HF.save(S);
  render();
}

function removeBtn(label, onClick) {
  return el("button", { type: "button", class: "icon-btn", "aria-label": "Remove " + label, text: "×", onclick: onClick });
}

function renderKeywords() {
  const ul = $("#kwList");
  ul.replaceChildren();
  for (const k of S.keywords) {
    const tags = [];
    if (k.regex) tags.push("Regex");
    else if (k.wholeWord) tags.push("Whole word");
    if (k.caseSensitive) tags.push("Case-sensitive");
    if (k.scope === "all") tags.push("Includes author");

    const toggle = el(
      "label",
      { class: "switch small", title: k.on ? "Pause this rule" : "Resume this rule" },
      el("input", {
        type: "checkbox",
        checked: k.on,
        "aria-label": "Rule active: " + k.text,
        onchange: (e) => {
          k.on = e.target.checked;
          commit();
        }
      }),
      el("span", { class: "track" })
    );

    ul.append(
      el(
        "li",
        { class: k.on ? "" : "off" },
        toggle,
        el(
          "div",
          { class: "row-main" },
          el("span", { class: "term" + (k.regex ? " mono" : ""), text: k.text }),
          el("span", { class: "tags" }, ...tags.map((t) => el("span", { class: "tag", text: t })))
        ),
        removeBtn(k.text, () => {
          S.keywords = S.keywords.filter((x) => x.id !== k.id);
          commit();
        })
      )
    );
  }
}

function renderSimpleList(listSel, items, remove, prefix = "") {
  const ul = $(listSel);
  ul.replaceChildren();
  for (const item of items) {
    ul.append(
      el(
        "li",
        {},
        el("div", { class: "row-main" }, el("span", { class: "term", text: prefix + item })),
        removeBtn(prefix + item, () => remove(item))
      )
    );
  }
}

async function renderStats() {
  const { stats } = await chrome.storage.local.get("stats");
  const total = (stats && stats.total) || 0;
  $("#statsLine").textContent = total ? "So far Hushfeed has filtered " + total.toLocaleString() + " posts." : "";
}

function render() {
  $("#enabled").checked = S.enabled;
  $("#masterLabel").textContent = S.enabled ? "Filtering on" : "Filtering paused";
  renderKeywords();
  renderSimpleList("#acList", S.accounts, (h) => { S.accounts = S.accounts.filter((x) => x !== h); commit(); }, "@");
  renderSimpleList("#alList", S.allow, (p) => { S.allow = S.allow.filter((x) => x !== p); commit(); });
  document.querySelectorAll('input[name="mode"]').forEach((r) => (r.checked = r.value === S.mode));
  document.querySelectorAll("[data-place]").forEach((c) => (c.checked = S.places[c.dataset.place]));
  $("#promoted").checked = S.hidePromoted;
}

function showError(sel, msg) {
  const e = $(sel);
  e.textContent = msg;
  e.hidden = !msg;
}

// Keywords
$("#kwForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("#kwText").value.trim();
  if (!text) return;
  if (text.length > HF.LIMITS.text) return showError("#kwError", "Use up to " + HF.LIMITS.text + " characters. Your rule has not been saved.");
  const regex = $("#kwRegex").checked;
  if (regex && !HF.validateRegex(text)) return showError("#kwError", "That regular expression isn’t valid.");
  if (S.keywords.length >= HF.LIMITS.keywords) return showError("#kwError", "You’ve reached the limit of " + HF.LIMITS.keywords + " rules.");
  showError("#kwError", "");
  const rule = HF.cleanKeyword({
    text,
    regex,
    wholeWord: $("#kwWhole").checked,
    caseSensitive: $("#kwCase").checked,
    scope: $("#kwScope").value
  });
  S.keywords.unshift(rule);
  $("#kwText").value = "";
  commit();
});

// Accounts
$("#acForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const raw = $("#acText").value.trim();
  if (!raw) return;
  const handle = HF.cleanHandle(raw);
  if (!handle) return showError("#acError", "Usernames use letters, numbers and underscores, up to 15 characters.");
  if (!S.accounts.includes(handle) && S.accounts.length >= HF.LIMITS.accounts) return showError("#acError", "You’ve reached the limit of " + HF.LIMITS.accounts + " accounts. Remove an account before adding another.");
  showError("#acError", "");
  if (!S.accounts.includes(handle)) S.accounts.unshift(handle);
  $("#acText").value = "";
  commit();
});

// Exceptions
$("#alForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const phrase = HF.cleanPhrase($("#alText").value);
  if (!phrase) return;
  if (phrase.length > HF.LIMITS.text) return showError("#alError", "Use up to " + HF.LIMITS.text + " characters.");
  const exists = S.allow.some((p) => p.toLowerCase() === phrase.toLowerCase());
  if (!exists && S.allow.length >= HF.LIMITS.allow) return showError("#alError", "You’ve reached the limit of " + HF.LIMITS.allow + " exceptions. Remove one before adding another.");
  showError("#alError", "");
  if (!exists) S.allow.unshift(phrase);
  $("#alText").value = "";
  commit();
});

// Behavior
$("#enabled").addEventListener("change", (e) => { S.enabled = e.target.checked; commit(); });
document.querySelectorAll('input[name="mode"]').forEach((r) => r.addEventListener("change", () => { S.mode = r.value; commit(); }));
document.querySelectorAll("[data-place]").forEach((c) => c.addEventListener("change", () => { S.places[c.dataset.place] = c.checked; commit(); }));
$("#promoted").addEventListener("change", (e) => { S.hidePromoted = e.target.checked; commit(); });

// Backup
const backupMsg = (t) => ($("#backupMsg").textContent = t);

$("#exportBtn").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(S, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = el("a", { href: url, download: "hushfeed-settings.json" });
  document.body.append(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  backupMsg("Settings exported.");
});

$("#importBtn").addEventListener("click", () => $("#importFile").click());
$("#importFile").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  try {
    const parsed = JSON.parse(await file.text());
    const imported = HF.importSettings(parsed);
    await HF.save(imported);
    S = imported;
    render();
    backupMsg("Imported " + S.keywords.length + " keyword rules, " + S.accounts.length + " accounts and " + S.allow.length + " exceptions.");
  } catch (_) {
    backupMsg("That file couldn’t be read. Choose a file exported from Hushfeed.");
  }
});

$("#resetBtn").addEventListener("click", async () => {
  if (!confirm("Remove all rules and statistics and restore the default settings?")) return;
  try {
    const result = await chrome.runtime.sendMessage({ type: "hf:reset" });
    if (!result || !result.ok) throw new Error("Reset failed");
    S = await HF.load();
    render();
    await renderStats();
    backupMsg("Settings and statistics reset.");
  } catch (_) {
    backupMsg("Reset failed. Please try again.");
  }
});

// Keep the page in sync if the popup changes something
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local") return;
  if (changes[HF.KEY]) { S = HF.sanitize(changes[HF.KEY].newValue); render(); }
  if (changes.stats) renderStats();
});

$("#version").textContent = "v" + chrome.runtime.getManifest().version;
HF.load().then((s) => { S = s; render(); });
renderStats();
