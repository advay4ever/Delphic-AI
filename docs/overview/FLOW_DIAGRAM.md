# 🔄 App Flow Diagram — How It All Works!

*(Written in simple terms so anyone can understand)*

---

## The Big Picture 🗺️

There are **4 players** in this app — like 4 people passing a note:

```
  🖥️ YOU              🐍 PYTHON           🧮 SYMPY          🤖 GROQ AI
(Browser)    ──►     (Flask)      ──►   (Calculator)  ──►   (Internet)
"I have a            "Got it!            "The answer          "Let me
 question"            Let me check        is x = -2            explain it
                      with SymPy          and x = -3"          step by step!"
                      first..."
```

---

## Step-by-Step Flow 👣

```
╔═════════════════════════════════════════════════════════════════╗
║  STEP 1 — YOU TYPE YOUR QUESTION  🖊️                           ║
║  "This is your desk at school"                                  ║
║                                                                 ║
║   You type:  "Solve x² + 5x + 6 = 0"                           ║
║   You press: SEND  ➤                                            ║
╚══════════════════════════╦══════════════════════════════════════╝
                           ║
                    📬 Your message is put
                    in an envelope and sent
                    (this is called HTTP)
                           ║
                           ▼
╔═════════════════════════════════════════════════════════════════╗
║  STEP 2 — THE CHAT PAGE REACTS  💬                              ║
║  "This is like your notebook updating itself"                   ║
║                                                                 ║
║   ✅  Your message appears in the chat right away               ║
║   💬  Bouncing dots appear  (= "please wait, thinking...")      ║
║   🔒  Send button goes grey  (= "one at a time please!")        ║
╚══════════════════════════╦══════════════════════════════════════╝
                           ║
                    📬 Message travels to
                    the Python code
                    on your computer
                           ║
                           ▼
╔═════════════════════════════════════════════════════════════════╗
║  STEP 3 — FLASK (PYTHON) RECEIVES IT  🐍                        ║
║  "This is like the school receptionist"                         ║
║                                                                 ║
║   📥  Opens the envelope, reads your question                   ║
║   📚  Looks up your conversation history                        ║
║       (so the AI remembers what you said before)                ║
║   📎  Clips your new question to the history                     ║
║   🧮  Asks SymPy: "Can you solve this?"                         ║
╚══════════════════════════╦══════════════════════════════════════╝
                           ║
                    🧮 SymPy checks: "Is this
                    a solve, factor, simplify,
                    derivative, or integral?"
                           ║
                           ▼
╔═════════════════════════════════════════════════════════════════╗
║  STEP 3.5 — SYMPY TRIES TO SOLVE IT  🧮  (NEW in Phase 2!)     ║
║  "This is like a calculator that never makes mistakes"          ║
║                                                                 ║
║   If it's a math problem SymPy can solve:                       ║
║   ✅  SymPy solves it instantly (e.g. x = -2, x = -3)          ║
║   📎  The verified answer is attached for the AI to use         ║
║                                                                 ║
║   If it's NOT a solvable equation (e.g. "What is algebra?"):    ║
║   😴  SymPy does nothing — the AI handles it alone              ║
╚══════════════════════════╦══════════════════════════════════════╝
                           ║
                    📦 Packs a box containing:
                    • The tutor rules
                      ("always explain step by step")
                    • Your full conversation
                    • Your new question
                    • SymPy's verified answer (if found)
                           ║
                           ▼
╔═════════════════════════════════════════════════════════════════╗
║  STEP 4 — THE BOX IS SENT TO GROQ  🌐                           ║
║  "This is like mailing a letter to a genius friend far away"    ║
║                                                                 ║
║   The box travels over the INTERNET to Groq's computers         ║
║   Groq runs a giant AI called  GPT-OSS 120B                     ║
║   It has read millions of math textbooks 📚📚📚                 ║
╚══════════════════════════╦══════════════════════════════════════╝
                           ║
                    🧠 The AI reads everything
                    and starts writing an answer
                           ║
                           ▼
╔═════════════════════════════════════════════════════════════════╗
║  STEP 5 — AI THINKS AND WRITES THE ANSWER  🤖                   ║
║  "This is like your genius friend writing back"                 ║
║                                                                 ║
║   Reads the rules:  "I must explain step by step"               ║
║   Reads your question: "Solve x² + 5x + 6 = 0"                 ║
║   Reads SymPy's hint: "The answer is x = -2 and x = -3"        ║
║   Writes word by word (~500 words per second!) ⚡               ║
║                                                                 ║
║   "Step 1: Factor the equation..."                              ║
║   "Step 2: Set each part to zero..."                            ║
║   "Answer: x = -2  or  x = -3  ✅"                             ║
║   "💡 Quick Tip: ..."                                           ║
╚══════════════════════════╦══════════════════════════════════════╝
                           ║
                    📬 Answer travels back
                    over the internet
                    to your computer
                           ║
                           ▼
╔═════════════════════════════════════════════════════════════════╗
║  STEP 6 — FLASK RECEIVES THE ANSWER  🐍                         ║
║  "The receptionist gets the reply"                              ║
║                                                                 ║
║   📥  Receives the answer from Groq                             ║
║   📚  Saves it to conversation history                          ║
║       (so next time the AI still remembers)                     ║
║   ✂️   Keeps only the last 20 messages (to save space)          ║
║   📤  Sends the answer back to your browser                     ║
╚══════════════════════════╦══════════════════════════════════════╝
                           ║
                    📬 Answer travels back
                    to your browser
                           ║
                           ▼
╔═════════════════════════════════════════════════════════════════╗
║  STEP 7 — BROWSER MAKES IT LOOK PRETTY  🎨                      ║
║  "This is like a printer that makes your homework look neat"    ║
║                                                                 ║
║   💬  Typing dots disappear                                     ║
║   🔓  Send button turns purple again                            ║
║   📝  Markdown is rendered:                                     ║
║       **bold** becomes  bold                                    ║
║       ## heading becomes a big title                            ║
║   ✨  KaTeX renders the math:                                   ║
║       \frac{-b}{2a}  becomes  a beautiful fraction             ║
╚══════════════════════════╦══════════════════════════════════════╝
                           ║
                           ▼
╔═════════════════════════════════════════════════════════════════╗
║  STEP 8 — YOU SEE THE ANSWER!  ✅                               ║
║  "Your homework is done!"                                       ║
║                                                                 ║
║   ┌─────────────────────────────────┐                          ║
║   │  Step 1: Factor the equation    │                          ║
║   │  x² + 5x + 6 = (x+2)(x+3)     │                          ║
║   │                                 │                          ║
║   │  Step 2: Set each part to zero  │                          ║
║   │  x = -2  or  x = -3            │                          ║
║   │                                 │                          ║
║   │  💡 Quick Tip: ...              │                          ║
║   └─────────────────────────────────┘                          ║
╚═════════════════════════════════════════════════════════════════╝

⏱️  Total time for all 8 steps:  about 1-2 seconds!
```

