# Fix: "plot sin x" Not Showing a Graph

## The Problem
When a student types **"plot sin x"**, the app only shows the AI's text description — no graph appears.

> Current status: fixed. The app now extracts graph data with `extract_plot_info()` and renders interactive Desmos graphs in the browser. This note documents the original bug and the parsing fix that made bare trig expressions like `sin x` work.

## Root Cause (Step by Step)

1. JS detects the word "plot" → fires a request to `/plot`
2. Older versions of `/plot` called `detect_and_plot("plot sin x")` in `ai/detector.py`
3. `detect_and_plot` stripped the word "plot" → left with `"sin x"`
4. The old PNG plotting path called `plot_function("sin x")` — but SymPy couldn't parse `"sin x"` (needs `"sin(x)"`)
5. The old plot function failed → `/plot` returned a 400 error
6. JS silently ignores the 400 → no graph shown, only AI text

---

## The Fix

### File: `ai/detector.py` → `_extract_expression()`

After the existing regex conversions (like `^` → `**`), add a step that wraps
bare trig/math function calls that are missing parentheses:

**Before:**
```python
# sin x  →  stays as "sin x"  (SymPy can't parse this)
```

**After (add this block):**
```python
# Convert "sin x" → "sin(x)", "cos 2x" → "cos(2*x)", etc.
for fn in ["sin", "cos", "tan", "cot", "sec", "csc",
           "log", "ln", "exp", "sqrt", "abs",
           "asin", "acos", "atan", "sinh", "cosh", "tanh"]:
    # Match: function name followed by a space and an expression (no opening paren)
    expr = re.sub(
        rf"\b{fn}\s+(?!\()([^\s,+\-*/^()]+)",
        lambda m, f=fn: f"{f}({m.group(1)})",
        expr
    )
```

This converts:
| User types | Before fix | After fix |
|---|---|---|
| `sin x` | `sin x` ❌ | `sin(x)` ✅ |
| `cos 2x` | `cos 2*x` ❌ | `cos(2*x)` ✅ |
| `tan 3x` | `tan 3*x` ❌ | `tan(3*x)` ✅ |
| `sin(x)` | `sin(x)` ✅ | `sin(x)` ✅ (unchanged) |

---

## Files to Change
- **`ai/detector.py`** — `_extract_expression()` function only (~5 lines added)

## Status
✅ Implemented. The current app uses Desmos-ready plot data instead of server-generated PNG graphs.
