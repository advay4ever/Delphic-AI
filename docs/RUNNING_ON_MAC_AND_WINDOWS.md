# Running Delphic AI On Mac And Windows

This page explains what changed.

It uses very simple words.

For the shortest steps, read [`START_HERE.md`](../START_HERE.md).

## What Changed

Before, people had to type many commands.

Now there are start files.

Mac users click:

```text
run_mac.command
```

Windows users click:

```text
run_windows.bat
```

Both files use:

```text
run_app.py
```

`run_app.py` is the helper.

It gets the app ready.

## What The Helper Does

The helper does this:

1. Checks Python.
2. Makes a safe app folder called `.venv`.
3. Installs the app tools.
4. Lets the user choose an AI provider.
5. Starts Delphic AI.
6. Opens the browser.

The app opens here:

```text
http://127.0.0.1:5001
```

Then a popup asks for:

- AI provider
- API key

## What `.venv` Means

`.venv` is the app's own toolbox.

It keeps the app's tools in one place.

## What The AI Key Means

The AI key lets Delphic AI talk to the provider.

The user can choose:

- Groq
- OpenAI
- Anthropic
- Google Gemini
- Mistral
- Together AI
- xAI
- DeepSeek

Then the user pastes the key in the popup.

The key is not sent back to the browser after it is saved.

## Which AI Models Does It Use?

Each provider has one model picked for it.

The picked models are meant to be a good mix:

- Smart enough for math
- Smart enough for science
- Cheaper than the biggest models

So the app does not automatically choose the most expensive model.

## Is This Easy For Everyone?

It is much easier than before.

But some people may still need help with:

- Installing Python
- Choosing an AI provider
- Pasting the AI key

The easiest version is putting Delphic AI online.

Then people only need one website link.
