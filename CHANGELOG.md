# Changelog

## 1.0.3
- Support X search and feed posts that use data-href links and language-tagged text instead of legacy tweet test IDs, including account blocking and multiple posts in one list item.
- Add Feedback & support in settings, with email drafts for problem reports and improvement suggestions.
- Include the extension version in drafts and show the support address for manual contact.

## 1.0.2
- Validate imported backups before replacing settings, preserving existing rules on invalid input.
- Run regular expressions in an isolated worker with a time limit and a popup warning for skipped slow rules.
- Recheck text nodes, emoji and post identity changes, and reset Show when a different post reuses an element.
- Preserve block boundaries when matching post text and author, including adjacent React elements and hidden posts.
- Report account, exception and keyword limits before saving, and reject oversized input without truncation.
- Rebuild the current-page counter on navigation and content changes, and reset statistics together with settings.
- Serialize statistics updates across tabs and ignore increments from before a reset.
- Detect promoted labels outside post text, author names and linked content.
- Expand regression coverage and return a failing test exit code when a check fails.

## 1.0.1
- Fixed: keywords that are emoji now match posts where X renders the emoji as an image.
- Fixed: a post whose text changed to a different text of the same length was not re-checked.
- Fixed: the toolbar counter now resets when filtering is turned off or the rules change.
- Fixed: the lifetime counter no longer counts the same post again after a settings change.

## 1.0.0
- First public release: keyword, phrase and account rules, exceptions, hide / collapse / blur modes, per-page scope, badge counter, import / export.
