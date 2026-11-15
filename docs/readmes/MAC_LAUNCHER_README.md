# Delphic AI Mac Source Launcher

The project root includes the Delphic AI source code and a Finder-friendly
launcher. This guide lives under `docs/readmes/`; run the launcher from the
project/download root, not from this documentation folder.

## What You Need

- A Mac with Python 3.10 or newer installed.
- Internet for initial package setup and whenever requesting an AI answer.

If you need Python, download it from [python.org](https://www.python.org/downloads/).

## Start Delphic AI

1. Keep this entire folder together. Do not move `run_mac.command` by itself.
2. Double-click `run_mac.command`.
3. If macOS asks for confirmation, choose **Open**.
4. Terminal will install the required packages the first time. This can take a few minutes.
5. When your browser opens, use Delphic AI at `http://127.0.0.1:5001`.

Keep the Terminal window open while using Delphic AI. Closing it stops the app.

## If Double-Click Is Blocked

1. Open **Terminal** from the Applications folder.
2. Type `zsh` followed by one space. Do not press Return yet.
3. Drag `run_mac.command` from Finder into the Terminal window.
4. Press **Return**.

This runs the same launcher through the Mac's installed Terminal.

## Add Your AI Key

Open a tutor, choose **Connect AI** or **Settings**, select a provider and model,
and paste the key there. Browsing alone does not force the popup open. Click
**Connect** or **Save changes**; saving is not a live key validation.
Do not paste your key into Terminal, chat, or screenshots.

Local configuration and chat history are stored privately in:

```text
~/Library/Application Support/Delphic AI
```

An API key pasted into **AI Settings** stays in memory only while Delphic AI is
running with this source launcher. Rebuilt native desktop apps additionally offer
an optional **Remember key on this device** checkbox using Mac Keychain. Do not
enable it on shared computers. The app and AI provider still need access to the
key; protected storage is not protection against malware or someone using your
unlocked account. Older desktop downloads need rebuilding for this option.

## Stop Delphic AI

Click the Terminal window, press `Control + C`, then press any key if Terminal asks you to close it.

## If It Does Not Start

- Install Python 3.10 or newer, then open `run_mac.command` again.
- Make sure the whole folder was extracted from the ZIP before opening the launcher.
- If the browser does not open automatically, visit `http://127.0.0.1:5001`.
- If double-click is blocked, use the Terminal steps above.
