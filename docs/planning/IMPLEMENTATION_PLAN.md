# 🗺️ Implementation Plan — Delphic AI

> A step-by-step roadmap of what was built, what's working, and what's next.

---

## ✅ Phase 1 — Core Setup (DONE)

Everything needed to get the app running:

- [x] Set up Flask web server (`app.py`)
- [x] Connected to Groq AI (`ai/service.py`)
- [x] Created the AI tutor personality via system prompt (`ai/prompt.py`)
- [x] Built the chat UI (sidebar, message bubbles, input box)
- [x] Added LaTeX math rendering (KaTeX)
- [x] Added Markdown rendering (Marked.js)
- [x] Added light/dark theme toggle
- [x] Made the layout responsive (works on phone + desktop)
- [x] Added conversation memory (last 20 messages)
- [x] Added SymPy symbolic math utilities (`ai/math_tools.py`)
- [x] Written 13 unit tests — all passing ✅
- [x] Fixed port conflict (switched from 5000 → 5001)
- [x] Created `requirements.txt` and virtual environment

---

## 🔧 Phase 2 — Making It Better (DONE)

Improvements to the core app:

- [x] **Add the `.env` file** with a real Groq API key ✅
- [x] **Connect SymPy to the chat** — SymPy now auto-detects math (solve, factor, simplify, differentiate, integrate) and feeds verified answers to the AI ✅
- [x] **Loading spinner** on the send button while waiting for the AI ✅
- [x] **Copy button** on each AI message so students can copy solutions easily ✅
- [x] **Input validation** — warn the user if they type something too short ✅
- [x] **Math graphs** — when a student asks to plot a function (e.g. `plot y = x²`), show a graph ✅

---

## 🚀 Phase 3 — Polish and Deploy

Getting the app ready for other people to use:

- [x] **UI Polish** — timestamps on messages, character counter, smooth scroll ✅
- [ ] **Procfile created** — `gunicorn app:app` ready for Render ✅
- [x] **Tested Gunicorn locally** — confirmed working on port 5001 ✅
- [x] **SSH-based GitHub remote** — secure pushes via SSH ✅
- [ ] Deploy to a cloud platform (e.g. **Render** or **Railway**)
- [ ] Set environment variables securely on the cloud
- [ ] Add HTTPS (SSL certificate — automatic on Render)
- [ ] Set up rate limiting (so no one spams the API)
- [ ] Set `FLASK_DEBUG=false` in production
- [ ] Rotate the `FLASK_SECRET_KEY` before deploying

---

## 🔐 Security Checklist

Important things to do before going public:

- [x] Never commit the `.env` file to GitHub (already in `.gitignore` ✅)
- [ ] Add a rate limiter (max X questions per minute per user)
- [ ] Validate and sanitise all user inputs
- [ ] Rotate the `FLASK_SECRET_KEY` before deploying
- [ ] Set `FLASK_DEBUG=false` in production

---

## 📁 Current File Structure

```
project-root/
├── app.py                  ✅ Web server
├── ai/
│   ├── service.py          ✅ Groq AI integration
│   ├── detector.py         ✅ Detects math type + runs SymPy
│   ├── math_tools.py       ✅ SymPy math engine
│   └── prompt.py           ✅ Settings + AI prompt
├── requirements.txt        ✅ Dependencies
├── .env                    🔒 Secret API key (gitignored)
├── .env.example            ✅ Template for secrets
├── .gitignore              ✅ Protects secrets
├── templates/
│   └── index.html          ✅ Chat UI
├── static/
│   ├── style.css           ✅ Styling + themes
│   └── script.js           ✅ Chat interactivity
├── tests/
│   └── test_math_utils.py  ✅ 13 unit tests (all passing)
└── docs/
    ├── README.md           ✅ Documentation index
    ├── overview/           ✅ App overview and architecture
    ├── planning/           ✅ Roadmap and future ideas
    ├── notes/              ✅ Learning and AI notes
    └── fixes/              ✅ Bug-fix writeups
```

---

*Last updated: March 15, 2026*
