# Delphic AI Portfolio And Buyer Copy

## Product Name

Delphic AI

## One-Sentence Description

Delphic AI is a focused Math and Science learning workspace that helps students
understand a problem, practice the next step, visualize ideas, use their own class
notes, and keep a useful study record.

## Short Sales Pitch

General AI chatbots can answer school questions, but students still have to manage
graphs, practice, notes, diagrams, and saved work in separate places. Delphic turns
those pieces into one learning workflow. Students can ask follow-up questions in
simpler language, work through a problem interactively, check supported math steps,
create local 2D and 3D graphs, search their own study material, view reviewed
science diagrams, and download the conversation as an HTML study record.

Delphic is designed as a learning product, not just a chat box. Its strongest
features combine AI explanations with deterministic local tools, visible sources,
safe rendering rules, and automated testing.

## The Buyer Problem

- Students often receive an answer without understanding the next step.
- General chat tools do not organize class notes, graphs, diagrams, and practice
  into one focused workflow.
- Schools and families need clearer privacy boundaries around API keys and uploads.
- A useful education product must work on the target computers and iPads and must
  keep important math formatting readable.

## What Delphic Offers Today

- Separate Math and Science tutor workspaces.
- Streamed, multi-turn explanations with simpler-language follow-ups.
- Interactive Step-by-Step and Guided Reasoning modes.
- SymPy-backed checks for supported student math work.
- Similar practice problems and Science quizzes.
- Local Three.js 2D and 3D graphing for supported equations.
- Practice problems and feedback on a student's math work.
- Separate reusable Study Library notes and per-message photo/document uploads.
  Supported documents include TXT, MD, CSV, JSON, text-based PDF, and DOCX;
  photos need a compatible provider/model.
- Reviewed local Science diagrams with safe structured rendering.
- Saved chat sessions and browser-openable HTML transcripts.
- Light, dark, and neon themes with responsive layouts.
- Temporary API-key handling that does not put the plain key in browser storage.
- Optional native desktop OS-vault key storage in source; real vault and rebuilt
  installer validation remain before advertising it as release-tested.

## Why It Is Different

### A Learning Workflow

Delphic connects explanation, guided practice, graphing, work checking, diagrams,
and saved results. The student can move through the whole learning loop without
leaving the tutor.

### Local, Inspectable Tools

Supported graphing, math checks, note retrieval, and reviewed diagrams run through
local code with clear limits. The AI is not the only part deciding what appears.

### Student-Owned Context

Students can add their own notes and inspect excerpts retrieved for an answer.
Those excerpts are not proof the model actually used them. Cosine similarity finds related text; Delphic does not falsely present that search
as proof that every uploaded claim is correct.

### Safety By Design

The app keeps temporary API keys on the backend, validates uploaded study files,
rejects unsafe diagram data, and redirects hateful or unrelated requests back to
learning tasks.

## Evidence

- Automated Python and browser regression suites cover chat, notes, diagrams,
  settings, sessions, downloads, graph rendering, and failure recovery.
- Dated counts and scope live in [Current Progress](../planning/CURRENT_PROGRESS.md)
  and the [review record](../testing/PROJECT_CODE_REVIEW_FINDINGS.md). Re-run the
  exact release source before publishing a new count; mocked tests are not live-provider evidence.
- Long responses carry finish metadata and offer one continuation when the output
  limit is reached.
- Math and Science tabs share temporary provider settings without storing the plain
  API key in browser storage.
- The Mac build process creates and smoke-tests an unsigned `.app` and `.dmg`.

No new full release run, live-provider demonstration, or installer rebuild is
claimed by this copy. A prepared script is not a recorded video.

## Honest Current Boundaries

- AI answers can still be wrong and important answers should be checked.
- The public Mac installer still needs Apple signing, notarization, and a clean-Mac
  test before release.
- Public school deployment would need accounts, administration, policy review,
  monitoring, support, and a clear billing plan.
- The optional AI image workflow is experimental and is not part of the public
  student product yet.
- Note retrieval finds related passages; it does not prove that a student's note is
  factually correct.

## Suggested Portfolio Headline

**One workspace for understanding, practicing, visualizing, and remembering Math
and Science.**

## Suggested Call To Action

> Watch the guided demo to see Delphic solve a problem, coach the next step, render
> interactive graphs, use a student's own notes, and create a downloadable study
> record in one connected workflow.

## Product Direction

The architecture can grow beyond Math and Science by adding carefully designed
subject prompts, deterministic tools, reviewed visual systems, and subject-specific
corpora. The next commercial work should focus on signed desktop distribution,
school-ready privacy and administration, measurable learning outcomes, and pilot
feedback from real students and teachers.
