# Delphic AI Recording Checklist

## Product Gate

- [ ] All Python tests pass.
- [ ] All Playwright browser tests pass.
- [ ] The Math and Science pages open without browser console errors.
- [ ] A real provider completes one Math answer and one Science answer.
- [ ] Step-by-Step Mode waits for the student's response.
- [ ] One 2D graph and one 3D graph render and remain interactive.
- [ ] A practice problem and a work-checking response complete successfully.
- [ ] A supported science diagram renders with readable labels.
- [ ] The HTML transcript opens correctly after download.

## Privacy Gate

- [ ] Use a separate demo API key with a strict spending limit.
- [ ] Configure the key before recording.
- [ ] Keep the API key field, `.env`, terminal history, and developer tools hidden.
- [ ] Use only made-up chat examples.
- [ ] Hide usernames, notifications, bookmarks, email, and personal file paths.
- [ ] Confirm the downloaded transcript contains no secret key or private path.
- [ ] Remove failed takes that accidentally show private information.

## Screen Setup

- [ ] Use a 1440 by 900 browser window at 100 percent zoom.
- [ ] Turn on Do Not Disturb.
- [ ] Close unrelated apps and tabs.
- [ ] Use a clean Delphic chat list.
- [ ] Keep the mouse pointer still while answers stream.
- [ ] Check that text is readable without squinting.
- [ ] Record a short audio test before the full take.

## Recording Order

- [ ] State the student problem in one sentence.
- [ ] Show a Math answer and a follow-up question.
- [ ] Show interactive Step-by-Step Mode.
- [ ] Show a 2D graph and a rotatable 3D graph.
- [ ] Generate a practice problem and check a student's work.
- [ ] Show one reviewed Science diagram.
- [ ] Switch themes and download the HTML transcript.
- [ ] End with the product value, not a list of buttons.

## Quality Gate

- [ ] Keep the final video between 4 and 5 minutes.
- [ ] Remove long loading pauses while keeping the workflow honest.
- [ ] Add accurate captions.
- [ ] Make captions readable with the sound turned off.
- [ ] Do not speed up important results so much that they cannot be inspected.
- [ ] Use a title card with the product name and one-sentence value statement.
- [ ] Include a link to the project or contact page at the end.
- [ ] Watch the final export from beginning to end before publishing.

## Buyer Questions To Be Ready For

- How are API keys protected?
- Where are chats and generated images stored?
- Which parts work without an internet connection?
- How does Delphic check math work?
- Which science diagrams and graphs are supported?
- What does the current desktop installer require?
- What would be needed for school accounts, administration, billing, and public deployment?
