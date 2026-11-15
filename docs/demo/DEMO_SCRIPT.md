# Delphic AI Buyer Demo Script

## Goal

Show a school, tutoring company, product manager, or possible partner why Delphic
is useful. The demo should prove that the product helps a student understand,
practice, visualize, and keep their learning in one place.

Target length: 4 to 5 minutes.

## Main Message

> Delphic AI is a focused Math and Science learning workspace. It combines guided
> tutoring, checked math tools, interactive graphs, science
> diagrams, and downloadable study records without making students jump between
> several apps.

Do not call Delphic perfect or claim that it replaces a teacher. The strongest
sales pitch is a real workflow that works from beginning to end.

## Before Recording

1. Run the final test checklist.
2. Start Delphic at `http://127.0.0.1:5001`.
3. Use a separate demo API key with a spending limit.
4. Configure the provider before recording so the secret key never appears.
5. Start with a clean Math chat and a clean Science chat.
6. Use a 1440 by 900 browser window at 100 percent zoom.
7. Turn off notifications and close personal tabs.

## Timed Walkthrough

### 0:00 to 0:25 - State The Student Problem

Show the Delphic home page.

Say:

> Students often use one tool for explanations, another for graphs, and another
> for practice. Delphic brings those jobs into one focused learning workspace
> for Math and Science.

Use the Math tutor entry point shown by the current Home page.

### 0:25 to 1:05 - Show A Clear Math Explanation

Ask:

```text
Solve 2x + 3 = 11 and explain why each step is allowed.
```

Point out the readable math formatting and streamed response.

Then ask:

```text
Explain the subtraction step in 5th grade language.
```

Say:

> Delphic keeps the conversation context, so a student can ask a short follow-up
> instead of starting the lesson again.

### 1:05 to 1:40 - Show Guided Learning

Start a new chat, turn on **Guide me step by step** (the existing Step-by-Step Mode), and ask:

```text
Solve 3x + 5 = 20.
```

Answer the first tutor question yourself:

```text
Subtract 5 from both sides.
```

Say:

> Guided mode asks for the student's next step instead of immediately giving away
> the entire solution.

### 1:40 to 2:20 - Show Local Graphing

Turn off **Guide me step by step** and ask:

```text
Graph y = sin(x).
```

Zoom and pan the 2D graph. Then ask:

```text
Graph z = x^2 - y^2.
```

Rotate and zoom the 3D graph.

Say:

> Delphic renders supported 2D and 3D graphs locally with Three.js. The desktop
> app does not need a paid Desmos graphing request.

### 2:20 to 3:10 - Show Practice And Work Checking

Click **Practice Similar Problem** on a math reply. Show that the tutor gives
a new problem without immediately revealing the answer. Then ask:

```text
Check my work: for 2x + 3 = 11, I subtracted 3 to get 2x = 8, then divided by 2 to get x = 4.
```

Say:

> Students can practice a related problem and ask for feedback on their work,
> instead of only reading completed solutions.

### 3:10 to 3:45 - Show A Safe Science Diagram

Switch to the Science tutor and ask:

```text
Draw a labeled plant cell diagram and explain the job of each shown part.
```

Point out the labels and written explanation.

Say:

> Supported diagrams use checked local templates instead of placing unchecked
> AI-made webpage code into the app.

### 3:45 to 4:15 - Show Product Polish

Switch between light, dark, and neon themes. Open the chat menu and download the
current chat as HTML.

Say:

> Chats, equations, supported diagrams, and generated study content can be kept as
> a browser-openable study record.

### 4:15 to 4:35 - Close With The Product Value

Return to the home page.

Say:

> Delphic is more than a general chatbot with a school label. It is a learning
> workflow: ask, reason, practice, visualize, and keep the
> result. That is the foundation we can expand into more subjects and school
> programs.

## Backup Prompts

Use these only if a provider response is slow or a live prompt behaves differently
than expected:

```text
Find the derivative of x^3 + 2x.
Graph x^2 / 9 + y^2 / 4 = 1.
Draw a force diagram for a box resting on a table.
Explain photosynthesis in simple words.
```

## Demo Rules

- Show only features that work in the current build.
- Never show an API key, `.env`, private note, username, or personal file path.
- Do not use experimental image generation in the main buyer demo yet.
- Keep one backup screen recording in case a live AI provider is unavailable.
- If the AI makes a mistake, say so honestly and show Delphic's correction or
  work-checking tools instead of hiding the limitation.
