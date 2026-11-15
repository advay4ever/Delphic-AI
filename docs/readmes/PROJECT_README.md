# Delphic AI

**Checked against source:** October 30, 2026. This describes the current source,
not a guarantee about an older downloaded installer or a live AI provider.

Delphic AI is a web-based learning assistant with separate Math and Science tutor workspaces. Both tutors run in the same Flask application, using port `5001` by default, while keeping their prompts, tools, and conversation histories separate.

The app can use several AI providers from Settings. Supported Math operations can
be checked with SymPy and graphed locally with Three.js. Both tutors support
streamed responses, formatted equations, saved chats, transcript downloads,
guided learning, uploads, and a personal Study Library. AI image generation is a
separate experimental, disabled-by-default feature with unresolved student-release gates.

For the simplest local setup, start with [START_HERE.md](../../START_HERE.md).

## Current Status

| Area | Current implementation |
|------|------------------------|
| Home | Shared entry page for the Math and Science tutors |
| Math tutor | Explanations, guided steps, work checking, practice, and graphing |
| Science tutor | Concept help, guided reasoning, practice, quizzes, and safe local diagrams |
| AI provider | User-selected provider: Groq, OpenAI, Anthropic, Google Gemini, Mistral, Together AI, xAI, DeepSeek, or OpenRouter |
| Storage | Local SQLite conversation and session history |
| Study Library | Selected reusable Math/Science notes with bounded TF-IDF/cosine retrieval |
| API keys | Temporary backend memory by default; optional native desktop OS-vault storage |
| Frontend | Flask templates, HTML, CSS, and JavaScript |
| Math rendering | KaTeX |
| Math verification | SymPy for supported answers and student step transitions |
| Graphing | Local Three.js 2D and 3D graphs in the Math tutor |
| Experimental images | Private-development OpenRouter generation, accuracy review, local storage, chat restoration, and HTML/ZIP export; disabled by default |
| Automated tests | Local pytest suite and Playwright browser checks |

## Workspaces

### Home

The home page provides entry points to both tutors. Each tutor sidebar also contains the same three navigation choices:

- Home
- Math tutor
- Science tutor

The current tutor is visually identified in the Workspace section.

### Math Tutor

The Math tutor currently supports:

- Step-by-step explanations
- Interactive Step-by-Step Mode with one next question at a time
- Follow-up questions such as `Why?` and requests for simpler language
- Work checking that uses SymPy to identify the first incorrect supported step
- Similar practice-problem generation
- SymPy-backed verification for supported operations
- Local interactive 2D graphs for functions, points, conics, polar curves, parametric curves, piecewise rules, inequalities, and vector fields
- Local interactive 3D graphs for explicit and implicit surfaces, parametric curves, and multi-surface systems
- Graphing without a Desmos key or graphing internet request
- Multi-turn graph requests using the last plotted equation
- Algebra, geometry, trigonometry, calculus, statistics, and word problems

The empty Math chat offers **Solve an equation**, **Explain a concept**, and
**Give me practice**, centered below the first two buttons. Those are example
prompts, not separate engines. There is no **Check my work** starter button;
type that request with your own steps, or attach your work and ask for a review.
Uploaded work is interpreted by the AI; local step verification does not inspect
handwriting or document contents automatically.

### Science Tutor

The Science tutor currently supports:

- Biology, chemistry, physics, Earth science, and environmental science
- Concept explanations and vocabulary help
- Formula explanations with KaTeX formatting
- Reasoning checks that identify incorrect ideas
- Guided Reasoning Mode with one idea and one question at a time
- Practice questions connected to the current topic
- A five-question Quiz Mode that asks one question at a time
- Quiz grading with explanations for incorrect or partly correct answers
- Redirection of Math-only graphing requests to the Math tutor
- Separate Science sessions and conversation history
- Reviewed local diagrams for forces, simple circuits, the water cycle, and plant cells
- Diagrams that return after refresh and appear in downloaded HTML transcripts
- A written fallback for diagram topics that are not supported yet

## Shared Features

Both tutor workspaces include:

- Streamed AI responses
- A 4,096-token tutor output budget (or a smaller configured provider cap),
  completion-status metadata, and one continuation for an eligible truncated answer
- Recent conversation context for follow-up questions
- New Chat, session switching, and per-chat Download/Delete actions
- Separate Math and Science session lists
- Copy controls on tutor responses
- Browser-openable `.html` transcript downloads
- Older chat messages available through **Load earlier messages**; full paged
  transcript retrieval remains separate from the AI's bounded context
