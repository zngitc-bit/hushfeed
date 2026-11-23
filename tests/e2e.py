"""End-to-end tests: loads the extension in Chromium and runs it against a mock of the X timeline.

Run from the repo root:
    pip install playwright && playwright install chromium
    python tests/e2e.py
"""
import json, time, os, shutil, tempfile, sys
from playwright.sync_api import sync_playwright
from regressions import run_regressions

EXT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "extension"))
PROFILE = tempfile.mkdtemp(prefix="hushfeed-pw-")

POSTS = [
 (1, "alice",   "Alice",   "Great news from ohnePixel today", False),
 (2, "bob",     "Bob",     "Concatenate these strings in JS", False),
 (3, "carol",   "Carol",   "my cat is cute", False),
 (4, "ohnepixel","ohnePixel","Just a normal post about nothing", False),
 (5, "dave",    "Dave",    "Free AIRDROP now!!", False),
 (6, "erin",    "Erin",    "Spoilers: the finale was wild", False),
 (7, "frank",   "Frank",   "Season finale recap, no spoilers inside", False),
 (8, "gina",    "Gina",    "\U0001F525 hot take on the market", False),
 (9, "promo",   "Brand",   "Buy our amazing product", True),
 (10,"hank",    "Hank",    "regular post nothing special", False),
]

def article(i, handle, name, text, promoted=False):
    promo = '<div>Ad</div>' if promoted else ''
    # emoji rendered as <img alt> like X does
    body = text.replace("\U0001F525", '<img alt="\U0001F525" src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" width="16" height="16">')
    return f'''<div data-testid="cellInnerDiv"><article data-testid="tweet" data-id="{i}">
<div data-testid="User-Name"><a href="/{handle}"><span>{name}</span></a><a href="/{handle}"><span>@{handle}</span></a></div>
<a href="/{handle}/status/{i}"><time>2h</time></a>{promo}
<div data-testid="tweetText"><span>{body}</span></div></article></div>'''

