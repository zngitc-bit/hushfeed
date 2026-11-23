import json


def run_regressions(ctx, admin, ext_id, check, article, page_html, errors):
    page = ctx.new_page()
    page.on("pageerror", lambda error: errors.append(("regressions", str(error))))
    page.route("https://x.com/**", lambda route: route.fulfill(
        content_type="text/html",
        body=page_html([(1, "alice", "Alice", "harmless", False)])))

    def settings(**values):
        admin.evaluate("(s) => chrome.storage.local.set({settings:s})", values)
        admin.wait_for_timeout(350)

    def fresh(**values):
        settings(**values)
        page.goto("https://x.com/home")
        page.wait_for_timeout(450)

    def rule(text, **extra):
        return {"id": "test", "text": text, "on": True, **extra}

    def state():
        return page.locator('[data-testid="cellInnerDiv"]').first.get_attribute("data-hf-state")

    def stored():
        return admin.evaluate('async () => (await chrome.storage.local.get("settings")).settings')

    def count():
        return admin.evaluate('''async () => {
            const tabs = await chrome.tabs.query({});
            for (const tab of tabs) {
                try { return await chrome.tabs.sendMessage(tab.id, {type:"hf:get-state"}); } catch (_) {}
            }
        }''')

    def import_data(data):
        admin.set_input_files("#importFile", {
            "name": "settings.json", "mimeType": "application/json",
            "buffer": json.dumps(data).encode("utf-8")})
        admin.wait_for_timeout(350)

    fresh(keywords=[rule("spoiler")])
    page.evaluate('() => document.querySelector("[data-testid=tweetText] span").firstChild.nodeValue = "spoiler!"')
    page.wait_for_timeout(350)
    check("regression: direct text mutation is filtered", state() == "hide")
    page.evaluate('() => document.querySelector("[data-testid=tweetText] span").firstChild.nodeValue = "harmless"')
    page.wait_for_timeout(350)
    check("regression: changing text back restores post", state() is None)

    fresh(keywords=[rule("🔥")])
    page.evaluate('() => document.querySelector("[data-testid=tweetText] span").appendChild(Object.assign(document.createElement("img"),{alt:"🔥"}))')
    page.wait_for_timeout(350)
    check("regression: emoji inserted after scan is filtered", state() == "hide")
    page.evaluate('() => document.querySelector("img").alt = "🌻"')
    page.wait_for_timeout(350)
    check("regression: emoji alt update restores post", state() is None)

    fresh(keywords=[rule("alice", scope="all", wholeWord=True)])
    page.evaluate('() => { const a=document.querySelector("article"); a.innerHTML=a.innerHTML.replaceAll("\\n", ""); }')
    page.wait_for_timeout(350)
    check("regression: whole-word author match preserves adjacent block boundaries", state() == "hide")
    page.evaluate('() => document.body.appendChild(document.createElement("i"))')
    page.wait_for_timeout(350)
    check("regression: author match remains stable while hidden", state() == "hide")
    settings(keywords=[rule("new\\s+line", scope="all", regex=True)])
    page.evaluate('() => document.querySelector("[data-testid=tweetText]").innerHTML="<div>new</div><div>line</div>"')
    page.wait_for_function('() => !!document.querySelector(".hf-hide")', timeout=5000)
    check("regression: full-text regex preserves rendered line boundaries", state() == "hide")
    settings(keywords=[rule("newline", scope="all")])
    check("regression: adjacent blocks cannot create a false keyword", state() is None)

    for mode in ["collapse", "blur"]:
        fresh(keywords=[rule("harmless")], mode=mode)
        page.click(".hf-note button" if mode == "collapse" else "article")
        page.wait_for_timeout(250)
        check(f"regression: {mode} reveals post", state() == "revealed")
        page.evaluate('() => document.querySelector("a[href*=status]").href="/alice/status/2"')
        page.wait_for_timeout(350)
        check(f"regression: recycled {mode} article with same text is filtered", state() == mode)

    fresh(keywords=[rule("harmless")])
    page.evaluate('() => history.pushState({}, "", "/alice/status/1")')
    page.wait_for_timeout(350)
    check("regression: route change alone restores thread post and badge", state() is None and count()["count"] == 0)
    page.evaluate('() => history.pushState({}, "", "/search?q=test")')
    page.wait_for_timeout(350)
    check("regression: search route reapplies filter and badge", state() == "hide" and count()["count"] == 1)
    page.evaluate('() => document.querySelector("[data-testid=cellInnerDiv]").remove()')
    page.wait_for_timeout(350)
    check("regression: removing a post updates current count", count()["count"] == 0)

    fresh(hidePromoted=True)
    page.evaluate('() => document.querySelector("[data-testid=tweetText] span").textContent="Ad"')
    page.wait_for_timeout(350)
    check("regression: ordinary Ad text remains visible", state() is None)
    page.evaluate('() => document.querySelector("[data-testid=User-Name] span").textContent="Promoted"')
    page.wait_for_timeout(350)
    check("regression: author named Promoted remains visible", state() is None)
    page.evaluate('() => document.querySelector("article").appendChild(Object.assign(document.createElement("span"),{textContent:"Promovat"}))')
    page.wait_for_timeout(350)
    check("regression: localized ad label still filters", state() == "hide")

    settings(keywords=[rule("important")])
    for invalid in [{"theme": "dark"}, {}, [], {"keywords": "spoiler"}, {"keywords": [None]},
                    {"accounts": ["invalid handle"]}, {"keywords": [{"text": "a" * 201}]},
                    {"keywords": [{"text": "(", "regex": True}]}, {"allow": ["x"] * 201}]:
        import_data(invalid)
        check("regression: invalid backup preserves current settings", stored()["keywords"][0]["text"] == "important", str(invalid)[:80])
    import_data({"keywords": [{"text": "legacy"}]})
    check("regression: older partial backup remains supported", stored()["keywords"][0]["text"] == "legacy")
    import_data({"keywords": [], "accounts": [], "allow": []})
    check("regression: valid empty backup can clear rules", stored()["keywords"] == [])

    for field, limit, prefix, form, error in [
        ("accounts", 500, "user", "ac", "#acError"),
        ("allow", 200, "phrase", "al", "#alError")
    ]:
        original = [f"{prefix}{i}" for i in range(limit)]
        settings(**{field: original})
        admin.fill(f"#{form}Text", "newentry")
        admin.click(f"#{form}Form button")
        admin.wait_for_timeout(350)
        check(f"regression: {field} limit preserves all entries and reports error", stored()[field] == original and admin.locator(error).is_visible())

    settings(keywords=[])
    admin.fill("#kwText", "(" + "a" * 199 + ")")
    admin.check("#kwRegex")
    admin.click("#kwForm button")
    admin.wait_for_timeout(250)
    check("regression: oversized regex rejected before storage", stored()["keywords"] == [] and admin.locator("#kwError").is_visible())
    admin.fill("#kwText", "(" + "a" * 198 + ")")
    admin.click("#kwForm button")
    admin.wait_for_timeout(350)
    check("regression: 200-character regex saved intact", len(stored()["keywords"][0]["text"]) == 200 and stored()["keywords"][0]["text"].endswith(")"))
    settings(keywords=[rule("a" * 201)])
    check("regression: preexisting long rule survives loading and saving", admin.evaluate('() => HF.save(S).then(() => S.keywords[0].text.length)') == 201)

    popup = ctx.new_page()
    popup.goto(f"chrome-extension://{ext_id}/popup.html")
    popup.wait_for_timeout(350)
    popup.fill("#word", "b" * 201)
    popup.press("#word", "Enter")
    popup.wait_for_timeout(250)
    check("regression: popup rejects oversized keyword with feedback", popup.locator("#wordError").is_visible() and len(stored()["keywords"]) == 1)
    popup.close()

    # Native regex features must survive moving evaluation to a worker.
    for pattern in ["harm(less)", "(?<=harm)less", "harmless(?=$)"]:
        fresh(keywords=[rule(pattern, regex=True)])
        page.wait_for_function('() => !!document.querySelector(".hf-hide")', timeout=5000)
        check("regression: native regex syntax works in worker", state() == "hide", pattern)

    fresh(keywords=[rule("(a+)+$", regex=True), {"id": "healthy", "text": "survivor", "regex": True}])
    page.evaluate('''(html) => {
        window.lastTick = performance.now(); window.maxGap = 0;
        window.heartbeat = setInterval(() => {const now=performance.now(); maxGap=Math.max(maxGap, now-lastTick); lastTick=now;}, 20);
        document.querySelector("#timeline").insertAdjacentHTML("beforeend", html);
    }''', article(2, "slow", "Slow", "a" * 30 + "!"))
    page.wait_for_timeout(700)
    page.evaluate('(html) => document.querySelector("#timeline").insertAdjacentHTML("beforeend", html)', article(3, "healthy", "Healthy", "survivor"))
    page.wait_for_function("""() => document.querySelector("article[data-id='3']").closest('.hf-hide')""", timeout=5000)
    gap = page.evaluate('() => { clearInterval(heartbeat); return maxGap; }')
    check("regression: slow regex cannot block page heartbeat", gap < 500, f"max gap {gap:.1f} ms")
    check("regression: healthy regex continues after timeout", page.locator('article[data-id="3"]').evaluate('(a) => !!a.closest(".hf-hide")'))
    check("regression: slow regex warning is available to popup", bool(count()["regexWarning"]))

    # Disabling filtering while the worker is busy must invalidate its eventual response.
    fresh(keywords=[rule("(a+)+$", regex=True)])
    page.evaluate('(html) => document.querySelector("#timeline").insertAdjacentHTML("beforeend", html)', article(4, "slow", "Slow", "a" * 30 + "!"))
    page.wait_for_timeout(180)
    settings(enabled=False, keywords=[rule("(a+)+$", regex=True)])
    page.wait_for_timeout(300)
    check("regression: disabling during regex evaluation restores all posts", page.locator(".hf-hide").count() == 0 and count()["count"] == 0)

    settings(keywords=[rule("harmless", regex=True)])
    restricted = ctx.new_page()
    restricted.route("https://x.com/**", lambda route: route.fulfill(
        content_type="text/html", headers={"Content-Security-Policy": "frame-src 'none'; worker-src 'none'"},
        body=page_html([(5, "alice", "Alice", "harmless", False)])))
    restricted.goto("https://x.com/home")
    restricted.wait_for_function('() => !!document.querySelector(".hf-hide")', timeout=6000)
    check("regression: extension regex worker operates with restrictive page CSP", restricted.locator(".hf-hide").count() == 1)
    restricted.close()

    # Reset while tabs are open, then reject an old in-flight counter update.
    old_epoch = admin.evaluate('async () => ((await chrome.storage.local.get("stats")).stats || {}).epoch || 0')
    admin.click('nav a[href="#backup"]')
    admin.once("dialog", lambda dialog: dialog.accept())
    admin.click("#resetBtn")
    admin.wait_for_timeout(500)
    stats = admin.evaluate('async () => (await chrome.storage.local.get("stats")).stats')
    check("regression: reset clears statistics and rules with live tab", stats["total"] == 0 and stored()["keywords"] == [])
    session = ctx.new_cdp_session(page)
    contexts = []
    session.on("Runtime.executionContextCreated", lambda event: contexts.append(event["context"]))
    session.send("Runtime.enable")
    isolated = next(c for c in contexts if c.get("name") == ext_id or c.get("origin", "").startswith(f"chrome-extension://{ext_id}"))
    session.send("Runtime.evaluate", {"contextId": isolated["id"], "expression": f'chrome.runtime.sendMessage({{type:"hf:stats",count:9,epoch:{old_epoch}}})', "awaitPromise": True})
    check("regression: stale increment after reset is ignored", admin.evaluate('async () => (await chrome.storage.local.get("stats")).stats.total') == 0)
    session.send("Runtime.evaluate", {"contextId": isolated["id"], "expression": f'Promise.all(Array.from({{length:20}}, () => chrome.runtime.sendMessage({{type:"hf:stats",count:1,epoch:{stats["epoch"]}}})))', "awaitPromise": True})
    check("regression: concurrent increments are serialized", admin.evaluate('async () => (await chrome.storage.local.get("stats")).stats.total') == 20)
    session.detach()
    page.close()