- A download notice showing the filename; the browser controls the save location
- Light, dark, and neon themes, with eight saved Neon accent choices
- Confidence badges on AI answers
- Responsive layouts, with current design work focused on computers and iPads;
  simulated viewports are not a substitute for real-device testing
- English responses by default
- Input-length validation and learning-focused safety redirection
- Safe local science diagrams that do not require a paid image or graph API
- An optional private-development Create image mode with educational, realistic, and creative choices

Choose **Settings > Appearance > Theme > Neon** to reveal the Neon accent
swatches: Cyan, Electric blue, Mint, Green, Yellow, Orange, Pink, and Purple.
The accent is saved in this browser and shared by Math, Science, and Home.
Neon uses a color-tinted workspace, sidebar, composer, and tools, with bright
filled primary buttons and stronger glow. Light/Dark styling and error colors
remain unchanged. Some accent text uses a lighter shade for readability;
the swatches and filled primary buttons use the chosen color.

## Example Prompts

### Math

| Prompt | Result |
|--------|--------|
| `Solve 2x + 3 = 11` | Step-by-step algebra explanation |
| `Why did you subtract 3?` | Follow-up reasoning using recent context |
| `Explain that in 5th grade language` | Simpler wording and smaller steps |
| `Check my work:` followed by one equation per line | Verified first-mistake feedback for supported algebra or derivatives |
| `Give me a similar practice problem` | One related problem without its answer |
| `Find the derivative of x^3 + 2x` | Calculus explanation with SymPy guidance |
| `Plot sin(x)` | Explanation plus an interactive graph |
| `Plot (3, 0)` | Interactive coordinate point |
| `Graph z = x^2 + y^2` | Rotatable interactive 3D surface |
| `Graph x^2 / 9 + y^2 / 4 = 1` | Interactive ellipse (implicit conic) |
| `Graph r = 2sin(3theta)` | Interactive polar curve |
| `Graph x = cos(t), y = sin(t)` | Interactive parametric curve |
| `Graph y = x^2 for x >= 0; y = -x for x < 0` | Interactive piecewise function |
| `Graph x^2 + y^2 <= 25` | Shaded inequality region |
| `Graph vector field <y, -x>` | Interactive 2D vector field |
| `Graph x^2 + y^2 + z^2 = 16` | Rotatable implicit 3D sphere |
| `Graph x = cos(t), y = sin(t), z = t / 2` | Rotatable 3D parametric curve |
| `z^2 = x^2 + y^2` then `z = x + 2` on the next line | 3D system with its intersection highlighted |

### Science

| Prompt | Result |
|--------|--------|
| `Explain photosynthesis in simple words` | Student-friendly concept explanation |
| `What does erosion mean in Earth science?` | Vocabulary explanation with context |
| `What does F = ma mean in real life?` | Formula connected to an example |
| `Check my reasoning: a chemical reaction creates new atoms` | Reasoning check and correction |
| `Give me a practice question about ecosystems` | One Science practice question |
| `Draw a plant cell diagram` | Reviewed local diagram plus a written explanation |
| Select `Quiz Mode` | Interactive five-question Science quiz |

## Product Demo

The buyer-facing demo package includes a timed walkthrough, a privacy and quality
checklist and reusable portfolio copy:

- [Buyer demo script](../demo/DEMO_SCRIPT.md)
- [Recording checklist](../demo/RECORDING_CHECKLIST.md)
- [Portfolio and buyer copy](../demo/PORTFOLIO_COPY.md)

The script covers follow-up tutoring, guided learning, local 2D and 3D graphing,
practice, work checking, a reviewed Science diagram, themes, and HTML download.
Experimental images are excluded from the main buyer demo. Recording and
publishing a final video remain separate tasks; the documents are not a finished video.

## How It Works

```text
Browser
  |
  |-- Home, Math tutor, or Science tutor
  |-- Shared JavaScript chat interface
  v
Flask application
  |
  |-- Math and Science routes
  |-- Separate session IDs and histories
  |-- Prompt and mode instructions
  |-- SQLite persistence
  |
  +-- Selected AI provider
  |
  +-- SymPy math verification
  |
  +-- Safe local graph data for Math requests
  |     `-- Three.js renders 2D and 3D graphs in the browser
  |
  +-- Validated diagram data for supported Science requests
        `-- Local controlled SVG renders the reviewed diagram
```

