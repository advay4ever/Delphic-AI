# Delphic AI

Delphic AI is a web-based learning assistant with separate Math and Science tutor workspaces. Both tutors run in the same Flask application on port `5001`, while keeping their interfaces, prompts, tools, and conversation histories separate.

The app can use several AI providers from an in-app setup popup. Math responses can be checked with SymPy and displayed with interactive Desmos graphs. Both tutors support streamed responses, formatted equations, saved sessions, transcript downloads, and guided learning controls.

For the simplest local setup, start with [START_HERE.md](START_HERE.md).

## Current Status

| Area | Current implementation |
|------|------------------------|
| Home | Shared entry page for the Math and Science tutors |
| Math tutor | Explanations, guided steps, work checking, practice, and graphing |
| Science tutor | Concept help, guided reasoning, practice, and interactive quizzes |
| AI provider | User-selected provider: Groq, OpenAI, Anthropic, Google Gemini, Mistral, Together AI, xAI, or DeepSeek |
| Storage | Local SQLite conversation and session history |
| Frontend | Flask templates, HTML, CSS, and JavaScript |
| Math rendering | KaTeX |
| Math verification | SymPy for supported expressions and equations |
| Graphing | Desmos in the Math tutor |
| Automated tests | 51 tests |

## Workspaces

### Home

The home page introduces Delphic AI and provides direct buttons for both tutors. Each tutor sidebar also contains the same three navigation choices:

- Home
- Math tutor
- Science tutor

The current tutor is visually identified in the Workspace section.

### Math Tutor

The Math tutor currently supports:

- Step-by-step explanations
- Interactive Step-by-Step Mode with one next question at a time
- Follow-up questions such as `Why?` and requests for simpler language
- Work checking that identifies the first incorrect step
- Similar practice-problem generation
- SymPy-backed verification for supported operations
- Interactive Desmos graphs for functions and points
- Multi-turn graph requests using the last plotted equation
- Algebra, geometry, trigonometry, calculus, statistics, and word problems

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

## Shared Features

Both tutor workspaces include:

- Streamed AI responses
- Recent conversation context for follow-up questions
- New Chat, session switching, and Clear Chat controls
- Separate Math and Science session lists
- Copy controls on tutor responses
- Browser-openable `.html` transcript downloads
- A post-download message showing the filename and where to find the Downloads folder
- Light, dark, and neon themes
- Confidence badges on AI answers
- Responsive desktop, tablet, and mobile layouts
- English responses by default
- Input-length validation and learning-focused safety redirection

## Example Prompts

### Math

| Prompt | Result |
|--------|--------|
| `Solve 2x + 3 = 11` | Step-by-step algebra explanation |
| `Why did you subtract 3?` | Follow-up reasoning using recent context |
| `Explain that in 5th grade language` | Simpler wording and smaller steps |
| `Give me a similar practice problem` | One related problem without its answer |
| `Find the derivative of x^3 + 2x` | Calculus explanation with SymPy guidance |
| `Plot sin(x)` | Explanation plus an interactive graph |
| `Plot (3, 0)` | Interactive coordinate point |

### Science

| Prompt | Result |
|--------|--------|
| `Explain photosynthesis in simple words` | Student-friendly concept explanation |
| `What does erosion mean in Earth science?` | Vocabulary explanation with context |
| `What does F = ma mean in real life?` | Formula connected to an example |
| `Check my reasoning: a chemical reaction creates new atoms` | Reasoning check and correction |
| `Give me a practice question about ecosystems` | One Science practice question |
| Select `Quiz Mode` | Interactive five-question Science quiz |

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
  +-- Desmos graph data for Math requests
