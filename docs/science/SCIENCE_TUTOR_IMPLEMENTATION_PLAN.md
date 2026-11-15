# Science Tutor Implementation Plan

This plan tracks the separate Delphic Science workspace. The science tutor should live in the same Flask app and same local port as the math tutor, but it should have its own UI, prompt, routes, and session history so the math-specific tools do not make the science experience feel awkward.

## Product Direction

Delphic should support multiple focused tutor workspaces:

- Math tutor: equations, solving, graphing, SymPy support, math practice, and math work checking.
- Science tutor: concept explanation, reasoning checks, science practice, vocabulary help, and guided conceptual learning.
- Future general tutor: a broader ChatGPT-like study workspace after the focused math and science tutors feel solid.

For now, science should not be merged into the math UI.

## Priority 1: Separate Science Workspace

Status: First pass implemented.

Tasks:

- Add a `/science` route in the same Flask app.
- Keep the app running on the same port, `5001`.
- Create a science-specific template instead of reusing the math homepage directly.
- Add a button/link from the current math/home UI to the Science tutor.
- Add a link from the Science tutor back to the Math tutor.
- Keep the visual design consistent with Delphic AI.

Acceptance checks:

- `http://127.0.0.1:5001/` opens the math tutor/home experience.
- `http://127.0.0.1:5001/science` opens the science tutor.
- No second server or second port is required.

## Priority 2: Science-Specific Prompt

Status: First pass implemented.

Tasks:

- Keep the math tutor prompt math-focused.
- Add a separate science tutor system prompt.
- Cover core school science:
  - Biology
  - Chemistry
  - Physics
  - Earth Science
  - Environmental Science
- Make the science tutor conceptual first:
  - explain ideas clearly
  - check reasoning
  - define vocabulary
  - generate practice questions
  - explain formulas when useful
- Do not add science calculators or lab tools yet.

Acceptance checks:

- Science answers do not mention graphing unless relevant.
- Science answers do not behave like equation-solving responses.
- Science answers end with the same `CONFIDENCE:` format as math answers.

## Priority 3: Separate Science Routes And Sessions

Status: First pass implemented.

Tasks:

- Add science endpoints:
  - `/science/stream`
  - `/science/ask`
  - `/science/history`
  - `/science/sessions`
  - `/science/sessions/new`
  - `/science/sessions/switch`
  - `/science/clear`
- Keep science history separate from math history.
- Reuse the existing database table instead of adding a new database for v1.
- Prefix science session IDs so math and science sessions can be filtered apart.

Acceptance checks:

- Math sessions do not show inside the science sidebar.
- Science sessions do not show inside the math sidebar.
- Clearing science chat does not clear math chat.

## Priority 4: Science UI Copy

Status: First pass implemented.

Tasks:

- Use science-specific header text.
- Use science-specific empty state copy.
- Use science-specific starter prompts:
  - `Explain photosynthesis in simple words`
  - `What is Newton's second law?`
  - `Why do atoms form bonds?`
  - `Check my reasoning: heavier objects fall faster because gravity pulls harder`
  - `Give me a practice question about ecosystems`
- Change `Step-by-Step Mode` wording to `Guided Reasoning Mode` in the science workspace.
- Keep the science input placeholder science-focused.

Acceptance checks:

- The science page does not feel like a graphing/equation workspace.
- The user can tell they are in Delphic Science from the header and starter prompts.

## Priority 5: Disable Math-Only Tools In Science

Status: First pass implemented.

Tasks:

- Do not call `/plot` from the science page.
- Do not run SymPy result injection for science responses.
- Do not show graph starter prompts in the science UI.
- Keep KaTeX support because science may still use formulas like \( F = ma \).

Acceptance checks:

- Asking a science prompt does not trigger graphing.
- Asking for science practice does not create a math-style problem unless the topic naturally uses formulas.

## Priority 6: Tests And QA

Status: Automated checks pass; live AI science QA still needed.

Current checks:

- Python tests pass.
- Python compile check passes.
- JavaScript syntax check passes.
- Math page smoke test passes.
- Science page smoke test passes.
- Science history endpoint smoke test passes.
- Route test for `/science` passes.
- Science session filtering tests pass.
- Science prompt wiring tests for `/science/ask` and `/science/stream` pass.

Manual QA still needed:

- `Explain photosynthesis in simple words`
- `What is Newton's second law?`
- `Why do atoms form bonds?`
- `Give me a practice question about ecosystems`
- `Check my reasoning: heavier objects fall faster because gravity pulls harder`

## Later Science UI Ideas

These should wait until the basic Science tutor feels stable:

- Subject tabs for Biology, Chemistry, Physics, Earth Science, and Environmental Science.
- Formula cards for physics and chemistry.
- Vocabulary review.
- Lab report helper.
- Diagram or concept-map support.
- Chemistry equation balancing.
- Physics unit/formula helper.
- A future general Delphic tutor that routes between math, science, and other study help.