The main browser request uses Server-Sent Events so the tutor response can appear while it is being generated. The completed response is saved to SQLite and restored when the user returns to that session.

The older corpus feature was removed on October 3, 2026. A new personal Study
Library is now available; old note folders and built-in files are not imported
or read automatically.

## Personal Study Library

Open **Study Library** in either tutor's sidebar, or choose **Save study notes**
from the chat input's plus menu. With no enabled notes for this tutor, the
composer's **Add study notes** shortcut opens the new-note form directly. Upload TXT, MD, CSV, JSON,
text-based PDF, or DOCX, review the extracted text, choose a subject, and save.
Study Library has one saved-note list and a header **+ Add note** button, not
separate My Notes/Add Notes tabs. The plus opens **New note** for uploading,
dragging and dropping, or pasting. Back returns to the list while keeping the
new-note draft. Saved notes have a **Use this note** switch and a three-dot menu for preview,
rename, edit, and delete. **Edit note** changes saved title, subject, and text;
failed saves keep the draft, and older tabs cannot silently overwrite newer
changes. The list supports local title/text search, exact-subject filters,
Recently updated/Title A-Z sorting, and Clear filters. On/Off text shows saved
selection; filters never change which notes the tutor may use. Duplicate text
shows an advisory but can still be saved as a separate copy. Earlier answer
excerpts remain unchanged. Editing, finding notes, and the new shortcuts
are in source; older downloaded installers need rebuilding. The count beside the composer shows notes enabled for the
current tutor, not how many were used in an answer. Subject suggestions require
your approval; they do not automatically change the note's subject.
Limits: 50 notes per browser library, 60 to 12,000 characters per note, one uploaded
document up to 4 MiB. Photos remain part of chat attachments, not saved notes.
Adding, previewing, and saving notes does not require an API key. Upload files
in the plus menu attaches a document to one question; Save study notes opens
the reusable library and still requires a preview review and explicit save.

