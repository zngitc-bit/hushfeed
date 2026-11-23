const $ = (s) => document.querySelector(s);
let S = HF.sanitize(null);
let pageCount = null;

const commit = () => HF.save(S);

function renderStatus() {
  const el = $("#status");
  if (!S.enabled) el.textContent = "Filtering is paused.";
  else if (pageCount === null) el.textContent = "Open x.com to start filtering.";
  else if (pageCount === 0) el.textContent = "Nothing hidden on this page yet.";
  else el.textContent = pageCount + (pageCount === 1 ? " post" : " posts") + " hidden on this page.";
}

function render() {
  $("#enabled").checked = S.enabled;
  document.querySelectorAll('input[name="mode"]').forEach((r) => (r.checked = r.value === S.mode));
  renderStatus();

  const list = $("#list");
  list.replaceChildren();
  $("#empty").hidden = S.keywords.length > 0;

  for (const k of S.keywords) {
    const li = document.createElement("li");
    if (!k.on) li.className = "off";

    const term = document.createElement("span");
    term.className = "term" + (k.regex ? " mono" : "");
    term.textContent = k.text;

    li.append(term);
    if (k.regex) {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = "Regex";
      li.append(tag);
    }

    const rm = document.createElement("button");
    rm.type = "button";
    rm.className = "icon-btn";
    rm.textContent = "×";
    rm.setAttribute("aria-label", "Remove " + k.text);
    rm.addEventListener("click", () => {
      S.keywords = S.keywords.filter((x) => x.id !== k.id);
      commit();
      render();
    });
    li.append(rm);
    list.append(li);
  }
}

$("#addForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("#word").value.trim();
  if (!text) return;
  const dupe = S.keywords.some((k) => !k.regex && !k.wholeWord && !k.caseSensitive && k.text.toLowerCase() === text.toLowerCase());
  if (!dupe && S.keywords.length < HF.LIMITS.keywords) {
    S.keywords.unshift(HF.cleanKeyword({ text }));
    commit();
  }
  $("#word").value = "";
  render();
});

$("#enabled").addEventListener("change", (e) => {
  S.enabled = e.target.checked;
  commit();
  renderStatus();
});

document.querySelectorAll('input[name="mode"]').forEach((r) =>
  r.addEventListener("change", () => {
    S.mode = r.value;
    commit();
  })
);

$("#openOptions").addEventListener("click", () => chrome.runtime.openOptionsPage());

async function init() {
  S = await HF.load();
  render();

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.id) {
      const res = await chrome.tabs.sendMessage(tab.id, { type: "hf:get-state" });
      pageCount = res ? res.count : null;
    }
  } catch (_) {
    pageCount = null;
  }
  renderStatus();

  const { stats } = await chrome.storage.local.get("stats");
  const total = (stats && stats.total) || 0;
  $("#total").textContent = total ? total.toLocaleString() + " hidden in total" : "";
}
init();
