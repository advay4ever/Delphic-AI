# 🤖 How to Improve the AI's Responses

> Ideas for making the AI sound more natural, helpful, and fluid.
> Ordered from easiest to hardest to implement.

---

## ✅ Status Overview

| # | Feature | Status |
|---|---|---|
| 1 | Name memory | ✅ Done |
| 2 | No tip on every message | ✅ Done |
| 3 | Length matches complexity | ✅ Done |
| 4 | Never restates the question | ✅ Done |
| 5 | Casual, friendly tone | ✅ Done |
| 6 | Follow-up question after each answer | ✅ Done |
| 7 | Question counter (encourage every 5) | ✅ Done |
| 8 | Frustration detector | ✅ Done |
| 9 | Difficulty detector (basic vs advanced) | ✅ Done |
| 10 | Topic memory (connects past topics) | ✅ Done |
| 11 | Streaming responses (word by word) | ✅ Done |
| 12 | Multi-turn graph awareness | ✅ Done |
| 13 | Confidence scoring badge | ✅ Done |
| 14 | Topic personas | ✅ Done |

**All 14 improvements complete. 🎉**

---

## 🥇 Easy Wins — Change the System Prompt Only ✅

### 1. ✅ Make the AI remember the student's name
Rule 12 in `ai/prompt.py` — AI uses the student's name occasionally when introduced.

### 2. ✅ Stop the "💡 Quick Tip" from appearing every single message
Rule 10 in `ai/prompt.py` — tip only appears when it genuinely adds value.

### 3. ✅ Shorter responses for simple questions
Rule 1 in `ai/prompt.py` — response length matched to question complexity.

### 4. ✅ Stop repeating the question back
Rule 5 in `ai/prompt.py` — AI gets straight to the answer.

### 5. ✅ More conversational tone
Rule 7 in `ai/prompt.py` — casual, warm, not textbook-style.

### 6. ✅ Ask follow-up questions more often
Rule 11 in `ai/prompt.py` — one follow-up question after every explanation.

---

## 🥈 Medium — Small Code Changes ✅

### 7. ✅ Question counter
`database.py` → `increment_question_count()` tracks questions per session.
`app.py` → `_build_messages_for_ai()` injects encouragement every 5 questions.

### 8. ✅ Frustration detector
`app.py` → detects phrases like "I don't understand", "confused", "I give up".
Injects: empathetic response + simpler re-explanation.

### 9. ✅ Difficulty detector
`app.py` → detects advanced words (integral, eigenvalue, proof) vs basic words (what is, explain).
Injects: precise language for advanced, jargon-free for basic.

### 10. ✅ Topic memory
`database.py` → `detect_topic()`, `add_topic()`, `get_topics()` — 5 topics tracked.
`app.py` → references previously covered topics in each response.

---

## 🥉 Harder — Bigger Changes ✅

### 11. ✅ Streaming responses (word by word)
- `ai/service.py` → `get_math_solution_stream()` uses `stream=True`
- `app.py` → `/stream` endpoint using Server-Sent Events (SSE)
- `script.js` → `createStreamingBubble()` + word-by-word drip queue (18ms/word)
- KaTeX re-renders on the final bubble after all words drip in

### 12. ✅ Multi-turn graph awareness
- `database.py` → `save_last_equation()` / `get_last_equation()`
- `app.py` → `/plot` uses AI to resolve follow-up requests like "make it steeper"
- If no equation found in message, AI resolves from the last plotted equation

### 13. ✅ Confidence scoring badge
- Rule 13 in `ai/prompt.py` — AI ends every response with `CONFIDENCE: High/Medium/Low`
- `script.js` → `extractConfidence()` strips the line from displayed text
- `script.js` → `createConfidenceBadge()` renders a coloured pill badge
  - ✅ Green = High, 🟡 Yellow = Medium, ⚠️ Red = Low

### 14. ✅ Topic personas
`app.py` → `_build_messages_for_ai()` detects topic and injects style instruction:
- **Algebra** → precise and methodical, every step shown
- **Geometry** → visual and descriptive, spatial analogies
- **Trigonometry** → unit circle focused, highlights patterns
- **Calculus** → conceptual first ("the why"), then rigorous
- **Statistics** → real-world examples (sports, weather, test scores)

---

## 🏆 Bonus Fix — Bulletproof LaTeX Rendering (May 2026)

Not in the original list but critical — the AI kept outputting broken LaTeX brackets.

