from pathlib import Path


def run_new_x_markup(ctx, admin, check, errors):
    fixture = (Path(__file__).parent / "fixtures/x-search-post.html").read_text(encoding="utf-8")
    page = ctx.new_page()
    page.on("pageerror", lambda error: errors.append(("new-x-markup", str(error))))
    page.route("https://x.com/**", lambda route: route.fulfill(content_type="text/html", body="<!doctype html><html><body><ul>" + fixture + "</ul></body></html>"))

    def settings(**values):
        admin.evaluate("(s) => HF.save(s)", values)
        page.wait_for_timeout(400)

    def rule(text="ohnepixel", **extra):
        return {"id": "search-rule", "text": text, "on": True, **extra}

    def state():
        return page.locator('li > [data-href]').get_attribute("data-hf-state")

    page.goto("https://x.com/search?q=ohnepixel&src=recent_search_click")
    settings(keywords=[rule(regex=True, scope="all")])
    page.wait_for_function('() => !!document.querySelector(".hf-hide")')
    check("new X: reported regex and author rule hides supplied search result", state() == "hide")
    settings(keywords=[rule(regex=True)])
    check("new X: regex matches post text without tweetText attribute", state() == "hide")
    settings(keywords=[rule()])
    check("new X: ordinary keyword matches mixed capitalization", state() == "hide")
    settings(keywords=[rule(caseSensitive=True)])
    check("new X: case-sensitive keyword still respects capitalization", state() is None)
    settings(accounts=["ohnepixelupdate"])
    check("new X: account rule finds author from post link", state() == "hide")
    settings(keywords=[rule()], allow=["bought a supercar"])
    check("new X: exception text overrides matching keyword", state() is None)
    settings(keywords=[rule()], places={"search": False})
    check("new X: search filter preference is respected", state() is None)

    for mode in ["collapse", "blur"]:
        settings(keywords=[rule()], mode=mode)
        check(f"new X: {mode} mode applies to modern post container", state() == mode)
        page.evaluate('''() => {
            window.postNavigation = 0;
            document.querySelector('li > [data-href]').onclick = () => { window.postNavigation++; };
        }''')
        page.click(".hf-note button" if mode == "collapse" else "article")
        page.wait_for_timeout(300)
        check(f"new X: {mode} reveal stops parent navigation", state() == "revealed" and page.evaluate("postNavigation") == 0)
        page.evaluate('() => document.querySelector("li > [data-href]").setAttribute("data-href", "/ohnePixelUpdate/status/2124525812695327164")')
        page.wait_for_timeout(350)
        check(f"new X: recycled {mode} row is filtered by its new post ID", state() == mode)
        settings(keywords=[])
        page.evaluate('() => document.querySelector("li > [data-href]").setAttribute("data-href", "/ohnePixelUpdate/status/2124525812695327163")')

    settings(keywords=[rule()])
    page.evaluate('() => document.querySelector("[lang]").textContent="ordinary post"')
    page.wait_for_timeout(350)
    check("new X: text-only rule excludes author name", state() is None)
    settings(keywords=[rule(scope="all")])
    check("new X: author scope includes display name and handle", state() == "hide")

    settings(hidePromoted=True)
    page.evaluate('() => document.querySelector("[lang]").textContent="Ad"')
    page.wait_for_timeout(350)
    check("new X: Ad in post text remains visible", state() is None)
    page.evaluate('() => document.querySelector("article").appendChild(Object.assign(document.createElement("span"), {textContent:"Promoted"}))')
    page.wait_for_timeout(350)
    check("new X: ad label outside body is recognized inside link wrapper", state() == "hide")

    settings(keywords=[rule()])
    page.evaluate('''() => {
        document.querySelector('ul').insertAdjacentHTML('beforeend', '<li><article id="unrelated">ohnepixel</article></li>');
        document.querySelector('[lang]').textContent = 'ohnePixel';
    }''')
    page.wait_for_timeout(350)
    check("new X: unrelated articles are not treated as feed posts", page.locator("#unrelated").get_attribute("data-hf-state") is None and state() == "hide")

    fixture = (Path(__file__).parent / "fixtures/x-search-thread.html").read_text(encoding="utf-8")
    page.reload()
    for regex in [False, True]:
        settings(keywords=[rule(regex=regex)])
        check(f"new X: linked mention matches with regex={regex}", page.locator('[data-href^="/goodvibesCS2/"]').get_attribute("data-hf-state") == "hide")
        check(f"new X: sibling reply remains visible with regex={regex}", page.locator('[data-href^="/MitaoCatCS/"]').is_visible())
    settings(accounts=["ohnepixel"])
    check("new X: mentioning a blocked account does not make it the author", page.locator('[data-href^="/goodvibesCS2/"]').is_visible())

    fixture = (Path(__file__).parent / "fixtures/x-feed-account.html").read_text(encoding="utf-8")
    page.goto("https://x.com/home")
    settings(accounts=["ohnepixel"])
    check("new X: blocked author is hidden in home feed", state() == "hide")
    page.evaluate('() => document.querySelector("[lang]").textContent = "Unrelated post text"')
    page.wait_for_timeout(350)
    check("new X: account blocking does not depend on keywords in body", state() == "hide")
    settings(keywords=[rule("Ilya Batishchev"), rule(regex=True, scope="all")], accounts=["ohnepixel", "ilyabatishchev"])
    check("new X: settings from supplied screenshot hide blocked author", state() == "hide")
    settings(accounts=["ohnepixelupdate"])
    check("new X: account matching remains exact", state() is None)
    page.close()
