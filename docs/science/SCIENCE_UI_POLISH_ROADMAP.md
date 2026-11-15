# Science UI Polish Roadmap

This roadmap is for making Delphic Science feel like its own focused science learning workspace, not just the math tutor with different text. Work through the priorities in order.

## Priority 1: Make The Science Workspace Visibly Distinct

Goal: Students should immediately know they are in the Science tutor.

Status: First polish pass implemented.

Tasks:

- Keep the Delphic brand consistent, but make the science workspace visually distinct from math.
- Use the title `Delphic Science` in the header and sidebar.
- Add a subtle science-specific accent treatment without making the UI look playful or childish.
- Avoid graph/equation-first visual cues on the science page.
- Keep the page calm, serious, and study-focused.

Acceptance checks:

- The science page does not feel like a math graphing workspace.
- The science page still feels like part of Delphic AI.
- The UI remains readable in dark, light, and neon themes.

## Priority 2: Improve The Science Empty State

Goal: The empty state should guide science learners toward useful first actions.

Status: First polish pass implemented.

Tasks:

- Rewrite the welcome text so it is science-specific and concise.
- Emphasize concepts, reasoning, vocabulary, practice, and checking explanations.
- Avoid long lists of science subjects in the main welcome copy.
- Keep starter prompts visible without crowding the message card.
- Make the empty state feel polished on mobile.

Acceptance checks:

- A student knows what to ask first.
- The copy does not sound like a generic chatbot.
- Text does not overflow or crowd on mobile.

## Priority 3: Organize Starter Prompts By Science Use Case

Goal: Starter prompts should represent real science workflows.

Status: First polish pass implemented.

Tasks:

- Keep 4-5 starter prompts maximum.
- Cover these use cases:
  - explain a concept
  - check reasoning
  - give practice
  - explain vocabulary
  - connect a formula to intuition
- Use prompts from different science areas:
  - Biology
  - Chemistry
  - Physics
  - Earth or Environmental Science
- Avoid making the first screen feel like a subject menu.

Suggested starter prompts:

- `Explain photosynthesis in simple words`
- `What does erosion mean in Earth science?`
- `What does F = ma mean in real life?`
- `Check my reasoning: a chemical reaction creates new atoms`
- `Give me a practice question about ecosystems`

Acceptance checks:

- Starter prompts feel useful and varied.
- No starter prompt triggers graphing or math-only behavior.
- Prompts fit cleanly on desktop and mobile.

## Priority 4: Refine Science Controls

Goal: Controls should match science learning instead of math solving.

Status: First polish pass implemented.

Tasks:

- Keep `Guided Reasoning Mode` instead of `Step-by-Step Mode`.
- Rename the practice button to science-specific wording, such as `Practice This Concept`.
- Make sure copy buttons and transcript export still work.
- Keep the theme menu and session controls consistent with math.
- Do not add subject tabs yet unless the current page feels too broad after QA.

Acceptance checks:

- Controls feel natural for science.
- Math-only labels do not appear in the science workspace.
- Existing shared controls still behave correctly.

## Priority 5: Improve Navigation Between Tutors

Goal: Math and science should feel like sibling workspaces.

Status: First polish pass implemented.

Tasks:

- Keep a clear `Science tutor` button on the math/home page.
- Keep a clear `Math tutor` link in the science workspace.
- Make switching work without changing ports.
- Avoid forcing users through a mode picker before asking a question.
- Consider adding a simple workspace label in each page header.

Acceptance checks:

- Users can move between math and science in one click.
- The active workspace is obvious.
- The navigation does not crowd the header on mobile.

## Priority 6: Add Science-Specific Visual Structure Later

Goal: Add richer science UI only after the basic tutor feels good.

Possible later additions:

- Subject chips for Biology, Chemistry, Physics, Earth Science, and Environmental Science.
- Formula cards for physics and chemistry.
- Vocabulary review cards.
- Lab helper section.
- Diagram or concept-map area.
- Saved science practice sets.

Do not build these until:

- live science QA feels solid
- the simple science chat UI feels stable
- we know which science workflows students actually use

## Priority 7: QA The Polished UI

Goal: Confirm the science UI is polished and does not break shared chat behavior.

Status: First QA pass completed on June 25, 2026.

Test flows:

- Open `/science`.
- Send a science concept prompt.
- Use `Guided Reasoning Mode`.
- Click `Practice This Concept`.
- Download a science chat.
- Clear science chat.
- Switch back to the math tutor.
- Confirm math graphing still works on `/`.

Checks:

- No overlapping text.
- No math-only labels in science UI.
- No graph UI appears in science unless added intentionally later.
- Mobile layout remains usable.
- Tests still pass.
