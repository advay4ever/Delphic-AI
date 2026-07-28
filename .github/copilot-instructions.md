<!-- Custom instructions for GitHub Copilot in this workspace -->

# Math AI Tutor - Copilot Instructions

- This is a Python Flask web application that serves as an AI math tutor for high schoolers.
- The backend uses OpenAI GPT-4o for generating step-by-step math solutions.
- SymPy is used for symbolic math operations (solving, simplifying, differentiating, integrating).
- The frontend uses KaTeX for LaTeX rendering and Marked.js for Markdown.
- Math expressions should always use LaTeX notation: `\( ... \)` for inline, `$$ ... $$` for display.
- Follow PEP 8 style for Python code.
- Keep the system prompt in `config.py` focused on being a helpful, encouraging math tutor.
- All AI responses should include step-by-step explanations.
