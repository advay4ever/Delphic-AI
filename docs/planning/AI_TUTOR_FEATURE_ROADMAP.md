# AI Tutor Feature Roadmap

This roadmap lists the next AI tutor features to build, in the order they should be added.

## 1. Step-by-Step Mode

### Goal

Make the tutor guide the student one step at a time instead of always giving the full answer immediately.

### How It Should Work

When a student asks a math question, the app can offer a mode where the AI says something like:

> Let's solve this together. What do you think we should do first?

The student answers, and the AI checks that step before moving on.

### Why This Helps

This helps students actually learn the process instead of only reading the final answer.

### Possible UI Ideas

- Add a toggle called `Step-by-Step Mode`.
- When it is on, the AI asks one question at a time.
- Show short feedback after each student step:
  - `Correct, now try the next step.`
  - `Close, but check this part again.`
  - `Good idea, but we need to do a different operation first.`

### Example

Student:

```text
Solve 2x + 3 = 11
```

AI:

```text
Let's solve it one step at a time.

We want to get x by itself. What should we do first to undo the +3?
```

Student:

```text
Subtract 3
```

AI:

```text
Exactly. Subtracting 3 from both sides gives us:

2x = 8

Now what should we do to get x by itself?
```

### Implementation Notes

- Add a frontend toggle for step-by-step mode.
- Send the mode setting with each chat request.
- Update the AI prompt so the tutor gives only the next step, not the full solution.
- Store enough conversation history so the AI knows which step the student is on.

## 2. Practice Problem Generator

### Goal

After helping with a problem, the tutor can give a similar practice problem.

### How It Should Work

The AI should offer a practice problem after a solution or explanation:

```text
Want to try a similar one?
```

If the student says yes, the AI creates a new problem using the same topic and similar difficulty.

### Why This Helps

Students learn better when they practice right after seeing an example.

### Possible UI Ideas

- Add a `Practice` button under AI answers.
- The button asks the AI for a similar problem.
- The AI should not show the answer immediately.
- After the student tries it, the AI checks their answer.

### Example

Original problem:

```text
Solve 2x + 3 = 11
```

Practice problem:

```text
Try this one:

Solve 3x - 4 = 14
```

### Implementation Notes

- Detect the topic of the last problem.
- Ask the AI to generate one similar problem.
- Save the practice problem in the session so the app can check the student's answer later.
- Add rules so the AI does not immediately reveal the answer.

## 3. Mistake Detector

### Goal

Let students show their work and have the AI find where the mistake happened.

### How It Should Work

The student can type their steps, and the AI checks them carefully.

The AI should say:

- Which step is correct.
- Where the first mistake happened.
- Why it is a mistake.
- How to fix it.

### Why This Helps

Students often know part of the process but make one small mistake. This feature helps them learn from that exact point.

### Example

Student:

```text
Check my work:
2x + 3 = 11
2x = 11 - 3
2x = 7
x = 3.5
```

AI:

```text
Your setup is good, but the first mistake is here:

2x = 11 - 3
2x = 7

The subtraction should be:

11 - 3 = 8

So the correct next step is:

2x = 8

Then divide by 2:

x = 4
```

### Implementation Notes

- Add a prompt rule for checking student work.
- Detect phrases like:
  - `check my work`
  - `is this right`
  - `where did I mess up`
  - `did I do this correctly`
- Ask the AI to find the first incorrect step instead of rewriting everything.
- For algebra problems, use SymPy when possible to verify equations.

## Best Build Order

1. Build Step-by-Step Mode first.
2. Build Practice Problem Generator second.
3. Build Mistake Detector third.

This order makes sense because step-by-step mode teaches the student, practice mode helps them try it, and mistake detection helps them improve when they get stuck.