---

## Super Simple Version 🍭

```
YOU          →      PYTHON       →      SYMPY          →      GROQ AI
"Question?"         "On it!"            "Answer is             "Let me
                                         x = -2, -3"            explain it!"

GROQ AI      →      PYTHON       →      YOU
"Here's             "Looks good,        "Got it!
 the steps!"         sending back!"      Thanks! 🎉"
```

---

## What Each Player Does 👥

```
┌──────────────────────────────────────────────────────────────┐
│  🖥️  BROWSER  (the page you see)                            │
│      • Shows the chat bubbles                                │
│      • Sends your question                                   │
│      • Makes math look beautiful                             │
├──────────────────────────────────────────────────────────────┤
│  🐍  FLASK / PYTHON  (the middleman)                         │
│      • Receives your question                                │
│      • Asks SymPy to solve it first                          │
│      • Passes SymPy's answer + your question to Groq         │
│      • Remembers your conversation                           │
│      • Sends back the reply                                  │
├──────────────────────────────────────────────────────────────┤
│  �  SYMPY  (the calculator that never makes mistakes)       │
│      • Solves equations exactly                              │
│      • Factors, simplifies, differentiates, integrates       │
│      • Gives the verified correct answer                     │
│      • Can't explain anything — just gives the answer        │
├──────────────────────────────────────────────────────────────┤
│  🤖  GROQ AI  (the tutor who explains things)                │
│      • Reads SymPy's verified answer                         │
│      • Writes a step-by-step explanation                     │
│      • Speaks like a friendly teacher                        │
└──────────────────────────────────────────────────────────────┘
```
