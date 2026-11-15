# Delphic AI v0.1.9 - Python Download Test

This is a **prerelease for testing**, not a finished school or public deployment.
It runs locally on your computer in a browser. Python is installed separately.

## Which File To Download

Under **Assets**, choose **Delphic-AI-v0.1.9-Python.zip**.
Do not choose GitHub's automatic **Source code (zip)** or **Source code (tar.gz)**.
Those are repository snapshots, not the prepared app download.

The matching `.zip.sha256` file is available to check the download's integrity.
The ZIP includes startup instructions in `README.md`.

## Start On Another Mac

1. Install Python if needed. Python 3.13 was used for local verification;
   the launcher requires at least Python 3.10, but other versions are not yet
   certified by clean-machine tests.
2. Download the app ZIP and double-click it to extract the complete folder.
3. Move the extracted **Delphic AI** folder to Documents. Keep its files together.
4. Open Terminal from Applications > Utilities.
5. Type `zsh` followed by one space, drag `run_mac.command` into Terminal,
   and press Return.
6. Keep Terminal open. First startup needs internet and can take several minutes
   to create `.venv` and install the app's Python libraries.
7. After successful startup, the browser opens `http://127.0.0.1:5001` by default.
   In a tutor, open **Connect AI** or **Settings** and privately enter your own
   provider key and select an available model. Provider access and costs are separate.

Do not disable Mac security protections or school device restrictions. If startup
is blocked or fails, record the message without including an API key.

To stop the app, press Control+C in Terminal. Closing the browser alone does not
stop it. Temporary keys entered in Settings must be entered again after stopping
the local server. This source download does not enable OS-vault key remembering.

## What This Download Contains

- Math and Science tutor workspaces, guided tutoring, and practice prompts.
- Local supported 2D and 3D graphing.
- Study Library notes with separate note surfaces and direct previews.
- Safeguards against replacing an unfinished note while uploading a document,
  plus a browser warning before leaving with an unfinished draft.
- Chat and saved-image ownership protections, safer math parsing, work-checking
  limits, streaming fixes, and more reliable chat navigation and exports.
- Mac and Windows startup scripts that check Python, isolated dependencies,
  local server readiness, and port conflicts.

The prepared ZIP excludes personal keys, saved chats, databases, notes, generated
images, the development virtual environment, and Git history. It contains a
placeholder-only `.env.example`, not the developer's `.env`.

## What To Test

1. Open both tutor workspaces and connect your AI provider.
2. Ask `Solve 2x + 3 = 11`, then try a follow-up and guided tutoring.
3. Ask `Graph y = x^2 - 4` and `Graph z = x^2 + y^2`.
4. Add a Study Library note, preview it, and ask a related question.
5. Start a new note, then upload a document. Confirm that **Keep my note**
   preserves the unfinished text instead of replacing it.
6. Download a chat transcript and open the downloaded file.
7. Stop and restart the app. Use the same browser profile and local address,
   and check that saved chats, notes, and graph messages remain accessible.

Private browsing, clearing cookies, or changing browser profiles can remove
access to saved work. This test is not a promise of recovery after cookie loss.
Record the Mac model, macOS version, Python version, browser, and any failures.

## Known Limits

- Separate clean-Mac and native Windows checks are still pending. Including a
  Windows script is not proof that the download has passed Windows testing.
- Provider/model availability and real AI answer quality need live testing;
  automated checks use fake keys and mocked AI replies.
- Experimental image generation is disabled by default and is not part of this
  download's main acceptance test. No developer API key is included.
- Older downloads do not update automatically. Stop an older instance before
  starting this one; a busy port must not be mistaken for successful startup.
- This is not an app with Python bundled, a hosted website, a school account
  system, or a guarantee of correct answers.
