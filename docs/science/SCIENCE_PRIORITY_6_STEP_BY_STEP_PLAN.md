# Science Priority 6 Step-by-Step Plan

This plan explains how to approach Priority 6: richer science-specific UI. The goal is to add useful structure without making the Science tutor feel crowded or overbuilt.

## Current Recommendation

Do not build every Priority 6 idea at once.

Start with one small feature, test it, then decide what should come next. The safest first feature is:

**Subject chips for Biology, Chemistry, Physics, Earth Science, and Environmental Science.**

Subject chips are low-risk because they help students start a science question without changing the core chat behavior.

## Step 1: Confirm The Basic Science Tutor Is Stable

Before adding new UI, confirm these flows still feel solid:

- Open `/science`.
- Ask a normal science concept question.
- Use `Guided Reasoning Mode`.
- Click `Practice This Concept`.
- Use `Download Transcript`.
- Clear the chat.
- Switch between Math and Science.
- Confirm graph UI does not appear in Science.

Move forward only if the simple Science tutor feels stable.

Status: Step 1 stability QA completed on June 26, 2026. Normal concept answers, Guided Reasoning Mode, Practice This Concept, transcript/history, clear chat, tutor navigation, Science graph redirection, and the Math graph endpoint were checked. Guided mode needed one prompt tightening so it ends by asking the student one next question.

## Step 2: Collect Real Science Use Cases

Use the Science tutor for real questions before building new UI.

Track which kind of help is most common:

- Explaining a concept.
- Defining vocabulary.
- Checking reasoning.
- Connecting a formula to intuition.
- Getting practice questions.
- Understanding a system or cycle.
- Preparing for a quiz or test.

The first Priority 6 feature should support the most common use case.

## Step 3: Choose One Feature To Build First

Pick only one:

1. Subject chips.
2. Formula cards.
3. Vocabulary review cards.
4. Lab helper section.
5. Diagram or concept-map area.
6. Saved science practice sets.

Recommended first choice: **Subject chips**.

## Step 4: Build Subject Chips First

Add five simple chips near the Science input or empty state:

- Biology
- Chemistry
- Physics
- Earth Science
- Environmental Science

When clicked, a chip should help shape the next question, not force a separate mode.

Example behavior:

- Clicking `Biology` could place `Ask a biology question...` guidance near the input.
- Clicking `Physics` could help starter prompts lean toward formulas, motion, force, and energy.
- Clicking `Chemistry` could help starter prompts lean toward atoms, bonding, reactions, and particles.

Keep the chat experience the same.

## Step 5: Keep The UI Quiet

The Science tutor should still feel calm and study-focused.

Rules:

- Do not add tabs yet.
- Do not add a separate subject dashboard yet.
- Do not add cards inside cards.
- Do not let chips crowd the mobile layout.
- Do not make the Science page feel like a subject menu.

## Step 6: Test Subject Chips

Acceptance checks:

- Chips fit on desktop and mobile.
- Chips do not overlap the input or starter prompts.
- Clicking a chip feels helpful.
- Students can ignore the chips and still ask any science question.
- Math tutor UI is not changed.
- Existing Science controls still work.

Run:

```bash
venv/bin/python -m pytest
node --check static/script.js
git diff --check
```

## Step 7: Decide The Second Feature

After subject chips are tested, choose the next feature based on what feels missing.

Good order:

1. Subject chips.
2. Vocabulary review cards.
3. Formula cards.
4. Lab helper section.
5. Diagram or concept-map area.
6. Saved science practice sets.

Do not build saved practice sets early. They require more session and storage design.

## Step 8: Update The Roadmap

After the first Priority 6 feature is implemented:

- Add a status note under Priority 6 in `SCIENCE_UI_POLISH_ROADMAP.md`.
- Record which feature was built first.
- Record what should be tested next.

## First Build Scope

The first Priority 6 implementation should only include:

- Subject chips.
- Light styling for the chips.
- A small amount of JavaScript to apply the selected subject.
- Tests that confirm the Science page still renders and the controls remain present.

Avoid building formula cards, vocab cards, lab helper, diagrams, or saved practice sets in the first pass.
