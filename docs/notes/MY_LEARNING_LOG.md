# 📚 Things I Learned — Delphic AI Project

> This is my personal learning log from building Delphic AI.
> I'll keep adding to this as I learn more.

---

## 📋 Table of Contents

1. [AI Temperature](#ai-temperature)
2. [AI App Structure vs. Material](#ai-app-structure-vs-material)
3. [What is an API and How Does it Share Data?](#what-is-an-api-and-how-does-it-share-data)
4. [What is LaTeX?](#what-is-latex)
5. [What is KaTeX?](#what-is-katex)
6. [SymPy — How the Calculator and the Teacher Work Together](#sympy--how-the-calculator-and-the-teacher-work-together)
7. [AI vs LLM — What's the Difference?](#ai-vs-llm--whats-the-difference)
8. [Conflicting AI Instructions — How to Override Them](#conflicting-ai-instructions--how-to-override-them)

---

## AI Temperature

Temperature is a number between `0` and `2` that controls how **creative or random** the AI is.

### Simple Analogy
Think of it like a **volume knob**:
- Turn it down → AI is quiet, careful, and accurate
- Turn it up → AI gets loud, creative, and unpredictable

---

### Full Temperature Scale

| Temperature | AI Behaviour | Good for Math? |
|---|---|---|
| `0.0` | Robotic. Same answer every single time. | ⚠️ Too stiff |
| `0.1` | Almost identical to 0.0. Tiny bit more natural. | ✅ Works fine |
| `0.2` | Slightly more natural. Still very accurate. | ✅ Works fine |
| **`0.3`** ✅ | **Accurate + sounds like a real human tutor.** | ✅ Best sweet spot |
| `0.4` | Still good. Occasionally rephrases things. | ✅ Still fine |
| `0.5` | More varied answers. Sometimes adds extra examples. | ⚠️ Getting loose |
| `0.6` | Starts taking small creative liberties. | ⚠️ Risky for math |
| `0.7` | ChatGPT's default. Great for chat, risky for math. | ❌ Too creative |
| `0.8` | Might reframe problems in unexpected ways. | ❌ Not reliable |
| `0.9` | Answers feel "off". Might skip steps or make errors. | ❌ Avoid |
| `1.0` | Very unpredictable. Sometimes brilliant, sometimes wrong. | ❌ Avoid |
| `1.5` | Weird, nonsensical explanations. | ❌ Don't use |
| `2.0` | Completely random. Basically broken. | ❌ Never |

---

### The Simple Rule
> **Lower = more predictable and accurate**
> **Higher = more creative and risky**

---

### Does All Math AI Use `0.3`?

**No.** Different apps choose different temperatures based on their needs:

| Tool | Approx. Temperature | Why |
|---|---|---|
| Wolfram Alpha | `0.0` | Pure math engine, no AI creativity |
| Khan Academy Khanmigo | `~0.2–0.4` | Needs accuracy but also warmth |
| ChatGPT (default) | `0.7` | General purpose, not math-specific |
| GitHub Copilot | `~0.2` | Code needs to be exact, like math |
| Our Math Tutor app | `0.3` | Accurate but still friendly |

---

### How to Choose a Temperature

Ask yourself 3 questions:

1. **How wrong can the AI afford to be?**
   - Math → very wrong = bad → use **low** temp
   - Creative writing → wrong is fine → use **high** temp

2. **Does the answer need to be the same every time?**
   - Calculator-like tool → `0.0`
   - Friendly tutor → `0.2–0.4`

3. **Does it need to feel human?**
   - Robotic tool → `0.0`
   - Friendly tutor → `0.3`
   - Casual chatbot → `0.7`

---

### Where is it set in this project?

Temperature is set in **`ai/service.py`**. This is the only file that talks to the Groq API, so it's the only place temperature matters.

There are actually **two places** in that file where temperature is set:

**1. Main chat function** — uses `0.3` (friendly tutor tone):
```python
# ai/service.py — get_math_solution()
response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=messages,
    temperature=0.3,      # ← friendly but accurate
    max_tokens=2048,
)
```

**2. Equation extractor function** — uses `0.0` (robot mode, must be exact):
```python
# ai/service.py — extract_equation()
response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[...],
    temperature=0.0,      # ← must output exact equation, no creativity
    max_tokens=100,
)
```

> **Why `0.0` for equation extraction?**
> When the app needs to pull an equation out of a word problem (e.g. "I have 12 apples..."), it must output something exact like `12 - 5`. Any creativity here would break the SymPy solver.

---

## AI App Structure vs. Material

Every AI app in the world — ChatGPT, Copilot, our math tutor, anything — follows the **exact same structure**. Only the materials (the specific tools and services) change.

### The Blueprint Analogy

Think of it like building a house. Every house has:
- A foundation
- Walls
- A roof
- Doors

That's the **structure** — always the same no matter what house you build.

But one house might use brick walls, another wooden walls. One has a red door, another a blue door. That's the **material** — different every time.

AI apps work the same way.

### The Structure (Always the Same)

```
User → App → AI API → App → User sees answer
```

That's it. Every AI app on earth follows this pattern:
1. User types something
2. App packages it up and sends it to an AI
3. AI thinks and writes back
4. App receives the answer and shows it to the user

### The Material (Changes Per App)

| Structure piece | Our App | ChatGPT | GitHub Copilot |
|----------------|---------|---------|----------------|
| Backend | Flask (Python) | OpenAI's servers | Microsoft's servers |
| AI model | GPT-OSS 120B (Groq) | GPT-4o | GPT-4o |
| Frontend | Our chat UI | Their chat UI | VS Code editor |
| Display | KaTeX for math | Plain text | Code highlighting |

### The Key Insight

> **The structure is the blueprint. The material is what you build it with.**

If I wanted to build a recipe AI, or a poetry AI, or a coding AI — I'd keep the exact same structure. I'd just swap out:
- The system prompt (instead of "math tutor", say "recipe chef")
- The AI model (maybe a different one)
- The display (instead of KaTeX, maybe show images)

This is why learning one AI app teaches you how ALL AI apps work.

---

## What is an API and How Does it Share Data?

### What is an API?

API stands for **Application Programming Interface**. That's a mouthful, so here's the simple version:

An API is a **door that a company builds** so that your app can use their powerful service — without you needing to build that service yourself.

### The Restaurant Analogy 🍽️

Imagine a super fancy restaurant:
- **You** = your app (the customer)
- **The kitchen** = Groq's giant AI (the powerful service)
- **The waiter** = the API

You can't walk into the kitchen yourself — it's private. So the restaurant gives you a **menu** (the API rules) and a **waiter** (the API itself). You tell the waiter what you want, the waiter goes to the kitchen, and brings back your food.

The menu says: *"To order, write down the dish name and your table number."* That's exactly what an API does — it gives you a list of rules for how to ask for something.

### Why Not Just Do It Yourself?

Because building a giant AI like GPT-OSS 120B would take:
- 🏢 Thousands of computers
- 💰 Billions of dollars
- 👨‍💻 Thousands of engineers
- 📅 Years of time

Instead, Groq built it — and we just use their API to tap into it with a few lines of code.

### APIs Are Everywhere 🌍

| App | What it does | API it uses |
|-----|-------------|-------------|
| Google Maps in Uber | Shows the map | Google Maps API |
| "Login with Google" | Lets you sign in | Google Auth API |
| Weather app | Shows the forecast | Weather API |
| Our math tutor | Solves math | Groq AI API |

---

### How Does an API Share Data?

When our app and Groq talk to each other, they use two things: a **format** (JSON) and a **road** (HTTP).

#### The Format: JSON 📦

JSON is just **organized text** with labels and values — like a form. For example:

```json
{
  "model": "openai/gpt-oss-120b",
  "messages": [
    { "role": "user", "content": "Solve x² + 5x + 6 = 0" }
  ]
}
```

Every piece of data has a **label** (like `"content"`) and a **value** (like `"Solve x² + 5x + 6 = 0"`). Both sides — our app and Groq — agree to use this format so neither gets confused.

#### The Road: HTTP 🛣️

HTTP is the same system your browser uses to load any website. It's the postal service of the internet — it carries messages from one computer to another. There are two directions:

| Direction | Name | Like... |
|-----------|------|---------|
| Our app → Groq | **Request** | Mailing a letter |
| Groq → Our app | **Response** | Getting a letter back |

#### What We Send to Groq 📤

```
POST https://api.groq.com/openai/v1/chat/completions

Headers:
  Authorization: Bearer gsk-your-key-here   ← our ID card (API key)
  Content-Type: application/json          ← "I'm sending JSON"

Body:
{
  "model": "openai/gpt-oss-120b",
  "messages": [
    { "role": "system", "content": "You are a math tutor..." },
    { "role": "user",   "content": "Solve x² + 5x + 6 = 0" }
  ],
  "temperature": 0.3,
  "max_tokens": 2048
}
```

#### What Groq Sends Back 📥

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Step 1: Factor the equation..."
      }
    }
  ]
}
```

#### The API Key 🔑

The API key (`gsk-your-key-here`) is like a **library card**. It proves to Groq that we are allowed to use their service. Without it, Groq would reject our request. This is why the key is kept secret in the `.env` file and never shared.

### The Full Data Journey 🚀

```
Our question (Python string)
        ↓
  Packed into JSON
        ↓
  Sent over HTTP (the internet)
        ↓
  Groq reads the JSON
        ↓
  AI thinks, writes an answer
        ↓
  Groq packs answer into JSON
        ↓
  Sent back over HTTP
        ↓
  Our Python code unpacks it
        ↓
  Sent to browser as JSON
        ↓
  JavaScript displays it as text
```

Every single step is just **text being passed around in an agreed format**. That's it.

### Where This Happens in Our Code

In `ai/service.py`, the OpenAI Python library handles all the packing, sending, and unpacking automatically:

```python
# This one line does ALL the sending and receiving:
response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=messages
)

# This digs into the JSON response to get just the text:
return response.choices[0].message.content
```

---

## What is LaTeX?

LaTeX (say it like "LAH-tech") is a **language for writing beautiful math**. It's not a file, not a program, not something you install — it's just a way of writing.

### The Problem It Solves

Try typing the quadratic formula on a computer:

```
x = (-b +/- sqrt(b^2 - 4ac)) / 2a
```

That's ugly and hard to read. It doesn't look like real math.

LaTeX fixes this by giving you **commands** that describe what the math should look like:

```
\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
```

### How It Works

LaTeX uses backslash commands to describe math symbols:

| You write... | It means... |
|-------------|------------|
| `\frac{1}{2}` | A fraction: 1 over 2 |
| `x^{2}` | x with a tiny superscript 2 |
| `\sqrt{9}` | A square root sign around 9 |
| `\pm` | The ± symbol |
| `\int` | An integral sign ∫ |

### The Recipe Analogy

LaTeX is like a **recipe** 📝. It describes what the dish should look like, but it doesn't cook anything. You need a chef (a renderer like KaTeX) to actually follow the recipe and make the dish.

### Where Does LaTeX Live in Our App?

LaTeX doesn't have its own file. It lives **inside the AI's response text**. When Groq sends back an answer, it uses LaTeX commands like `\frac{1}{2}` to describe the math. It's just text — nothing more.

### Who Uses LaTeX?

Scientists, mathematicians, and professors have been using LaTeX for over 40 years to write textbooks, research papers, and homework assignments. Every math textbook you've ever read was probably made with LaTeX.

---

## What is KaTeX?

KaTeX (say it like "KAY-tech") is a **tool that reads LaTeX and draws beautiful math on a web page**. It was made by the people at Khan Academy (the free homework help website).

### The Problem It Solves

Web browsers (Chrome, Safari, Firefox) don't understand LaTeX. If you put `\frac{1}{2}` on a webpage, the browser just shows it as ugly text: `\frac{1}{2}`. It has no idea what to do with it.

KaTeX is a translator that says: *"Oh! I see some LaTeX code here. Let me turn that into a beautiful picture!"*

### How It Works in Our App

1. The AI writes an answer with LaTeX commands (e.g. `\frac{1}{2}`)
2. The answer arrives in the browser as plain text
3. KaTeX scans the text looking for math markers (`\( \)` or `$$ $$`)
4. When it finds them, it swaps the ugly code for beautiful rendered symbols
5. You see gorgeous math instead of raw commands

### KaTeX is Always Watching

KaTeX runs silently in the background **every time** the AI sends a response. If it finds math markers, it renders them. If there's no math, it does nothing. You never notice it — like a spell-checker that only highlights when it spots something.

### Where Does KaTeX Live in Our App?

KaTeX is **not a file in our project**. It's loaded from the internet (a CDN) in `index.html`:

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex/dist/katex.min.js"></script>
```

Then `script.js` has the code that tells KaTeX when to scan and render:
- `protectLatex()` — saves math blocks before Markdown runs
- `restoreLatex()` — puts them back after
- `renderMathInElement()` — tells KaTeX to draw the math

### LaTeX vs. KaTeX — The Short Version

| | LaTeX | KaTeX |
|--|-------|-------|
| What it is | A language (like English) | A translator (like Google Translate) |
| What it does | Describes what math should look like | Actually draws it on screen |
| Where it lives | Inside the AI's response text | Loaded from the internet into your browser |
| Has its own file? | No — it's just text | No — loaded via CDN |
| Analogy | The recipe 📝 | The chef who follows the recipe 👨‍🍳 |

---

## SymPy — How the Calculator and the Teacher Work Together

### What is SymPy?

SymPy is a Python library that does **real math**. It's like a calculator, but way more powerful. It can solve equations, factor, simplify, find derivatives, and find integrals. And it **never makes mistakes** — because it follows the actual rules of math, just like a calculator does.

### The Problem Before SymPy

Before we added SymPy, our app only had the AI (Groq). When a student asked "Solve x² + 5x + 6 = 0", the AI would try to solve it by itself. The AI is really smart, but it doesn't actually "do math" — it **predicts** what the answer should look like, word by word. Most of the time it gets it right. But sometimes it makes silly mistakes, like saying x = -1 instead of x = -2.

That's like having a teacher who doesn't have a calculator. The teacher is smart, but sometimes makes a small mistake when doing the math in their head.

### The Fix — Give the Teacher a Calculator

Now, before the AI answers, we run the question through SymPy first. SymPy solves it instantly and gives us the **exact correct answer**. Then we pass that answer to the AI and say: "Here's the right answer. Now explain it step by step."

### The Story Version 🍎

Imagine a student asks: "What is 2 + 2?"

**Before (AI alone):**
- Teacher thinks really hard
- Teacher says: "I think it's 4!"
- Teacher is usually right, but sometimes tired and says "5"

**After (SymPy + AI together):**
- Calculator on the desk says: "The answer is 4."
- Teacher reads the calculator
- Teacher says: "Great question! Take 2 apples, add 2 more. Count them: 1, 2, 3, 4. The answer is **4**!"
- Teacher can NEVER get the wrong number now

### How They Talk to Each Other

SymPy and the AI don't actually talk to each other directly. They don't even know the other exists. `app.py` is the **middleman** — like a person passing notes between two classmates:

```
Student asks a question
        ↓
app.py receives it
        ↓
app.py asks SymPy: "Can you solve this?"
        ↓
SymPy says: "Yes! x = -2 and x = -3"
        ↓
app.py tells the AI: "The student asked this question.
  SymPy already solved it: x = -2 and x = -3.
  Now explain it step by step."
        ↓
AI writes a beautiful explanation
        ↓
app.py sends it to the student
```

### What Each One Does

| | SymPy (the calculator) | AI / Groq (the teacher) |
|--|----------------------|------------------------|
| What it does | Gets the right answer | Explains how to get there |
| Can it be wrong? | Never | Sometimes |
| Can it explain? | No — just gives the number | Yes — writes like a tutor |
| Can it understand "what is algebra?" | No | Yes |
| Speed | Instant | 1-2 seconds |
| Where it runs | On your computer | On the internet (Groq's servers) |

### When SymPy Helps and When It Doesn't

SymPy only helps with **specific math problems** — things it can actually calculate:

| Question | SymPy helps? | Why? |
|----------|-------------|------|
| "Solve x² + 5x + 6 = 0" | ✅ Yes | It's a solvable equation |
| "Factor x² + 5x + 6" | ✅ Yes | It can factor polynomials |
| "Derivative of 3x² + 2x" | ✅ Yes | It can do calculus |
| "Integrate x²" | ✅ Yes | It can do integrals |
| "Simplify (x²+2x+1)/(x+1)" | ✅ Yes | It can simplify expressions |
| "What is algebra?" | ❌ No | That's a question about a concept, not a calculation |
| "Explain the quadratic formula" | ❌ No | That needs a teacher, not a calculator |

When SymPy can't help, the AI handles it alone — just like before.

### Where It Lives in Our Code

- **`ai/math_tools.py`** — The 5 SymPy functions (solve, factor, simplify, differentiate, integrate)
- **`ai/detector.py`** — The "detective" that reads your question and figures out which SymPy function to call
- **`app.py`** — The middleman that connects SymPy's answer to the AI

### The One-Sentence Version

> We gave the teacher a calculator, so now the teacher always gets the right answer AND explains it clearly.

---

## AI vs LLM — What's the Difference?

**AI** is the big umbrella term. **LLM** is one specific type of AI.

Not all AI is an LLM — but all LLMs are AI.

### The Family Tree

```
AI  (the big umbrella)
│
├── Machine Learning
│     ├── Neural Networks
│     │     ├── LLMs  ← GPT, Claude, Gemini (what this app uses)
│     │     └── Image AI (DALL·E, Stable Diffusion)
│     └── Other models (spam filters, recommendation engines)
│
├── Rule-based systems (chess engines, calculators)
└── Symbolic Math (SymPy ← also in this app, NOT an LLM)
```

### What is an LLM specifically?

**LLM = Large Language Model.**

It's a model trained on billions of pages of text (books, websites, Wikipedia, code) that learned to understand and generate human language. GPT, Claude, Gemini, and LLaMA are all LLMs.

### What this app uses

| Part | AI? | LLM? |
|---|---|---|
| Groq / GPT model | ✅ | ✅ |
| SymPy | ✅ (sort of) | ❌ |
| Desmos graphs | ❌ | ❌ |

### The hybrid architecture

This app is a **hybrid** — it uses:
- The **LLM** (Groq) for understanding questions and explaining answers in plain English
- **SymPy** for 100% accurate symbolic math (not AI guessing — real algebra)

This is smarter than using just an LLM alone, because LLMs can make arithmetic mistakes but SymPy never does.

---

## Conflicting AI Instructions — How to Override Them

When you give an AI multiple instructions, sometimes they **contradict each other**. The AI has to pick one — and it doesn't always pick the right one.

### The Bug We Hit

The main system prompt had this rule:
> **Rule #1: ALWAYS provide step-by-step solutions**

Then when Hint Mode was turned on, we added:
> *"Give only ONE small hint"*

The AI ignored the hint instruction and gave the full answer anyway — because Rule #1 felt more authoritative to it.

### Why This Happens

LLMs don't have strict logic like `if hint_mode: skip rule 1`. They weigh all instructions together and pick the most "confident-sounding" one. A permanent rule set at the start of the conversation feels stronger than a new instruction added later.

### The Fix — Explicit Override Language

To make the AI follow the new instruction, you have to **explicitly tell it to override the old one**:

**Before (weak — AI ignores it):**
```python
"The student is in HINT MODE. Do NOT give the full solution..."
```

**After (strong — AI obeys it):**
```python
"⚠️ OVERRIDE — HINT MODE IS ACTIVE. This overrides all other instructions.
You MUST NOT give the full solution, the final answer, or any step-by-step working..."
```

### The Key Words That Work

| Word/Phrase | Why it helps |
|---|---|
| `OVERRIDE` | Signals this beats earlier rules |
| `overrides all other instructions` | Leaves no ambiguity |
| `MUST NOT` (in caps) | Stronger than "do not" |
| `⚠️` emoji | Draws attention to the rule |

### The Lesson

> When giving an AI conflicting instructions, **the later instruction needs to explicitly say it overrides the earlier one** — otherwise the AI will follow whichever sounds most confident.

---

<!-- Add new topics below this line -->
