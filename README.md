# Hushfeed

Mute posts on X (Twitter) by keyword, phrase or account. Chrome extension, Manifest V3.

- Whole-word, case-sensitive and regular-expression rules
- Hide posts by account, with an exceptions list
- Hide, collapse or blur matching posts
- Choose where filtering applies (home, search, profiles, replies, lists)
- Badge counter, keyboard shortcut (Alt+Shift+H), JSON export / import
- Private: rules are stored locally, no network requests, no analytics

**Install:** Chrome Web Store link goes here after publication.

## Run it locally

1. Open `chrome://extensions` and turn on **Developer mode**.
2. Click **Load unpacked** and select the `extension/` folder.

## Repository layout

| Folder | Contents |
|---|---|
| `extension/` | The extension itself. This folder is what gets zipped and uploaded to the store. |
| `store/` | Store listing text, promo tile, screenshots, marquee |
| `docs/` | Privacy policy, published with GitHub Pages |
| `scripts/` | `build.sh` creates the store zip on macOS / Linux |
| `tests/` | End-to-end tests that run the extension in Chromium (Playwright) |
| `.github/workflows/` | Builds the release zip when a version tag is pushed |

## Release a new version

1. Edit the code in `extension/`.
2. Raise `version` in `extension/manifest.json` and add a line to `CHANGELOG.md`.
3. Commit, then create and push a tag that matches the version (for example `v1.0.1`).
4. GitHub builds `hushfeed-1.0.1.zip` and attaches it to a Release. Upload that file in the Chrome Web Store dashboard.

## Run the tests

```
pip install playwright
playwright install chromium
python tests/e2e.py
```

The tests load the extension in Chromium and run it against a mock of the X timeline. They cannot replace a manual check on x.com after X changes its page.

## Privacy

See [docs/index.md](docs/index.md). Hushfeed reads post text on x.com only to match your rules, entirely in your browser.

## Contact

zng.itc@gmail.com

## Disclaimer

Independent project, not affiliated with or endorsed by X Corp.

Copyright © 2026 ZNG. All rights reserved.