**3-layer fix so it can never happen again:**
1. **`ai/service.py`** → `normalise_latex()` — converts all bad variants before anything is saved or sent:
   - `\[ \]` → `$$ $$`
   - `\begin{equation}` / `\begin{align}` / `\begin{aligned}` → `$$ $$`
   - Bare `[ ]` on its own line → `$$ $$`
2. **`app.py`** → streaming path normalises full assembled reply before saving to DB
3. **`script.js`** → `protectLatex()` catches all variants as a final safety net;
   DONE handler uses `renderMarkdown()` (not raw `marked.parse()`) so `protectLatex` always runs on the final render

---

> 💬 All 14 improvements are done. Next features are in [`MORE_FEATURES.md`](../planning/MORE_FEATURES.md).


These require zero code changes — just editing the text in `ai/prompt.py`.

### 1. Make the AI remember the student's name
Ask for the student's name at the start and use it throughout.
```
"If the student introduces themselves, remember their name and use it occasionally."
```

### 2. Stop the "💡 Quick Tip" from appearing every single message
Right now every response ends with a tip, which gets repetitive.
```
"Only add a 💡 Quick Tip when it genuinely adds value — not after every single response."
```

### 3. Shorter responses for simple questions
The AI gives a full essay even for "what is 2+2".
```
"Match your response length to the complexity of the question.
Simple questions = short answers. Complex problems = detailed steps."
```

### 4. Stop repeating the question back
The AI often starts with "Great question! You're asking about..." which wastes space.
```
"Never restate or paraphrase the student's question back to them. Get straight to the answer."
```

### 5. More conversational tone
The AI sounds a bit formal sometimes.
```
"Write like a friendly tutor talking to a student in person — casual, clear, and encouraging.
Avoid academic or textbook-style language."
```

### 6. Ask follow-up questions more often
After answering, the AI should check if the student understood.
```
"After explaining a concept, ask one simple follow-up question to check understanding.
Example: 'Does that make sense? Want to try a practice problem?'"
```

---

## 🥈 Medium — Small Code Changes

These need a small change in `app.py` or `ai/prompt.py`.

### 7. Track how many questions the student has asked
After every 5 questions, give the student encouragement.
- Keep a counter in the database
- Inject a "the student has asked X questions today" note into the system prompt

### 8. Detect frustration and respond with more empathy
If the student says "I don't understand" or "this is confusing", switch to a simpler explanation.
```python
if any(word in user_message.lower() for word in ["don't understand", "confused", "lost", "help"]):
    # Inject: "The student is struggling. Use a very simple analogy first."
```

### 9. Adapt to the difficulty of the question
Detect whether the question is basic or advanced and adjust tone automatically.
- "what is 2+2" → very brief, casual
- "derive the volume of a sphere" → detailed, formal

### 10. Remember what topics have been covered
Keep a list of topics discussed in the session and reference them.
```
"Earlier we talked about quadratic equations — this connects to that."
```

---

## 🥉 Harder — Bigger Changes

### 11. Streaming responses (word by word)
Right now the full response appears all at once after a delay.
Streaming would show words appearing one by one as the AI generates them — like ChatGPT.
- Requires changing `get_math_solution()` to use `stream=True`
- Requires a new `/stream` endpoint using Server-Sent Events (SSE)
- **Impact: Makes the app feel much more alive and responsive**

### 12. Multi-turn awareness for graphs
If the student asks "make it steeper" after plotting a graph, the AI should understand they mean the previous graph.
- Requires the AI to look back at previous plot requests in conversation history

### 13. Confidence scoring
After giving an answer, the AI rates its own confidence (High / Medium / Low).
- Low confidence → "I'd recommend double-checking this with a textbook"
- Helps students know when to trust the AI

### 14. Different "personas" for different topics
- Algebra → strict and precise
- Geometry → visual and descriptive  
- Statistics → real-world examples focus
- Calculus → conceptual and intuitive

---

## 🏆 Biggest Impact — Do These First

If you only do a few, these will make the biggest difference:

| # | Change | Time needed |
|---|---|---|
| 2 | Stop tip on every message | 2 min |
| 3 | Shorter answers for simple questions | 2 min |
| 4 | Stop repeating the question | 2 min |
| 11 | Streaming responses | 1–2 hours |
| 8 | Detect frustration | 30 min |

---

> 💬 Tell GitHub Copilot which one you want to implement!
