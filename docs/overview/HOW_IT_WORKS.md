# How Delphic AI Works

---

## 🗂️ Project File Map

```
project-root/
├── app.py              ← The web server (handles requests)
├── ai/
│   ├── service.py      ← Talks to Groq AI (the AI brain)
│   ├── detector.py     ← Detects math type, runs SymPy, detects graph requests
│   ├── math_tools.py   ← Does symbolic math + Desmos graph conversion
│   └── prompt.py       ← Settings and the AI's personality
├── requirements.txt    ← List of libraries to install
├── .env                ← Your secret API key (you create this)
├── templates/
│   └── index.html      ← The webpage the user sees
└── static/
    ├── style.css       ← Makes the page look pretty
    └── script.js       ← Makes the chat work in the browser
```

---

## 🏗️ The Big Picture

Think of this app like a **pizza restaurant**:

| Restaurant | This App |
|---|---|
| Customer orders pizza | You type a math question |
| Waiter takes the order | `app.py` receives your message |
| Calculator checks the answer | `ai/detector.py` runs SymPy first |
| Chef explains the recipe | `ai/service.py` asks Groq AI to explain it step by step |
| Pizza is served | The answer is shown in the chat |

---

## 📄 File-by-File Explanation

---

### 1. `app.py` — The Web Server (The Waiter 🧑‍🍳)

This is the **heart** of the app. It uses **Flask**, a simple Python tool for building websites.

It has 3 jobs:

- **`/` (home page)** → When you open the browser, it loads the chat page.
- **`/ask` (receive question)** → When you send a message, it validates the input, asks SymPy to solve it first, then passes everything to the AI, and sends the answer back.
- **`/plot` (generate graph)** → When you ask to plot a function, it generates a graph image and sends it back.
- **`/clear` (clear chat)** → When you click "Clear Chat", it wipes the conversation history.

It also:
- Validates input (rejects messages shorter than 3 chars or longer than 2000 chars)
- Keeps track of your **conversation history** (up to the last 20 messages) so the AI remembers what you said earlier

---

### 2. `ai/service.py` — The AI Brain (The Chef 🤖)

This file **talks to Groq's AI** — a super-fast AI service that runs the GPT-OSS 120B model.

