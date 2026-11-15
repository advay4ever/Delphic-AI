# Start Delphic AI On Mac Or Windows

This download runs on the laptop, not on a hosted website. It contains the app's
required source code, not Python or installed libraries. Keep the extracted
folder together; the launcher cannot work by itself.

## Before Starting

1. Install Python from [python.org](https://www.python.org/downloads/).
   The launcher requires Python 3.10 or newer. Python 3.13 is the initial local
   test version; other versions and operating systems need the release checks.
2. On Windows, include the Python launcher or add Python to PATH during installation.
3. Download the curated `Delphic-AI-vVERSION-Python.zip` release asset. Replace
   VERSION with the actual release number. Do not choose an older installer or
   GitHub's automatic whole-project source ZIP.
4. Extract the whole ZIP into a writable folder, such as Documents. Do not run
   files from inside the ZIP. The first start needs internet and extra disk space
   to download the libraries; Python and library sizes vary by platform.
5. A school-managed laptop may block Python, Terminal, scripts, downloads, or AI
   connections. Follow its device rules; these steps do not remove restrictions.

## Start On Mac

1. Open the extracted `Delphic AI` folder in Finder.
2. Open Terminal from Applications > Utilities.
3. Type `zsh` followed by one space. Do not press Return yet.
4. Drag `run_mac.command` from Finder into Terminal.
5. Press Return. Keep Terminal open while using the app.

If a previous double-click showed an Apple warning, click Cancel and use the
Terminal steps. Do not disable system-wide security protections. Downloaded
scripts may still trigger warnings; these instructions are not a safety guarantee.

## Start On Windows

1. Open the extracted `Delphic AI` folder.
2. Double-click `run_windows.bat`.
3. Keep the command window open while using the app.

If Python is missing or cannot run, the launcher shows instructions instead of
starting the app. Install Python and reopen the launcher. Follow school/device
policy if Windows blocks an unrecognized downloaded script; do not turn off
system-wide protections.

## First Startup And AI Setup

The launcher creates `.venv` inside the extracted folder and installs the required
libraries there, without installing them into system Python. First startup may
take several minutes. Later starts check and reuse the environment.

After the local server is ready, the browser opens `http://127.0.0.1:5001` by
default. An explicit `PORT` setting changes the address printed in the command
window. Do not share the local address as an internet website.

Open a tutor and choose **Connect AI** or **Settings**. Choose a supported
provider and model, then paste a key privately. Saving settings is not a live
validation of the key. Provider access and charges are separate from this download.
Internet is needed for AI answers. Local supported graphs and diagrams do not
require paid requests. Experimental image generation remains opt-in and requires
its separately configured OpenRouter connection; it is not turned on by this ZIP.

Keys entered in Settings are temporary and can expire during use. They are not
kept after the local server stops. OS-vault remembering is not available in this
source launcher. Separately configured environment keys are different and are
not removed by forgetting a temporary connection. Never share keys in chat,
screenshots, or the download folder.

## Saved Work And Downloads

Default private data locations:

- Mac: `~/Library/Application Support/Delphic AI`
- Windows: `%APPDATA%\Delphic AI`

An explicit `DELPHIC_DATA_DIR` setting overrides these locations. The local `.env`
is a settings file, not an encrypted key vault. Browser cookies also identify
saved work. Keep using the same normal browser profile and local address.
Clearing cookies, private browsing, or changing profiles can make earlier chats
and notes inaccessible even when the database is still on disk.

Chat transcript downloads go wherever the browser saves downloads, usually the
Downloads folder. Open the browser's Downloads list to locate the saved file.

## Stop Or Update

To stop, click Terminal/the command window and press Control+C. On Mac, press
Return when asked to close. On Windows, follow the command-window prompt.
Closing only the browser does not stop the app.

For an update, stop the app and extract the new ZIP into a new folder. Keep the
private data folder and the same browser profile/address. Do not copy an old
`.venv` into the new folder. Back up private data before a version upgrade; an
older project-root database or image folder is not automatically moved by copying
settings. Release-specific migration testing is required.

## If Something Goes Wrong

- Read the error in the command window. Do not post any keys with an error report.
- If installation fails, check internet access and writable disk space, then retry.
- If `.venv` is broken, stop the app and rename only the `.venv` folder to
  `.venv-backup` inside the extracted download. Reopen the launcher to rebuild it.
  Do not delete the separate private data folder.
- If the port is busy, stop another Delphic instance or the program using that
  port. The launcher must not open an unrelated service as if it were Delphic.
- If the browser cannot open, use the local address printed after successful
  startup. A startup timeout or server failure must be resolved first.

This candidate still needs a separate Mac and Windows clean-machine check.
The release description must state the exact versions actually verified.
