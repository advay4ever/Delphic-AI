# Streaming LaTeX Render (Clean Streaming)

## Goal
During word-by-word streaming, users currently see raw LaTeX delimiters (e.g. `$$x^2 + 1$$`) appearing character by character. The fix is to make math render cleanly — no raw `$$` ever visible.

## Approach
- While streaming, **buffer any text inside a LaTeX block** (don't show it while incomplete)
- The moment the **closing delimiter** (`$$` or `\)`) arrives, **instantly render that chunk with KaTeX** and append it to the bubble
- Non-math text continues to drip word-by-word as normal

## Result
User sees: normal words streaming → rendered formula pops in cleanly → more words stream → etc.

## Files to Change
- `static/script.js` — modify the word-drip queue logic to detect LaTeX delimiters and buffer accordingly

## Status
⬜ Not started