```

The main browser request uses Server-Sent Events so the tutor response can appear while it is being generated. The completed response is saved to SQLite and restored when the user returns to that session.

## Main Routes

| Route | Purpose |
|-------|---------|
| `/` | Home page and Math tutor |
| `/science` | Science tutor |
| `/stream` | Stream a Math response |
| `/science/stream` | Stream a Science response |
| `/plot` | Produce Math graph data |
| `/history` | Load the current Math conversation |
| `/science/history` | Load the current Science conversation |
| `/sessions` | List Math sessions |
| `/science/sessions` | List Science sessions |
| `/clear` | Clear the current Math conversation |
| `/science/clear` | Clear the current Science conversation |

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
|   `-- math_tools.py              SymPy operations
|-- templates/
|   |-- index.html                 Home page and Math tutor
|   `-- science.html               Science tutor
|-- static/
|   |-- script.js                  Shared browser behavior
|   |-- style.css                  Themes and responsive styling
|   `-- assets/                    Delphic logo files
|-- tests/
|   |-- test_follow_up_detection.py
|   `-- test_math_utils.py
|-- docs/                           App documentation and development records
|-- requirements.txt
|-- requirements-build.txt          PyInstaller build dependencies
|-- run_app.py                      Cross-platform setup and launch script
|-- run_mac.command                 macOS double-click launcher
|-- run_windows.bat                 Windows double-click launcher
|-- desktop_launcher.py             Desktop bundle entry point
|-- delphic_desktop.spec            PyInstaller bundle config
|-- Procfile
`-- .env.example
```

## Getting Started

### Requirements

- Python 3.10 or newer
- An API key for one supported AI provider

### Default AI models

The in-app provider picker uses cost-balanced defaults for math and science tutoring:

| Provider | Default model |
| --- | --- |
| Groq | `openai/gpt-oss-120b` |
| OpenAI | `gpt-5-mini` |
| Anthropic | `claude-haiku-4-5-20251001` |
| Google Gemini | `gemini-3.5-flash` |
| Mistral | `magistral-small-latest` |
| Together AI | `openai/gpt-oss-120b` |
| xAI | `grok-4.20-0309-reasoning` |
| DeepSeek | `deepseek-v4-pro` |

### Installation

The easiest option is to download or clone the project, then run the launcher for your computer:

- macOS: double-click `run_mac.command`, or run `python3 run_app.py`
- Windows: double-click `run_windows.bat`, or run `py -3 run_app.py`

The launcher creates `.venv`, installs `requirements.txt`, creates private settings if needed, starts the app, and opens `http://127.0.0.1:5001`.

On macOS, double-click `run_mac.command`. If Finder blocks it, open Terminal, type `zsh` and one space, drag `run_mac.command` into Terminal, and press Return.

The source launcher stores private configuration and chat history outside the downloaded project:

- macOS: `~/Library/Application Support/Delphic AI`
- Windows: `%APPDATA%\Delphic AI`

After the first launch, use **AI Settings** in Delphic AI to choose a provider and add an API key. Manual `.env` configuration is also supported:

An API key entered through **AI Settings** stays in memory only while Delphic AI is running. Users who intentionally want a persistent key can add it to the private `.env` file in the data folder above.

```text
GROQ_API_KEY=your-groq-api-key-here
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
GOOGLE_API_KEY=your-google-api-key-here
MISTRAL_API_KEY=your-mistral-api-key-here
TOGETHER_API_KEY=your-together-api-key-here
XAI_API_KEY=your-xai-api-key-here
DEEPSEEK_API_KEY=your-deepseek-api-key-here
FLASK_SECRET_KEY=created-by-the-launcher-or-change-me
```

Manual setup is also supported:

```bash
git clone https://github.com/advay4ever/Math-AI-agent.git
cd Math-AI-agent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

On Windows PowerShell, activate the environment with:

```powershell
venv\Scripts\Activate.ps1
```

Set the local values in `.env`:

```text
GROQ_API_KEY=your-groq-api-key-here
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
GOOGLE_API_KEY=your-google-api-key-here
MISTRAL_API_KEY=your-mistral-api-key-here
TOGETHER_API_KEY=your-together-api-key-here
XAI_API_KEY=your-xai-api-key-here
DEEPSEEK_API_KEY=your-deepseek-api-key-here
FLASK_SECRET_KEY=change-me-in-development
```

Run the app:

```bash
python app.py
```

Open `http://127.0.0.1:5001` in a browser. The Science tutor is available at `http://127.0.0.1:5001/science`.

## Testing

Run the complete automated test suite with:

```bash
python -m pytest
```

The current 36 tests cover:

- Math utility operations
- Follow-up classification
- Math Step-by-Step and practice prompt behavior
- Science Guided Reasoning, practice, and Quiz Mode instructions
- Science quiz continuation and grading rules
- Math and Science session separation
- Tutor page rendering and navigation
- Science prompt wiring and Math-tool redirection

## Deployment

The included `Procfile` starts the Flask app with Gunicorn:

```text
web: gunicorn app:app
```

Set an AI provider API key and a private `FLASK_SECRET_KEY` in the deployment environment. The current application is an educational prototype without user accounts, per-user authentication, or production-grade privacy controls.

## Current Boundaries

- AI answers can be incorrect and should be checked when accuracy matters.
- SymPy verification applies only to supported Math expressions and operations.
- Science quiz grading is generated by the AI rather than a fixed question bank.
- Interactive graphing is available only in the Math tutor.
- Conversations are stored in a local SQLite database.
- Sessions are browser-based and are not connected to student accounts.
- The app currently responds in English.

## Documentation

The current documentation index is available in [docs/README.md](docs/README.md).
