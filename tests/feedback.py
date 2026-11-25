from pathlib import Path
from urllib.parse import parse_qs, urlparse


def run_feedback(ctx, admin, check, errors):
    page = ctx.new_page()
    page.on("pageerror", lambda error: errors.append(("feedback", str(error))))
    page.goto(admin.url)
    before = admin.evaluate("() => HF.load()")
    version = page.evaluate("() => chrome.runtime.getManifest().version")
    check("feedback: draft starts hidden", not page.locator("#feedbackDraft").is_visible())
    page.locator("#reportProblem").focus()
    page.keyboard.press("Enter")
    check("feedback: keyboard opens local problem draft", page.locator("#feedbackDraft").is_visible() and page.locator("#feedbackDraftTitle").inner_text() == "Problem report")
    check("feedback: draft heading receives focus", page.evaluate("document.activeElement.id") == "feedbackDraftTitle")
    draft = page.locator("#feedbackText").input_value()
    check("feedback: draft includes recipient and runtime version", "To: zng.itc@gmail.com" in draft and "Hushfeed version " + version in draft)
    gmail_url = page.locator("#feedbackGmail").get_attribute("href")
    gmail = parse_qs(urlparse(gmail_url).query)
    mailto = parse_qs(urlparse(page.locator("#feedbackMailto").get_attribute("href")).query)
    check("feedback: email and Gmail drafts agree", gmail["su"] == mailto["subject"] and gmail["body"] == mailto["body"] and gmail["to"] == ["zng.itc@gmail.com"])
    check("feedback: draft contains only version and prompts", gmail["body"][0] == f"Hushfeed version {version}\r\n\r\nWhat happened?\r\n\r\nWhat did you expect?\r\n\r\nSteps to reproduce\r\n\r\nYou can attach a screenshot if it helps.\r\n\r\n")
    # Intercept Gmail so no account is accessed and no message is sent.
    def gmail_route(route):
        route.fulfill(content_type="text/html", body="<title>Gmail test destination</title>")
    ctx.route("https://mail.google.com/**", gmail_route)
    with ctx.expect_page() as opened:
        page.click("#feedbackGmail")
    gmail_page = opened.value
    gmail_page.wait_for_load_state()
    check("feedback: Gmail opens in a separate tab", gmail_page.url == gmail_url and page.url == admin.url)
    check("feedback: Gmail cannot access opener", gmail_page.evaluate("window.opener === null"))
    gmail_page.close()
    ctx.unroute("https://mail.google.com/**", gmail_route)
    page.bring_to_front()

    # Keep clipboard tests isolated from the user's real system clipboard.
    page.evaluate("""() => {
        window.copiedFeedback = [];
        Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
            writeText: async text => { window.copiedFeedback.push(text); }
        }});
    }""")
    page.click("#copyFeedback")
    page.wait_for_function("document.querySelector('#feedbackStatus').textContent.startsWith('Draft copied')")
    check("feedback: copies complete draft", page.evaluate("copiedFeedback.at(-1)") == draft)
    page.click("#copySupportEmail")
    page.wait_for_function("document.querySelector('#feedbackStatus').textContent === 'Email address copied.'")
    check("feedback: copies support email", page.evaluate("copiedFeedback.at(-1)") == "zng.itc@gmail.com")

    page.click("#suggestImprovement")
    suggestion = page.locator("#feedbackText").input_value()
    check("feedback: switching topics replaces draft and clears status", "My suggestion" in suggestion and "What happened?" not in suggestion and page.locator("#feedbackStatus").inner_text() == "")
    check("feedback: topic expansion state updates", page.locator("#reportProblem").get_attribute("aria-expanded") == "false" and page.locator("#suggestImprovement").get_attribute("aria-expanded") == "true")
    check("feedback: Gmail subject changes with topic", parse_qs(urlparse(page.locator("#feedbackGmail").get_attribute("href")).query)["su"] == ["Hushfeed improvement suggestion"])

    page.evaluate("() => { navigator.clipboard.writeText = async () => { throw new DOMException('Denied', 'NotAllowedError'); }; }")
    page.click("#copyFeedback")
    page.wait_for_function("document.querySelector('#feedbackStatus').textContent.includes('draft is selected')")
    check("feedback: denied clipboard selects draft for manual copying", page.evaluate("() => { const t = document.querySelector('#feedbackText'); return document.activeElement === t && t.selectionStart === 0 && t.selectionEnd === t.value.length; }") )
    page.click("#copySupportEmail")
    page.wait_for_function("document.querySelector('#feedbackStatus').textContent.includes('email address is selected')")
    check("feedback: denied clipboard selects address for manual copying", page.evaluate("getSelection().toString()") == "zng.itc@gmail.com")
    page.evaluate("Object.defineProperty(navigator, 'clipboard', {configurable:true, value:undefined})")
    page.click("#copyFeedback")
    page.wait_for_function("document.querySelector('#feedbackStatus').textContent.includes('draft is selected')")
    check("feedback: absent clipboard API has a manual fallback", page.evaluate("document.activeElement.id") == "feedbackText")
    check("feedback: settings are unchanged", before == admin.evaluate("() => HF.load()"))

    output = Path(__file__).resolve().parents[1] / "dist/feedback-preview"
    output.mkdir(parents=True, exist_ok=True)
    page.click("#reportProblem")
    for width, theme in [(1100, "dark"), (390, "light")]:
        page.set_viewport_size({"width": width, "height": 1000})
        page.emulate_media(color_scheme=theme)
        check(f"feedback: no horizontal overflow at {width}px", page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        page.locator("#feedback").screenshot(path=str(output / f"feedback-{width}-{theme}.png"))
    page.close()