When you ask a question, Delphic searches your enabled notes for that tutor using
TF-IDF and cosine similarity across titles and text, with limited word-form and
simple equation search hints. Follow-ups can use bounded same-chat context.
The tutor is instructed to prefer a suitable, correct method from the matching
notes, simplify that method when needed, and allow another approach on request.
This is model guidance, not guaranteed factual checking or semantic search.
At most three short matching excerpts enter the
provider request. Expand **Matching notes** under an answer to inspect
the retrieved material; references also survive refresh and appear in HTML exports.
These are retrieved candidates, not proof that the AI used them or that they are
true. Paragraph-aware excerpts carry bounded opening context when possible;
`[...]` marks omitted text, so an excerpt may still be incomplete. No match
means normal tutoring without invented library references. See the
[notes-first live checks](../testing/STUDY_LIBRARY_TEST_GUIDE.md#check-notes-first-teaching)
before treating real-model teaching behavior as verified.

Only save material you own or may use. Notes are local SQLite text associated
with a server-generated browser cookie, not accounts or cross-device storage.
Losing that cookie can make notes inaccessible. Topic checks are limited
heuristics, not fact checking or complete multilingual classification.
Retrieved notes are unverified reference data, not instructions or guaranteed
facts. The tutor is instructed to explain discovered mistakes, prefer actual
app-supplied math checks, and admit uncertainty instead of blindly agreeing.
This is model guidance, not a guarantee of accuracy or an automatic review of
every saved note. Original notes are not silently corrected.
Deleting/disabling a note stops future searches, but earlier chat excerpts
remain until the chat is deleted; continuing that same answer reuses its saved
reference snapshot. No original upload is retained.

See the [Study Library implementation plan](../implementation/STUDY_LIBRARY_IMPLEMENTATION_PLAN.md).

## Chat Photos And Files

The **+** inside the input pill offers **Add photos** and **Upload files** in
both tutors. Select up to three files, preview/remove them, and send a question.
Photos can also be pasted into the input. An attachment-only message asks the
tutor to explain the material.

Supported: JPG/JPEG, PNG, WebP, TXT, Markdown, CSV, JSON, text-based PDF, and
DOCX. Each file can be up to 4 MiB. Documents have text and page limits; scanned
PDFs need a separate photo, and encrypted PDFs are rejected. HEIC, SVG, video,
audio, old DOC files, and arbitrary archives are not supported.

Photos require a vision-capable model using the OpenAI, Anthropic, Gemini, or
OpenRouter image-input protocol. Other current provider profiles can use text
documents, not photos. Selecting a provider alone does not guarantee every
model supports images; Delphic does not silently change your model or key.

Processed document text and sanitized photos are saved in the local chat
database and reused for bounded follow-up context. Deleting the chat deletes
that context. The selected provider receives context used by the conversation;
avoid uploading private student information. Original files are not retained as
downloadable uploads. Browser storage does not store the selected files.
Transcript exports list attachment names, not original files or extracted text.

This is chat context, **not corpus search or model training**. Live provider
acceptance and interpretation accuracy require separate tests.
See the [attachment implementation plan](../implementation/CHAT_ATTACHMENTS_IMPLEMENTATION_PLAN.md).

## Main Routes

| Route | Purpose |
|-------|---------|
| `/` | Home page and Math tutor |
| `/science` | Science tutor |
| `GET /ai-settings` | Report non-secret connection and desktop-storage status |
| `POST /ai-settings` | Validate and save provider/model/key choices |
| `DELETE /ai-settings` | Forget the current temporary key and any enabled desktop saved copy; not `.env` keys |
| `/stream` | Stream a Math response |
| `/science/stream` | Stream a Science response |
| `/plot` | Produce Math graph data |
| `/local-graph-message` | Save a local graph request when no AI provider is configured |
| `/history` | Load the current Math conversation |
| `/science/history` | Load the current Science conversation |
| `/sessions` | List Math sessions |
| `/science/sessions` | List Science sessions |
| `/clear` | Clear the current Math conversation |
| `/science/clear` | Clear the current Science conversation |
| `/responses/continue`, `/science/responses/continue` | Continue an eligible truncated answer once |
| `/library/notes`, `/library/notes/<note_id>` | List, create, edit, or delete owned reusable notes |
| `/library/preview`, `/library/status` | Preview a note upload and report enabled-note counts |
| `GET /images` | List safe metadata for the current browser owner's images in the active Math or Science chat |
| `GET /images/<image_id>` | Privately display or download one owned generated image |
| `DELETE /images/<image_id>` | Delete one owned generated image and its local file |
| `POST /images/generate` | Create, review, sanitize, and privately save one experimental generated image |

## Project Structure

```text
project-root/
|-- START_HERE.md                  Easiest setup instructions
|-- app.py                         Flask routes and tutor request flow
|-- database.py                    SQLite sessions, messages, and statistics
|-- ai/
|   |-- prompt.py                  Math and Science system prompts
|   |-- service.py                 AI provider integration and response streaming
|   |-- detector.py                Math and graph request detection
|   |-- graphing.py                Safe local 2D and 3D graph-data generator
|   |-- work_checker.py            Local first-mistake verification for student steps
|   |-- safe_math.py               Allowlisted math parser and resource bounds
|   |-- attachments.py             Bounded file processing and provider context
|   |-- study_library.py           Note validation, retrieval, and references
|   |-- device_credentials.py      Optional native desktop credential storage
|   `-- math_tools.py              SymPy operations
|-- images/                        Provider-neutral image generation foundation
|-- science/                       Reviewed local diagram templates and validation
|-- templates/
|   |-- index.html                 Home page and Math tutor
|   `-- science.html               Science tutor
|-- static/
|   |-- script.js                  Shared browser behavior
|   |-- graphing.js                Three.js 2D and 3D graph renderer
|   |-- style.css                  Themes and responsive styling
|   |-- vendor/three/              Local Three.js 0.180.0 files and license
|   `-- assets/                    Delphic logo files
|-- tests/
|   |-- test_follow_up_detection.py
|   |-- test_graphing.py
|   `-- test_math_utils.py
|-- docs/
|   |-- readmes/                   Detailed README files and documentation indexes
|   |-- planning/                  Ideas, progress, proposals, and planning archive
|   |-- implementation/            Feature implementation plans and their archive
|   |-- testing/                   Test guides
|   |-- overview/                  Architecture explanations
|   |-- demo/                      Walkthrough and recording materials
|   |-- fixes/                     Fix proposals and records
|   `-- notes/                     Historical learning and development notes
|-- scripts/check_docs.cjs          Local Markdown link and heading check
|-- requirements.txt
|-- requirements-dev.txt            Runtime and Python test dependencies
|-- requirements-build.txt          PyInstaller build dependencies
|-- VERSION                         One version number for web and desktop builds
|-- version.py                      Safe version-file reader
|-- run_app.py                      Cross-platform setup and launch script
|-- run_mac.command                 macOS double-click launcher
|-- run_windows.bat                 Windows double-click launcher
|-- desktop_launcher.py             Desktop bundle entry point
|-- delphic_desktop.spec            PyInstaller bundle config
|-- packaging/build_mac_release.sh  macOS build, test, and DMG workflow
|-- Procfile
`-- .env.example
```

## Getting Started

### Requirements

- Python 3.10 or newer
- Internet and an eligible provider account/key for AI answers. Existing saved
  material and supported local graphing do not need a paid AI request.
- Node.js/npm and Playwright for browser tests, not for normal tutoring

### Default AI models

These are the defaults currently configured in `ai/service.py`. They are not a
live catalog, price comparison, or guarantee of availability or account access.
Check the exact provider/model before a demo; the app does not automatically
verify a key or model when you save Settings.

| Provider | Default model |
| --- | --- |
| Groq | `openai/gpt-oss-120b` |
| OpenAI | `gpt-5.6-luna` |
| Anthropic | `claude-haiku-4-5-20251001` |
| Google Gemini | `gemini-3.5-flash` |
| Mistral | `magistral-small-latest` |
| Together AI | `openai/gpt-oss-120b` |
| xAI | `grok-4.20-0309-reasoning` |
| DeepSeek | `deepseek-v4-pro` |
| OpenRouter | `openai/gpt-5.6-terra` |

### Installation

The easiest source-code option is to download or clone the project, then run the launcher for your computer:

- macOS: double-click `run_mac.command`, or run `python3 run_app.py`
- Windows: double-click `run_windows.bat`, or run `py -3 run_app.py`

The launcher creates `.venv`, installs `requirements.txt`, creates private settings if needed, starts the app, and opens `http://127.0.0.1:5001`.

On macOS, double-click `run_mac.command`. If Finder blocks it, open Terminal, type `zsh` and one space, drag `run_mac.command` into Terminal, and press Return.

The source launcher stores private configuration and chat history outside the downloaded project:

- macOS: `~/Library/Application Support/Delphic AI`
- Windows: `%APPDATA%\Delphic AI`

Legacy files in `corpus/` remain on disk but are not searched. New Study Library
notes saved through the app are searched when enabled for the current tutor.

After the first launch, use **AI Settings** in Delphic AI to choose a provider and add an API key. Manual `.env` configuration is also supported:

By default, an API key entered through **AI Settings** stays in memory only while
Delphic AI is running. Rebuilt native desktop apps offer an optional **Remember
key on this device** checkbox, using Mac Keychain or Windows Credential Manager.
It saves one connection per operating-system account and app data folder. The
website and source web launcher do not enable device storage. Older downloaded
apps need rebuilding to include this feature.

Leave remembering off on shared computers. Unchecking it and saving removes the
stored copy but keeps the current temporary connection; **Forget saved key**
removes both the stored copy and this browser session's temporary key. A key
manually configured in `.env` remains a separate fallback and is not removed.
Storage failures are reported rather than falling back to plaintext files.
Manual `.env` setup below is still supported, but `.env` is not an encrypted vault.

Protected storage is not a promise that only a human can read the key: the app
and provider use it, and someone using the same unlocked operating-system account
or malware may access it. On Mac, other scripts using the same Python executable
can have access under Keychain's default permissions; a signed, tested desktop
build is preferable to a shared Python installation. See the
[keyring security notes](https://keyring.readthedocs.io/en/stable/#security-considerations).

To check remembered keys in a rebuilt desktop app:

1. Open Settings, connect with a key, and enable **Remember key on this device**.
2. Quit the desktop app itself, not just the browser tab, then reopen it.
3. Check that Settings shows the remembered provider/model without displaying the key.
4. Uncheck remembering and save, then quit/reopen. The temporary connection should
   be gone unless a separate `.env` key is configured.
5. Remember the connection again, use **Forget saved key**, and repeat the restart
   check. A storage error must be visible, not reported as successful removal.

Automated tests use fake vaults; native Mac/Windows round-trip tests and rebuilt
installer validation remain release checks. Do not use a student's key in test logs.

```text
GROQ_API_KEY=your-groq-api-key-here
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
GOOGLE_API_KEY=your-google-api-key-here
MISTRAL_API_KEY=your-mistral-api-key-here
TOGETHER_API_KEY=your-together-api-key-here
XAI_API_KEY=your-xai-api-key-here
DEEPSEEK_API_KEY=your-deepseek-api-key-here
OPENROUTER_API_KEY=your-openrouter-api-key-here
DELPHIC_ENABLE_EXPERIMENTAL_IMAGES=false
FLASK_SECRET_KEY=created-by-the-launcher-or-change-me
```

### Manual Source Setup

For macOS/Linux, run from the cloned project:

```bash
git clone https://github.com/advay4ever/Math-AI-agent.git
cd Math-AI-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Set a long, private `FLASK_SECRET_KEY` in `.env` before relying on saved browser
ownership across restarts. Do not leave the example signing-key placeholder.
Then start the source server using `.venv`:

```bash
python app.py
```

Open `http://127.0.0.1:5001`; Science is at `/science`. Direct `app.py` uses the
project-root database and `instance/` image folder unless `DELPHIC_DATA_DIR` is
set. The source launcher uses the per-user folders listed above instead; these
are different data locations, not automatically synchronized copies.

For Windows PowerShell, after cloning and entering the project folder:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
# Set a private FLASK_SECRET_KEY in .env, then:
python app.py
```

### Building The Mac App

The regular source launcher above still requires Python. A release developer can
create a Mac app that already contains Python:

```bash
source .venv/bin/activate
python -m pip install -r requirements-build.txt
packaging/build_mac_release.sh
```

The release script reads the version from `VERSION`, runs the Python and browser
tests, builds `Delphic AI.app`, smoke-tests its Math and Science pages, creates a
`.dmg`, and writes a SHA-256 checksum. Without Apple credentials, the filename
contains `unsigned` and is meant only for local testing.

See [Mac Release Checklist](../MAC_RELEASE_CHECKLIST.md) before sharing a build.

## Testing

Run the Python test suite with:

```bash
python -m pytest -q
```

The development requirements include the normal app packages and `pytest`. If you
used the launcher before running tests, install them with
`python -m pip install -r requirements-dev.txt` inside `.venv` first.

Run the browser checks for interactive graphs and tutor controls with:

```bash
npm ci
npx playwright install chromium
DELPHIC_TEST_PORT=5004 npm run test:e2e
```

Playwright starts an isolated server on port `5004` by default, with temporary
test data. It refuses to reuse an existing server. Set `DELPHIC_TEST_PORT`
explicitly because the localhost-navigation test otherwise falls back to `5001`.
Choose another unused port if necessary; do not run tests against a personal
data directory. In PowerShell, set `$env:DELPHIC_TEST_PORT = "5004"`, then run
`npm run test:e2e`.
It uses the Python executable inside `.venv`.
Developers can set `DELPHIC_PYTHON` to a different Python executable when needed.

Check project Markdown links and local heading anchors with:

```bash
node scripts/check_docs.cjs
node --test tests/docs-check.test.cjs
```

This excludes installed dependencies, generated output, and private runtime data.
It checks local links, not external website uptime or factual accuracy. Historical
test counts belong in dated records; do not present a focused test run as a new
complete release verification.

The automated Python and browser test suites cover:

- Math utility operations
- Follow-up classification
- Math Step-by-Step and practice prompt behavior
- Science Guided Reasoning, practice, and Quiz Mode instructions
- Science quiz continuation and grading rules
- Math and Science session separation
- Tutor page rendering and navigation
- Science prompt wiring and Math-tool redirection
- Safe local 2D and 3D graph data, including bounded surface meshes
- 3D graph camera views, theme rerendering, coordinate inspection, and phone layout
- Desktop launcher behavior
- Experimental image request validation, safety, provider errors, review retries, private ownership, storage, and deletion
- Create image controls, mobile themes, refresh restoration, portable MathML HTML export, and large ZIP export
- Fixed image-quality evaluation coverage and release score calculations

## Deployment

The included `Procfile` starts the Flask app with Gunicorn:

```text
web: gunicorn app:app
```

This is a server entry point, not a complete production deployment. The current
application has browser-session ownership checks but no user accounts, login,
school administration, production spending controls, or complete hosted privacy
infrastructure. Temporary API keys and request locks are process-local; adding
workers does not make them shared. See [SECURITY.md](../../SECURITY.md) and the
[website launch proposal](../implementation/WEB_DEPLOYMENT_STEP_BY_STEP_PLAN.md)
before exposing the app. No public deployment is claimed complete.

Keep a stable private `FLASK_SECRET_KEY`, configure trusted hosts explicitly, and
review the exact provider's terms and data handling. As checked October 29,
OpenRouter requires users to be at least 18; this is an eligibility blocker, not
something an API key or stronger filter bypasses. [OpenRouter terms](https://openrouter.ai/terms).

## Current Boundaries

- AI answers can be incorrect and should be checked when accuracy matters.
- Confidence badges reflect the model's reported label, not a calibrated score
  or independent verification that the answer is true.
- SymPy verification applies only to supported Math expressions and operations.
- Science quiz grading is generated by the AI rather than a fixed question bank.
- Interactive graphing is available only in the Math tutor.
- Local graphing supports the 2D and 3D graph types listed in the Math tutor section, including polar, parametric, implicit, piecewise, inequality, and vector-field graphs.
- Conversations are stored in a local SQLite database.
- Sessions are browser-based and are not connected to student accounts.
- Experimental image generation is controlled by `DELPHIC_ENABLE_EXPERIMENTAL_IMAGES` and disabled by default. No separate student or school mode is implemented. Stronger request filtering and output review are safeguards, not a guarantee of suitability for minors. Provider eligibility and student-release approval remain separate unresolved requirements.
- A real paid image smoke test and the blind human accuracy evaluation have not been run in this workspace. Passing mocked tests is not proof that the selected model is accurate enough to release.
- The experimental image owner boundary uses a signed browser session, not a production student account. A public multi-user deployment needs real account authorization and shared rate-limit/idempotency storage.
- The app currently responds in English.

## Chat Privacy And Legacy Data

New Math and Science chats are assigned to a server-generated browser owner in
a signed session cookie. Listing, switching, downloading, clearing, deletion,
titles, continuation, and saved graph state check ownership. New images use that
same owner; client-provided owner headers cannot grant access. Tabs in the same
browser profile share ownership. Separate browser profiles do not share chats.
Tabs keep their own selected chat IDs in per-tutor session storage and explicitly
identify the visible chat on stateful requests. The server rechecks owner and
tutor mode; another tab's current selection cannot silently redirect a question.
Session storage holds no API keys. Dirty Settings drafts survive background/focus
refreshes, while real expiry/Forget still invalidates saved-key reuse.
Closing Settings also keeps unsaved provider/model choices for the current page,
but clears an unsaved key. Remembered desktop connections intentionally survive
app restart until removed; this is separate from temporary-key expiry.

History initially renders 40 messages; **Load earlier messages** prepends older
batches. Exports collect all pages before producing HTML/ZIP. A single export is
limited to 10,000 messages, 32 MiB of serialized message data, and 64 MiB of image
data. Size limits or mid-download deletion produce an explicit error, not a
partial file. The snapshot bounds message IDs, not concurrent edits to their text.
Older loaded pages remain until navigation; this is not a virtualized timeline.

The Mac desktop server now has eight bounded request workers. Saturation returns
503 with `Retry-After`; conflicting writes within a chat return a retryable 409
instead of overlapping deletion/generation/continuation. Other chats and ordinary
reads can proceed while a provider request is slow. These locks are process-local,
not distributed production infrastructure. Rebuilt installer validation is pending.

The October 25 privacy upgrade intentionally leaves older unowned chats and
images unassigned and hidden from browser lists/downloads. Their data is preserved
in SQLite and on disk, not deleted or assigned to the first visitor. No browser
archive/import screen is included; local recovery would need separate approval.
Before changing an existing populated database, startup backs up its SQLite data
and generated-image files. Backups live in `instance/ownership-backups/<id>/` for
the default source layout, or `DELPHIC_DATA_DIR/ownership-backups/<id>/` when set.
If the backup fails, startup stops the upgrade. Stop other app processes before
upgrading an existing installation; do not run older builds against its database.

Keep `FLASK_SECRET_KEY` private and stable across restarts and workers. Clearing
cookies or changing that key can remove browser access without deleting the
saved chats. This is local browser-session isolation, not student accounts,
cross-device sync, encrypted database storage, or production-grade authorization.
Restart source apps to load the fix; desktop downloads require rebuilding and
testing. See the [review findings](../testing/PROJECT_CODE_REVIEW_FINDINGS.md)
for source verification and remaining release blockers.

## Documentation

The current documentation index is available in [Documentation README](DOCUMENTATION_README.md).