How it works:
1. Takes the full conversation history (all your previous messages + AI replies)
2. Adds the **system prompt** (the AI's instructions — defined in `ai/prompt.py`)
3. If SymPy solved the problem, includes the verified answer as a hint
4. Sends it all to Groq
5. Returns the AI's response back to the web server

Key settings:
- **`model: openai/gpt-oss-120b`** → Uses a powerful 120 billion parameter model
- **`temperature: 0.3`** → Keeps answers focused and consistent (lower = less random)
- **`max_tokens: 2048`** → Limits how long each answer can be

---

### 3. `ai/prompt.py` — Settings & AI Personality (The Recipe 📋)

This file stores two things:

**① App Settings** — reads from your `.env` file:
- `GROQ_API_KEY` → Your secret key to access Groq AI
- `FLASK_SECRET_KEY` → A password used to secure your session/cookies
- `FLASK_DEBUG` → Whether to run in debug mode

**② The System Prompt** — this is the most important part. It tells the AI *how to behave*:
- Act as a friendly high school math tutor
- Always explain solutions step by step
- Use LaTeX for all math (e.g. `\( x^2 + 1 \)` renders as a proper equation)
- Cover: Algebra, Geometry, Trig, Calculus, Statistics
- End every answer with a "💡 Quick Tip"
- Stay on topic — only answer math questions

> 🔑 **This is why the AI acts like a tutor and not just a general chatbot.**

---

### 4. `ai/math_tools.py` — The Symbolic Calculator (The Calculator 🔢)

This uses **SymPy**, a Python math library that can do *exact* math (not just decimal approximations).

It has 6 tools:

| Function | What it does | Example |
|---|---|---|
| `solve_equation()` | Solves equations for x | `x² - 5x + 6 = 0` → `x = 2, 3` |
| `simplify_expression()` | Simplifies expressions | `sin²x + cos²x` → `1` |
| `differentiate()` | Finds the derivative | `x³` → `3x²` |
| `integrate_expr()` | Finds the integral | `x²` → `x³/3 + C` |
| `factor_expression()` | Factors polynomials | `x² + 5x + 6` → `(x+2)(x+3)` |
| `get_desmos_latex()` | Converts functions for Desmos | `sin(x)` → Desmos-ready LaTeX |

Math results are returned as **LaTeX** so they look beautiful in the browser. Graph requests are converted into Desmos-ready expressions and rendered interactively in the frontend.

---

### 4.5 `ai/detector.py` — The Math Detective (NEW in Phase 2! 🔍)

This file is the **glue** between SymPy and the AI. It reads the student's question and figures out what kind of math it is.

How it works:
1. Reads your message (e.g. "Solve x² + 5x + 6 = 0")
2. Looks for keywords like "solve", "factor", "simplify", "derivative", "integrate"
3. Extracts the math expression from your sentence
4. Runs the matching SymPy function to get the exact answer
5. Returns the verified answer so the AI can use it

| If you say... | It detects... | SymPy runs... |
|--------------|--------------|--------------|
| "Solve x² + 5x + 6 = 0" | Solve | `solve_equation()` |
| "Factor x² + 5x + 6" | Factor | `factor_expression()` |
| "Simplify (x²+2x+1)/(x+1)" | Simplify | `simplify_expression()` |
| "Derivative of 3x² + 2x" | Derivative | `differentiate()` |
| "Integrate x²" | Integral | `integrate_expr()` |
| "Plot y = x² - 4" | Graph | `get_desmos_latex()` |
| "What is algebra?" | Nothing | AI handles it alone |

> 🔑 **This is why the AI now gives correct answers — SymPy checks the math first!**

---

### 5. `templates/index.html` — The Webpage (The Menu 🖥️)

This is what you see in the browser. It has:
- A **sidebar** with topic shortcuts (Algebra, Geometry, etc.) and quick questions
- A **chat area** where messages appear
- An **input box** where you type your question
- A **send button** and **clear chat button**

It loads two special JavaScript libraries:
- **KaTeX** → Renders LaTeX math as beautiful formatted equations
- **Marked.js** → Renders Markdown (bold, bullet points, etc.) in the AI's responses

---

### 6. `static/style.css` — The Design (The Decoration 🎨)

Handles all the visuals:
- **Light and Dark theme** (saved in your browser so it remembers your preference)
- Chat bubbles (purple for your messages, white/dark for AI replies)
- Responsive layout — works on both phone and desktop
- Animated typing indicator (the bouncing dots while AI is thinking)

---

### 7. `static/script.js` — The Chat Logic (The Interactivity ⚡)

Makes the page interactive. It:
1. Listens for when you press **Enter** or click **Send**
2. **Validates your input** — warns you if the question is too short (under 3 chars)
3. Shows your message in the chat immediately
4. Replaces the send button with a **loading spinner** while waiting for the AI
5. Shows the **typing indicator** (dots) while the AI is thinking
6. Sends your message to the server (`/ask`) using `fetch()`
7. If it's a graph request, also sends to `/plot` in parallel
8. When the response comes back, renders it with **Markdown + KaTeX**
9. Adds a **📋 Copy button** on each AI response (appears on hover)
10. If a graph was requested, displays an **interactive Desmos graph** in the chat
11. Auto-resizes the text box as you type
12. Handles **sidebar clicks** (topics fill the input, quick actions send immediately)

---

## 🔄 Full Flow — What Happens When You Ask a Question

```
You type: "Solve x² + 5x + 6 = 0"
        ↓
[script.js]       Sends a POST request to /ask with your message
        ↓
[app.py]          Receives the message, adds it to conversation history
        ↓
[ai/detector.py]  Detects it's a "solve" problem, runs SymPy → x = -2, x = -3
        ↓
[app.py]          Attaches SymPy's verified answer as a hint for the AI
        ↓
[ai/service.py]   Sends history + system prompt + SymPy hint to Groq AI
        ↓
[Groq GPT-OSS]    Generates a step-by-step explanation guided by SymPy's answer
        ↓
[app.py]          Sends the response back as JSON
        ↓
[script.js]       Renders Markdown with Marked.js, renders math with KaTeX
        ↓
You see: A beautifully formatted, mathematically correct solution ✅
```

---

## 🔐 The `.env` File — Your Secrets

This file is **never shared or committed to Git**. It holds:

```
GROQ_API_KEY=gsk-your-key-here      ← Required to use Groq AI
FLASK_SECRET_KEY=any-random-string   ← Secures your session cookies
FLASK_DEBUG=true                     ← Shows errors during development
```

> ⚠️ Without the `GROQ_API_KEY`, the AI won't work. You get one from [console.groq.com](https://console.groq.com).

---

## 📦 `requirements.txt` — The Dependencies

These are the Python libraries the app needs:

| Library | Purpose |
|---|---|
| `flask` | Web server framework |
| `openai` | Talk to Groq AI (uses the same library) |
| `python-dotenv` | Read the `.env` file |
| `sympy` | Symbolic math engine |
| `gunicorn` | Production-grade web server |

---

## 🚀 Why Port 5001?

macOS reserves **port 5000** for AirPlay Receiver (a built-in system feature). So when you tried to open `localhost:5000`, your Mac blocked it. We switched the app to run on **port 5001** to avoid this conflict.

---

*That's the entire app — 8 files, one AI tutor!* 🎓