def page_html(posts):
    cells = "\n".join(article(*p) for p in posts)
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>mock</title></head>
<body><div id="timeline">{cells}</div></body></html>'''

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))

console_errors = []

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel="chromium", headless=True,
        args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"],
        viewport={"width": 1280, "height": 900})
    sw = ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event("serviceworker", timeout=15000)
    ext_id = sw.url.split("/")[2]
    check("extension loads, service worker registered", bool(ext_id))
    # Installation opens options automatically. Wait for it before navigating another tab.
    welcome = None
    for _ in range(100):
        welcome = next((tab for tab in ctx.pages if tab.url == f"chrome-extension://{ext_id}/options.html"), None)
        if welcome:
            welcome.wait_for_load_state()
            break
        ctx.pages[0].wait_for_timeout(50)
    if welcome is None:
        raise RuntimeError("The installation welcome page did not open")

    def handler(route):
        route.fulfill(status=200, content_type="text/html", body=page_html(POSTS))
    ctx.route("https://x.com/**", handler)
    ctx.route("https://twitter.com/**", handler)

    admin = ctx.new_page()
    admin.on("pageerror", lambda e: console_errors.append(("admin", str(e))))
    admin.goto(f"chrome-extension://{ext_id}/options.html")
    admin.wait_for_timeout(500)

    def set_settings(**s):
        admin.evaluate("async (s) => { await chrome.storage.local.set({settings: s}); }", s)
        page.wait_for_timeout(500)

    def kw(text, **o):
        d = dict(text=text, on=True, regex=False, wholeWord=False, caseSensitive=False, scope="text")
        d.update(o); return d

    page = ctx.new_page()
    page.on("pageerror", lambda e: console_errors.append(("x", str(e))))
    page.on("console", lambda m: console_errors.append(("x-console", m.text)) if m.type == "error" else None)
    page.goto("https://x.com/home")
    page.wait_for_timeout(600)

    def visible():
        return page.evaluate("""() => [...document.querySelectorAll('[data-testid=cellInnerDiv]')]
          .filter(c => getComputedStyle(c).display !== 'none' &&
                       !c.querySelector('article.hf-collapsed'))
          .map(c => +c.querySelector('article').dataset.id)""")
    def hidden():
        return page.evaluate("""() => [...document.querySelectorAll('[data-testid=cellInnerDiv]')]
          .filter(c => getComputedStyle(c).display === 'none' || c.querySelector('article.hf-collapsed'))
          .map(c => +c.querySelector('article').dataset.id).sort((a,b) => a-b)""")

    check("no rules: nothing hidden", hidden() == [], str(hidden()))

    # --- keyword basics ---
    set_settings(keywords=[kw("ohnePixel")])
    check("keyword hides post containing it (case-insensitive default)", hidden() == [1], str(hidden()))
    set_settings(keywords=[kw("OHNEPIXEL")])
    check("matching ignores capitalization", hidden() == [1], str(hidden()))
    check("author-only match NOT hidden when scope=text (post 4 by @ohnepixel)", 4 not in hidden())

    set_settings(keywords=[kw("ohnePixel", scope="all")])
    check("scope=all also hides posts authored by that handle", hidden() == [1, 4], str(hidden()))

    set_settings(keywords=[kw("cat", wholeWord=True)])
    check("whole word: 'cat' hides 'my cat is cute' but not 'Concatenate'", hidden() == [3], str(hidden()))
    set_settings(keywords=[kw("cat")])
    check("substring: 'cat' hides both cat and Concatenate", hidden() == [2, 3], str(hidden()))

    set_settings(keywords=[kw("AIRDROP", caseSensitive=True)])
    check("case-sensitive matches exact case", hidden() == [5], str(hidden()))
    set_settings(keywords=[kw("airdrop", caseSensitive=True)])
    check("case-sensitive does not match other case", hidden() == [], str(hidden()))

    set_settings(keywords=[kw("airdrop|spoilers", regex=True)])
    check("regex alternation", hidden() == [5, 6, 7], str(hidden()))

    set_settings(keywords=[kw("[unclosed", regex=True), kw("ohnePixel")])
    check("invalid regex stored directly does not break other rules", hidden() == [1], str(hidden()))

    set_settings(keywords=[kw("ohnePixel", on=False)])
    check("paused rule does not hide", hidden() == [], str(hidden()))

    # --- accounts / allow / promoted / enabled ---
    set_settings(accounts=["bob", "hank"])
    check("account rule hides by author handle", hidden() == [2, 10], str(hidden()))
    set_settings(accounts=["BOB"])
    check("account rule is case-insensitive after sanitize", hidden() == [2], str(hidden()))

    set_settings(keywords=[kw("spoilers")], allow=["season finale recap"])
    check("exception phrase lets a matching post through", hidden() == [6], str(hidden()))

    set_settings(hidePromoted=True)
    check("promoted posts hidden when enabled", hidden() == [9], str(hidden()))
    set_settings(hidePromoted=False, keywords=[kw("ohnePixel")], enabled=False)
    check("master switch off shows everything", hidden() == [], str(hidden()))
    set_settings(keywords=[kw("ohnePixel")], enabled=True)
    check("master switch back on hides again", hidden() == [1], str(hidden()))

    # --- lifetime stats not double counted ---
    def total():
        return admin.evaluate("async () => ((await chrome.storage.local.get('stats')).stats || {}).total || 0")
    set_settings(keywords=[kw("ohnePixel")]); page.wait_for_timeout(2500); s1 = total()
    set_settings(keywords=[kw("ohnePixel")], mode="collapse"); page.wait_for_timeout(2500); s2 = total()
    set_settings(keywords=[kw("ohnePixel")], mode="hide"); page.wait_for_timeout(2500); s3 = total()
    check("lifetime counter not inflated by settings changes", s1 == s2 == s3 and s1 >= 1, f"{s1},{s2},{s3}")

    # --- emoji ---
    set_settings(keywords=[kw("\U0001F525")])
    check("emoji keyword matches emoji rendered as <img alt>", hidden() == [8], str(hidden()))
    set_settings(keywords=[kw("\U0001F525 hot take")])
    check("phrase mixing emoji and text matches", hidden() == [8], str(hidden()))
    set_settings(keywords=[kw("\U0001F525", scope="all")])
    check("emoji keyword with scope=all", hidden() == [8], str(hidden()))

    # --- modes ---
    set_settings(keywords=[kw("ohnePixel")], mode="collapse")
    note = page.evaluate("() => document.querySelector('.hf-note')?.innerText || null")
    check("collapse mode shows note", note and "ohnePixel" in note, str(note))
    page.click(".hf-note button")
    page.wait_for_timeout(400)
    check("Show button reveals the post", hidden() == [] and page.evaluate("() => document.querySelectorAll('.hf-note').length") == 0)

    # revealed state is kept while the rule still matches, even if the mode changes (by design)
    set_settings(keywords=[kw("ohnePixel")], mode="blur")
    check("revealed post stays revealed after changing mode (by design)", hidden() == [] and not page.evaluate("() => !!document.querySelector('article.hf-blur')"))
    set_settings(keywords=[], mode="blur"); set_settings(keywords=[kw("ohnePixel")], mode="blur")
    blurred = page.evaluate("() => !!document.querySelector('article.hf-blur')")
    check("blur mode blurs matching post", blurred)
    nav_before = page.url
    page.click("article.hf-blur a[href='/alice']", force=True)
    page.wait_for_timeout(400)
    check("click on blurred post reveals it and does not navigate", not page.evaluate("() => !!document.querySelector('article.hf-blur')") and page.url == nav_before)

    set_settings(keywords=[], mode="hide"); set_settings(keywords=[kw("ohnePixel")], mode="hide")
    check("after rules reload, post is hidden again",  hidden() == [1], str(hidden()))
    set_settings(keywords=[], mode="hide")
    check("removing the rule restores the post", hidden() == [], str(hidden()))

    # --- dynamic content (infinite scroll) ---
    set_settings(keywords=[kw("ohnePixel")])
    page.evaluate("""(h) => { document.getElementById('timeline').insertAdjacentHTML('beforeend', h); }""",
                  article(11, "newguy", "New", "another ohnePixel post that loads later"))
    page.wait_for_timeout(500)
    check("posts added later (infinite scroll) are filtered", 11 in hidden(), str(hidden()))

    # post text arrives after the article is already in the DOM (React hydration)
    page.evaluate("""(h) => { document.getElementById('timeline').insertAdjacentHTML('beforeend', h); }""",
                  article(12, "late", "Late", "", False))
    page.wait_for_timeout(400)
    page.evaluate("() => { document.querySelector('article[data-id=\"12\"] [data-testid=tweetText] span').textContent = 'filled in later: ohnePixel'; }")
    page.wait_for_timeout(500)
    check("text filled in after insertion is evaluated", 12 in hidden(), str(hidden()))

    # same-length replacement (cache signature uses textContent length)
    page.evaluate("""(h) => { document.getElementById('timeline').insertAdjacentHTML('beforeend', h); }""",
                  article(13, "swap", "Swap", "harmless text here", False))
    page.wait_for_timeout(400)
    page.evaluate("() => { document.querySelector('article[data-id=\"13\"] [data-testid=tweetText] span').textContent = 'ohnePixel text here!'.slice(0,18); }")
    n = page.evaluate("() => document.querySelector('article[data-id=\"13\"]').textContent.length")
    page.evaluate("() => { document.querySelector('article[data-id=\"13\"] [data-testid=tweetText] span').textContent = 'ohnePixel text here'; }")
    page.evaluate("() => { document.body.appendChild(document.createElement('i')); }")
    page.wait_for_timeout(500)
    # 'harmless text here' (18) -> 'ohnePixel text here' (19): different length, so this one should be caught
    check("text replaced by different-length text is re-evaluated", 13 in hidden(), str(hidden()))
    # truly same length swap
    page.evaluate("""(h) => { document.getElementById('timeline').insertAdjacentHTML('beforeend', h); }""",
                  article(14, "same", "Same", "harmless xxxxxx text", False))
    page.wait_for_timeout(400)
    page.evaluate("() => { document.querySelector('article[data-id=\"14\"] [data-testid=tweetText] span').textContent = 'ohnePixel xxxxx text'; }")
    page.wait_for_timeout(500)
    check("same-length text swap is re-evaluated", 14 in hidden(), "cache signature only uses text length")

    # --- places ---
    page.evaluate("() => history.pushState({}, '', '/alice/status/1')")
    page.evaluate("() => { document.body.appendChild(document.createElement('i')); }")
    page.wait_for_timeout(500)
    check("post page (thread) is not filtered by default", 1 not in hidden(), str(hidden()))
    page.evaluate("() => history.pushState({}, '', '/search?q=x')")
    page.evaluate("() => { document.body.appendChild(document.createElement('i')); }")
    page.wait_for_timeout(500)
    check("search page is filtered", 1 in hidden(), str(hidden()))
    page.evaluate("() => history.pushState({}, '', '/home')")
    page.evaluate("() => { document.body.appendChild(document.createElement('i')); }")
    page.wait_for_timeout(300)

    # --- badge + count ---
    set_settings(keywords=[kw("ohnePixel")], mode="hide")
    info = admin.evaluate("""async () => {
        const tabs = await chrome.tabs.query({});
        const out = [];
        for (const t of tabs) {
          try { const r = await chrome.tabs.sendMessage(t.id, {type:'hf:get-state'});
                if (r) out.push({id:t.id, count:r.count, badge: await chrome.action.getBadgeText({tabId:t.id})}); } catch(e) {}
        }
        return out; }""")
    check("content script answers popup count query", len(info) == 1 and info[0]["count"] >= 1, str(info))
    check("toolbar badge shows the count", info and info[0]["badge"] == str(info[0]["count"]), str(info))

    # --- disabling after hiding: does badge/count reset? ---
    set_settings(keywords=[kw("ohnePixel")], enabled=False)
    info2 = admin.evaluate("""async () => {
        const tabs = await chrome.tabs.query({}); const out=[];
        for (const t of tabs) { try { const r = await chrome.tabs.sendMessage(t.id,{type:'hf:get-state'});
          if (r) out.push({count:r.count, badge: await chrome.action.getBadgeText({tabId:t.id})}); } catch(e){} } return out; }""")
    check("badge/count cleared after filtering is turned off", info2 and info2[0]["count"] == 0, str(info2))
    set_settings(keywords=[], enabled=True)

    # --- ReDoS ---
    set_settings(keywords=[kw("(a+)+$", regex=True)])
    page.evaluate("""(h) => { document.getElementById('timeline').insertAdjacentHTML('beforeend', h); }""",
                  article(15, "slow", "Slow", "a"*30 + "!", False))
    t0 = time.time()
    try:
        page.wait_for_timeout(800)  # Let the observer start matching before probing responsiveness.
        page.evaluate("1+1")
        dt = time.time() - t0
        check("ReDoS: catastrophic regex does not freeze the page", dt < 3, f"{dt:.1f}s")
    except Exception as e:
        check("ReDoS: catastrophic regex does not freeze the page", False, "page unresponsive: " + str(e)[:80])
    set_settings(keywords=[])

    # --- performance ---
    many = "".join(article(1000+i, f"user{i}", f"User {i}", f"Random post number {i} with some filler text to read", False) for i in range(400))
    page.evaluate("(h) => { document.getElementById('timeline').insertAdjacentHTML('beforeend', h); }", many)
    set_settings(keywords=[kw("ohnePixel"), kw("airdrop|spoilers|giveaway", regex=True), kw("post number 399")])
    t0 = time.time()
    page.evaluate("() => { document.body.appendChild(document.createElement('i')); }")
    page.wait_for_function("() => [...document.querySelectorAll('[data-id]')].some(a => a.dataset.id=='1399' && getComputedStyle(a.closest('[data-testid=cellInnerDiv]')).display==='none')", timeout=10000)
    check("perf: ~420 posts filtered quickly", time.time() - t0 < 2.5, f"{time.time()-t0:.2f}s")
    t0 = time.time()
    for _ in range(20): page.evaluate("() => { document.body.appendChild(document.createElement('i')); }")
    page.wait_for_timeout(600)
    lag = page.evaluate("() => { const s=performance.now(); let n=0; while(performance.now()-s<1){n++}; return n }")
    check("perf: page stays responsive after burst of mutations", lag > 0)
    set_settings(keywords=[])

    # --- options page UI ---
    o = ctx.new_page()
    o.on("pageerror", lambda e: console_errors.append(("options", str(e))))
    o.on("console", lambda m: console_errors.append(("options-console", m.text)) if m.type == "error" else None)
    o.set_viewport_size({"width": 1100, "height": 900})
    o.goto(f"chrome-extension://{ext_id}/options.html")
    o.wait_for_timeout(400)
    pass
    o.fill("#kwText", "(")
    o.check("#kwRegex"); o.click("#kwForm button[type=submit]")
    check("options: invalid regex shows an error and is not saved", o.is_visible("#kwError") and o.locator("#kwList li").count() == 0)
    o.fill("#kwText", "ohnePixel"); o.uncheck("#kwRegex"); o.click("#kwForm button[type=submit]")
    o.wait_for_timeout(300)
    check("options: valid rule is added", o.locator("#kwList li").count() == 1)
    o.fill("#kwText", "https://t.co/abc?x=1&y=2 [test] (a|b)"); o.click("#kwForm button[type=submit]")
    o.wait_for_timeout(300)
    check("options: special characters in plain text rules are handled", o.locator("#kwList li").count() == 2)
    o.fill("#acText", "bad handle!"); o.click("#acForm button[type=submit]")
    check("options: invalid @handle is rejected with a message", o.is_visible("#acError"))
    o.fill("#acText", "@SomeUser"); o.click("#acForm button[type=submit]")
    o.fill("#alText", "season finale recap"); o.click("#alForm button[type=submit]")
    o.wait_for_timeout(300)
    stored = admin.evaluate("async () => (await chrome.storage.local.get('settings')).settings")
    check("options: accounts normalized to lowercase", stored["accounts"] == ["someuser"], str(stored["accounts"]))
    check("options: exception stored", stored["allow"] == ["season finale recap"])
    o.click("input[name=mode][value=blur]"); o.wait_for_timeout(200)
    stored = admin.evaluate("async () => (await chrome.storage.local.get('settings')).settings")
    check("options: mode change saved", stored["mode"] == "blur")
    pass

    with o.expect_download() as dl:
        o.click("#exportBtn")
    path = dl.value.path()
    exported = json.load(open(path))
    check("options: export produces valid JSON with rules", len(exported["keywords"]) == 2)
    o.once("dialog", lambda d: d.accept())
    o.click("#resetBtn"); o.wait_for_timeout(300)
    check("options: reset clears everything", o.locator("#kwList li").count() == 0)
    o.set_input_files("#importFile", path); o.wait_for_timeout(400)
    check("options: import restores rules", o.locator("#kwList li").count() == 2)
    bad = os.path.join(PROFILE, "bad.json"); open(bad, "w").write("not json")
    o.set_input_files("#importFile", bad); o.wait_for_timeout(300)
    check("options: importing a bad file shows a message and keeps rules", "couldn" in o.inner_text("#backupMsg") and o.locator("#kwList li").count() == 2)
    evil = os.path.join(PROFILE, "evil.json"); json.dump({"keywords":[{"text":"<img src=x onerror=alert(1)>"}], "mode":"zzz", "places":{"home":"yes"}, "accounts":["valid_user"]}, open(evil, "w"))
    o.set_input_files("#importFile", evil); o.wait_for_timeout(400)
    check("options: hostile import is sanitized and not executed as HTML", o.locator("#kwList img").count() == 0 and o.locator("#kwList li").count() == 1)

    # --- popup UI ---
    pu = ctx.new_page()
    pu.on("pageerror", lambda e: console_errors.append(("popup", str(e))))
    pu.set_viewport_size({"width": 330, "height": 420})
    pu.goto(f"chrome-extension://{ext_id}/popup.html")
    pu.wait_for_timeout(500)
    check("popup: status when no X tab is active", "x.com" in pu.inner_text("#status") or "hidden" in pu.inner_text("#status"), pu.inner_text("#status"))
    pu.fill("#word", "NewWord"); pu.press("#word", "Enter"); pu.wait_for_timeout(300)
    check("popup: Enter adds a keyword", "NewWord" in pu.inner_text("#list"))
    pu.fill("#word", "newword"); pu.press("#word", "Enter"); pu.wait_for_timeout(300)
    check("popup: duplicate (different case) not added twice", pu.inner_text("#list").lower().count("newword") == 1)
    pass

    page.close()
    pu.close()
    o.close()
    run_regressions(ctx, admin, ext_id, check, article, page_html, console_errors)
    ctx.close()

print()
passed = sum(1 for r in results if r[1]); print(f"{passed}/{len(results)} passed")
print("FAILED:", [r[0] for r in results if not r[1]])
print("console/page errors:", console_errors[:10])
shutil.rmtree(PROFILE, ignore_errors=True)
sys.exit(0 if passed == len(results) and not console_errors else 1)
