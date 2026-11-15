# Installable App Plan

Yes, Delphic AI can become an installable app that does not ask users to install Python.

The best way is to bundle Python inside Delphic AI.

That means users install Delphic AI, and Python comes hidden inside it.

They do not need to know what Python is.

## What We Added

These files are the first step:

- `desktop_launcher.py`
- `delphic_desktop.spec`
- `requirements-build.txt`

`desktop_launcher.py` starts Delphic AI like a desktop app.

`delphic_desktop.spec` tells PyInstaller which files to put inside the app.

`requirements-build.txt` installs the build tool.

## What Users Would See

On Mac, the goal is:

```text
Delphic AI.app
```

On Windows, the goal is:

```text
Delphic AI.exe
```

The user would open the app. The app would start the local server and open the browser.

The files added here prepare the app for that. They do not yet create a polished final installer like a signed Mac `.pkg` or Windows `.msi`.

Those final installer files should be made on each operating system after the PyInstaller build works.

## Why This Is Easier

With the current launcher, users need Python installed first.

With an installable app, Python is already inside the app.

So users do not install Python themselves.

## What Still Needs Work

The app still needs an AI API key.

The app can ask the user to choose a provider and paste a key in the browser.

The desktop launcher can also create a settings file here:

Mac:

```text
~/Library/Application Support/Delphic AI/.env
```

Windows:

```text
%APPDATA%\Delphic AI\.env
```

The in-app settings screen is easier than asking users to edit `.env`.

## How A Developer Builds It

Install build tools:

```bash
python -m pip install -r requirements-build.txt
```

Build the app:

```bash
pyinstaller delphic_desktop.spec
```

The built app appears in:

```text
dist/
```

After that, a developer can wrap the built app in a real installer:

- Mac: `.dmg` or `.pkg`
- Windows: `.exe` installer or `.msi`

## Important Mac And Windows Detail

You usually build the Mac app on a Mac.

You usually build the Windows app on Windows.

A Mac build does not automatically make a Windows `.exe`.

A Windows build does not automatically make a Mac `.app`.

## Best Final Version

For people with zero computer knowledge, the best final setup is:

1. They download Delphic AI.
2. They install it.
3. They open it.
4. They choose an AI provider.
5. They paste their API key into a settings screen.
6. The app opens and works.

Even easier than that is hosting Delphic AI online, because then users only need one website link.
