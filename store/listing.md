# Chrome Web Store listing: copy and paste

## Name (max 75 characters)
Hushfeed – Mute posts by keyword

## Summary (max 132 characters)
Hide posts on X (Twitter) by keyword, phrase or account. Regex, exceptions, blur mode. Private: nothing leaves your device.

## Category
Productivity (alternative: Social & Communication)

## Description
Hushfeed keeps the words, names and topics you're tired of out of your X (Twitter) feed.

Add a keyword, a phrase or an account, and matching posts disappear from your timeline. No account, no sign-up, no tracking.

WHAT YOU CAN DO
• Hide posts by keyword or phrase (case-insensitive by default)
• Match whole words only, case-sensitive, or with regular expressions
• Search the post text only, or the author's name and handle as well
• Hide every post from specific accounts
• Add exceptions: phrases that are always allowed through
• Choose what happens to a match: hide it, collapse it into a slim "Show" note, or blur it
• Choose where filtering applies: home, search, profiles, replies, lists
• Optionally hide promoted posts
• See how many posts were hidden on the current page, right on the toolbar icon
• Turn everything on or off with Alt+Shift+H
• Export and import your rules as a JSON file
• Light and dark mode

PRIVATE BY DESIGN
Your rules are stored locally in your browser. Hushfeed makes no network requests, collects no data and contains no analytics or ads.

Hushfeed is an independent project and is not affiliated with or endorsed by X Corp. "X" and "Twitter" are trademarks of their respective owners.

## Single purpose (required field)
Hide posts on x.com / twitter.com that match words, phrases or accounts the user has chosen.

## Permission justifications
- storage: Saves the user's rules and preferences locally in the browser (chrome.storage.local).
- Host access (x.com, twitter.com), declared via content script matches: The content script reads the text of posts shown on the page in order to compare it with the user's rules and hide matching posts. Page content is processed locally and never transmitted.

## Privacy practices tab
- Data collected: none. Leave every data-type box unchecked.
- Certify: not sold to third parties, not used for unrelated purposes, not used for creditworthiness or lending.
- Remote code: No. All code is bundled in the package.
- Privacy policy URL: use the GitHub Pages address of docs/index.md (https://YOUR-USERNAME.github.io/hushfeed/) and paste the link.

## Images to upload
- Store icon 128x128: icons/icon128.png (already in the package)
- Small promo tile 440x280: store/promo-tile-440x280.png
- Screenshots 1280x800: store/screenshots/screenshot-1 ... screenshot-5
- Marquee 1400x560 (optional): store/screenshots/marquee-1400x560.png
