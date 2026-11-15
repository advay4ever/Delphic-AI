# Delphic AI Product Plan

This file tracks what Delphic AI still needs before it feels like a complete, polished learning product.

## Product Direction

Delphic AI should feel like a calm, serious, useful tutor. The goal is not to look like a toy chatbot or a generic homework solver. The product should help students understand problems step by step, check their thinking, and build confidence.

Core identity:

- Clear explanations
- Step-by-step reasoning
- Follow-up friendly tutoring
- Practice after learning
- Clean, mature visual design

## Highest Priority

### 1. Polish The Tutor Welcome Screen

Status: Done for the first polished pass.

The homepage is only the front door. The main product is the tutor workspace.

Tasks:

- Rewrite the welcome message so it matches Delphic AI's tone. Done.
- Remove wording that feels generic or too much like a normal math chatbot. Done.
- Add a small set of starter prompts. Done.
- Make the first empty-chat state feel polished. Done.
- Make the chat header, sidebar, and welcome message feel visually connected to the homepage. Done.

Suggested starter prompts:

- Solve an equation
- Explain a concept
- Check my work
- Give me practice
- Graph a function

### 2. Clean Up Branding

Status: Done for public-facing references.

Old names make the project feel unfinished.

Tasks:

- Replace public references to `LumaMath`. Done.
- Replace public references to `Math AI Tutor`. Done.
- Replace public references to `Math AI Agent` where appropriate. Done.
- Update `README.md`. Done.
- Update `docs/README.md`. No change needed.
- Update overview docs. Done.
- Make sure exported chat files say `Delphic AI`. Done.
- Keep internal file names only if changing them would create unnecessary risk. Done.

### 3. Make The Homepage Feel Finished

Status: Done for the first polished pass.

The homepage should communicate value quickly without too many buttons.

Tasks:

- Keep only one or two clear calls to action. Done.
- Make sure the logo never overlaps text. Done.
- Check desktop, tablet, and mobile widths. Done.
- Keep the full triangle logo visible. Done.
- Make sure the homepage text sounds confident but not dramatic. Done.
- Remove any future-subject promises until they are actually planned. Done.

### 4. Improve Response Quality

The AI should sound like one consistent tutor.

Tasks:

- Make the prompt enforce a calm, clear tutoring voice.
- Reduce overly long answers for simple questions.
- Make follow-up answers feel connected to previous context.
- Improve frustration handling.
- Make step-by-step mode ask exactly one question at a time.
- Avoid over-formatting responses when the student asks something simple.

## Core Features To Strengthen

### Step-by-Step Mode

Current goal:

Guide students one step at a time instead of giving the whole solution immediately.

Needed improvements:

- Make the mode more obvious in the UI. Done.
- Make the AI avoid revealing the final answer too early. Improved.
- Make the AI check the student's attempted step before moving on. Improved.
- Keep responses shorter in this mode. Improved.

### Practice Problem Generator

Current goal:

Generate a similar problem after an explanation.

Needed improvements:

- Make practice problems match the previous topic and difficulty.
- Avoid giving the solution immediately.
- Store the generated practice problem clearly in conversation context.
- Let the student submit an answer and get feedback.

### Graphing

Current goal:

Let students plot functions and understand what the graph means.

Needed improvements:

- Improve graph request detection. Improved.
- Improve error messages when graph parsing fails. Done.
- Add a clearer graph container title. Done.
- Explain key graph features after plotting. Already handled by the tutor response; keep testing.
- Test common examples:
  - `plot y = x^2`
  - `graph sin(x)`
  - `plot y = 2x + 1`
  - `graph x^2 - 4`

### Work Checking

Current goal:

Let students ask whether their answer or work is correct.

Needed improvements:

- Better detect attempted answers. Improved.
- Compare the student's answer to the previous problem. Improved.
- Explain exactly where the mistake happened. Improved.
- Avoid making the student feel dumb. Improved.
- Give the next correction step, not just the final answer. Improved.

## User Experience Improvements

### Empty State

The first tutor screen should make it obvious what to do.

Tasks:

- Add a Delphic AI welcome block.
- Add starter prompt buttons.
- Keep the text short.
- Avoid a giant list of math topics.

### Sidebar

The sidebar should feel useful, not cluttered.

Tasks:

- Improve session names.
- Show cleaner previews.
- Consider adding rename/delete session later.
- Make `New Chat`, `Download Chat`, and `Clear Chat` visually balanced.

### Theme System

The app currently has multiple themes.

Tasks:

- Keep dark as the default.
- Make light mode still readable.
- Decide whether neon mode is worth keeping.
- Make sure the logo works in all themes.

### Mobile Layout

Tasks:

- Check homepage on phone width.
- Check tutor input on phone width.
- Make sure message buttons do not crowd the chat.
- Make sure the sidebar opens and closes smoothly.

## Reliability And QA

Before showing or publishing Delphic AI, test these flows:

- Homepage loads.
- `Start learning` opens the tutor.
- New chat works.
- Clear chat works.
- Past sessions load.
- Step-by-step mode persists.
- Normal math question works.
- Follow-up question works.
- Practice button works.
- Graph request works.
- Download chat works.
- Theme menu works.
- Mobile sidebar works.

Example test prompts:

```text
Solve 2x + 3 = 11
```

```text
Why did you subtract 3?
```

```text
Give me a similar practice problem.
```

```text
Plot y = x^2 - 4
```

```text
I got x = 5. Is that right?
```

## Documentation Tasks

Tasks:

- Update the main README with Delphic AI branding.
- Add a short product description.
- Add setup instructions.
- Add screenshots later.
- Add a feature list.
- Add known limitations.
- Add a roadmap section.
- Keep planning docs organized and remove duplicate plans over time.

## Possible Future Features

These should wait until the core product feels stable.

- Difficulty selector
- Explanation style selector
- Student profile or learning memory
- Topic mastery tracking
- Saved practice sets
- Quiz mode
- Uploaded image/problem support
- Teacher/parent dashboard
- Better symbolic math verification
- More advanced graph interactions
- Shareable session links

## Design Principles

Use these to judge future changes:

- If it does not help learning, question it.
- If it makes the UI louder, simplify it.
- If it gives an answer without understanding, improve the tutoring flow.
- If it looks childish, make it calmer.
- If it looks too corporate, make it warmer.
- If a feature is unreliable, hide it until it is ready.

## Suggested Build Order

1. Polish tutor welcome screen and starter prompts.
2. Clean up Delphic AI branding across docs and UI.
3. Improve AI response style and follow-up behavior.
4. QA graphing, practice, and step-by-step mode.
5. Improve README and project documentation.
6. Add settings only after the core flow feels solid.
