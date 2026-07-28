"""
Delphic AI - Flask Application
"""

from flask import Flask, render_template, request, jsonify, session, Response, stream_with_context
from ai.prompt import FLASK_DEBUG, FLASK_SECRET_KEY, SCIENCE_TUTOR_SYSTEM_PROMPT
from ai.service import (
    get_default_provider_config,
    get_math_solution,
    get_math_solution_stream,
    get_public_provider_options,
    get_api_key_validation_error,
    normalise_latex,
    SUPPORTED_AI_PROVIDERS,
)
from ai.detector import detect_and_solve, extract_plot_info
from database import (
    init_db, save_message, load_messages, clear_messages,
    log_tokens, get_total_tokens,
    increment_question_count, detect_topic, add_topic, get_topics,
    save_last_equation, get_last_equation, list_all_sessions
)
import uuid
import re
import os

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
trusted_hosts = [
    host.strip()
    for host in os.getenv("DELPHIC_TRUSTED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]
app.config.update(
    MAX_CONTENT_LENGTH=1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    TRUSTED_HOSTS=trusted_hosts,
)
AI_SETTINGS_BY_SESSION: dict[str, dict] = {}

# Set up the database on startup
init_db()

SAFETY_REDIRECT_REPLY = (
    "Sorry, I'm here to help with learning. Send me a math question, "
    "a step you want checked, or a topic you want explained.\n\n"
    "CONFIDENCE: High"
)

SCIENCE_SAFETY_REDIRECT_REPLY = (
    "Sorry, I'm here to help with learning. Send me a science question, "
    "a step you want checked, or a topic you want explained.\n\n"
    "CONFIDENCE: High"
)

SCIENCE_MATH_TOOL_REDIRECT_REPLY = (
    "That looks like a math graphing request. I can help with science concepts here, "
    "but graphing and pure math solving belong in the Math tutor. Use the Math tutor "
    "for the graph, or ask me what the equation means in a science context.\n\n"
    "CONFIDENCE: High"
)

SCIENCE_QUIZ_GRADING_RULES = (
    "Quiz grading rule: Before grading, compare the student's answer with the accepted science answer. "
    "If the student's answer is correct, mark it correct and do not invent a correction. "
    "If the student's answer is partly correct or wrong, explain exactly why in one or two student-friendly sentences, "
    "then name the correct idea. For Earth layer questions, use this order: crust, mantle, outer core, inner core. "
    "The layer directly below the crust is the mantle."
)


@app.after_request
def add_security_headers(response):
    """Apply browser protections that are safe for the local HTTP app."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    return response


def should_redirect_to_learning(user_message: str) -> bool:
    """Catch obvious hateful or abusive prompts and keep the tutor focused."""
    text = user_message.lower()
    protected_group_terms = [
        "race", "religion", "muslim", "jewish", "christian", "hindu",
        "black people", "white people", "asian people", "latino people",
        "immigrants", "gay people", "trans people", "disabled people",
        "women", "men",
    ]
    hateful_actions = [
        "i hate", "kill all", "should die", "are inferior", "are subhuman",
        "get rid of", "wipe out",
    ]
    abusive_directives = [
        "write hateful", "make a hateful", "insult all", "bully someone", "bully people",
    ]

    targets_group = any(term in text for term in protected_group_terms)
    hateful_toward_group = targets_group and any(action in text for action in hateful_actions)
    asks_for_abuse = any(phrase in text for phrase in abusive_directives)

    return hateful_toward_group or asks_for_abuse


def should_redirect_science_math_tooling(user_message: str) -> bool:
    """Keep obvious math graphing/tool requests out of the science workspace."""
    text = user_message.lower().strip()
    starts_with_graphable_equation = bool(
        re.match(r'^\s*y\s*=', user_message, re.IGNORECASE)
        or re.match(r'^\s*f\s*\(\s*x\s*\)\s*=', user_message, re.IGNORECASE)
    )
    asks_for_graph = bool(re.search(r'\b(graph|plot|sketch)\b', text))
    contains_graphable_equation = bool(
        re.search(r'\by\s*=', user_message, re.IGNORECASE)
        or re.search(r'\bf\s*\(\s*x\s*\)\s*=', user_message, re.IGNORECASE)
    )
    math_tool_terms = [
        "function", "equation", "parabola", "slope", "intercept",
        "quadratic", "polynomial",
    ]

    return starts_with_graphable_equation or (
        asks_for_graph
        and (contains_graphable_equation or any(term in text for term in math_tool_terms))
    )


def science_quiz_context_active(conversation: list[dict]) -> bool:
    """Detect whether the recent science chat is already inside a quiz."""
    recent_text = "\n".join(
        str(message.get("content", "")) for message in conversation[-10:]
    ).lower()
    quiz_markers = [
        "science quiz",
        "quiz mode",
        "question 1",
        "question 2",
        "question 3",
        "question 4",
        "question 5",
    ]
    done_markers = ["final score", "quiz complete", "quiz is complete"]

    return any(marker in recent_text for marker in quiz_markers) and not any(
        marker in recent_text for marker in done_markers
    )


def get_session_id(mode: str = "math") -> str:
    """Get or create a unique ID for this browser session and tutor mode."""
    key = "session_id" if mode == "math" else f"{mode}_session_id"
    prefix = "" if mode == "math" else f"{mode}:"
    if key not in session:
        session[key] = f"{prefix}{uuid.uuid4()}"
    return session[key]


def get_ai_settings_id() -> str:
    """Create a server-side settings bucket without putting the API key in the cookie."""
    if "ai_settings_id" not in session:
        session["ai_settings_id"] = str(uuid.uuid4())
    return session["ai_settings_id"]


def get_active_ai_config() -> dict | None:
    settings_id = session.get("ai_settings_id")
    if settings_id and settings_id in AI_SETTINGS_BY_SESSION:
        return AI_SETTINGS_BY_SESSION[settings_id]
    return get_default_provider_config()


def get_ai_status() -> dict:
    active_config = get_active_ai_config()
    provider = active_config.get("provider") if active_config else "groq"
    source = active_config.get("source") if active_config else None
    return {
        "configured": bool(active_config and active_config.get("api_key")),
        "provider": provider,
        "source": source,
        "providers": get_public_provider_options(),
    }


@app.route("/ai-settings", methods=["GET", "POST", "DELETE"])
def ai_settings():
    """Save or report the AI provider settings for this local app session."""
    if request.method == "GET":
        return jsonify(get_ai_status())

    settings_id = get_ai_settings_id()
    if request.method == "DELETE":
        AI_SETTINGS_BY_SESSION.pop(settings_id, None)
        return jsonify(get_ai_status())

    data = request.get_json() or {}
    provider = str(data.get("provider", "")).strip().lower()
    api_key = str(data.get("api_key", "")).strip()

    if provider not in SUPPORTED_AI_PROVIDERS:
        return jsonify({"error": "Choose a supported AI provider."}), 400
    validation_error = get_api_key_validation_error(api_key)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    AI_SETTINGS_BY_SESSION[settings_id] = {
        "provider": provider,
        "api_key": api_key,
        "source": "session",
    }
    return jsonify(get_ai_status())


def session_belongs_to_mode(session_id: str, mode: str) -> bool:
    """Keep math and science session history separated in the shared DB."""
    if mode == "math":
        return not session_id.startswith("science:")
    return session_id.startswith(f"{mode}:")


def list_sessions_for_mode(mode: str) -> list[dict]:
    return [
        item for item in list_all_sessions()
        if session_belongs_to_mode(item["session_id"], mode)
    ]


def classify_follow_up(user_message: str, conversation: list[dict]) -> str | None:
    """Detect follow-ups and classify the student's intent."""
    if len(conversation) < 2:
        return None

    text = user_message.lower().strip()
    compact_text = text.rstrip("?!., ")

    check_phrases = [
        "i got", "my answer", "is this right", "is that right",
        "am i right", "did i do", "check my", "check this", "is my work",
        "check it", "check this work", "check my work", "check my answer",
        "did i get it", "did i get this", "does this look right",
        "is my answer right", "is my answer correct", "is this correct",
        "is it correct", "is it right", "would this be right",
        "i think", "i got to", "i ended with", "i ended up with",
        "my final answer", "here is my work", "heres my work",
    ]
    easier_phrases = [
        "i don't get", "i dont get", "don't understand", "dont understand",
        "explain again", "explain that", "explain it", "say that again",
        "what do you mean", "can you clarify", "make it simpler",
        "simpler", "simple words", "easier words", "easy words",
        "5th grade", "fifth grade", "like i'm 5th grade", "like im 5th grade",
        "elementary school", "go slower", "i'm confused", "im confused", "confused",
        "lost", "no idea", "makes no sense",
    ]
    reasoning_phrases = [
        "why did", "why do", "why does", "why is", "how did", "how do",
        "where did", "what does that mean", "what does this mean",
        "that step", "this step", "what is that",
    ]
    practice_phrases = [
        "another one", "one more", "give me another", "give me one",
        "practice", "similar problem", "similar question", "try another",
        "can i try", "let me try",
    ]
    answer_request_phrases = [
        "give me the answer", "what is the answer", "what's the answer",
        "show me the answer", "tell me the answer", "give the answer",
        "show the solution", "show me the solution", "give me the solution",
        "can you give the answer", "can you give me the answer",
        "solve it for me", "can you solve it", "just solve it", "reveal the answer",
    ]
    harder_phrases = [
        "harder", "more difficult", "challenge", "hard problem",
        "make it harder", "give me a harder",
    ]
    similar_phrases = [
        "what about", "now do", "now try", "try this", "how about",
        "same thing", "same idea",
    ]
    generic_follow_up_phrases = [
        "the previous", "from before", "continue", "keep going",
    ]
    short_follow_ups = {"why", "how", "what", "huh", "wait", "again", "simpler"}

    has_check_phrase = any(phrase in text for phrase in check_phrases)
    looks_like_answer = re.search(r"\b[a-z]\s*=\s*-?\d", text)
    looks_like_multi_step_work = len(re.findall(r"=", text)) >= 2
    looks_like_attempted_step = (
        bool(re.search(r"\b(i|we)\s+(subtracted|added|divided|multiplied|factored|got|ended)\b", text))
        and bool(re.search(r"\d|=", text))
    )

    if has_check_phrase or looks_like_answer or looks_like_multi_step_work or looks_like_attempted_step:
        return "check_work"
    if any(phrase in text for phrase in answer_request_phrases):
        return "answer_request"
    if any(phrase in text for phrase in harder_phrases):
        return "harder_practice"
    if any(phrase in text for phrase in practice_phrases):
        return "similar_practice"
    if any(phrase in text for phrase in easier_phrases):
        return "simplify"
    if any(phrase in text for phrase in reasoning_phrases) or compact_text in {"why", "how"}:
        return "reasoning"
    if any(phrase in text for phrase in similar_phrases):
        return "similar_question"
    if (
        compact_text in short_follow_ups
        or any(phrase in text for phrase in generic_follow_up_phrases)
        or bool(re.search(r"\b(this|that|it)\b", text)) and len(text.split()) <= 6
    ):
        return "general"

    return None


def is_follow_up_question(user_message: str, conversation: list[dict]) -> bool:
    """Detect short or referential follow-ups that depend on earlier context."""
    return classify_follow_up(user_message, conversation) is not None


@app.route("/")
def index():
    """Serve the main chat page."""
    get_session_id()  # Make sure a session ID exists
    return render_template("index.html")


@app.route("/science")
def science():
    """Serve the separate science tutor workspace on the same Flask app."""
    get_session_id("science")
    return render_template("science.html")


@app.route("/history", methods=["GET"])
def history():
    """Return the conversation history for the current session."""
    session_id = get_session_id()
    messages = load_messages(session_id)
    return jsonify({"messages": messages, "tokens_used": get_total_tokens(session_id)})


@app.route("/sessions", methods=["GET"])
def sessions_list():
    """Return all sessions with preview info."""
    current = get_session_id()
    all_sessions = list_sessions_for_mode("math")
    return jsonify({"current_session_id": current, "sessions": all_sessions})


@app.route("/sessions/switch", methods=["POST"])
def switch_session():
    """Switch the active session to an existing one."""
    data = request.get_json() or {}
    target_id = data.get("session_id", "").strip()
    if not target_id:
        return jsonify({"error": "No session_id provided"}), 400
    if not session_belongs_to_mode(target_id, "math"):
        return jsonify({"error": "Session does not belong to the math tutor."}), 400
    session["session_id"] = target_id
    messages = load_messages(target_id)
    return jsonify({"session_id": target_id, "messages": messages, "tokens_used": get_total_tokens(target_id)})


@app.route("/sessions/new", methods=["POST"])
def new_session():
    """Force a brand-new session."""
    new_id = str(uuid.uuid4())
    session["session_id"] = new_id
    return jsonify({"session_id": new_id})


@app.route("/science/history", methods=["GET"])
def science_history():
    """Return the conversation history for the science tutor session."""
    session_id = get_session_id("science")
    messages = load_messages(session_id)
    return jsonify({"messages": messages, "tokens_used": get_total_tokens(session_id)})


@app.route("/science/sessions", methods=["GET"])
def science_sessions_list():
    """Return science tutor sessions with preview info."""
    current = get_session_id("science")
    science_sessions = list_sessions_for_mode("science")
    return jsonify({"current_session_id": current, "sessions": science_sessions})


@app.route("/science/sessions/switch", methods=["POST"])
def science_switch_session():
    """Switch the active science session to an existing one."""
    data = request.get_json() or {}
    target_id = data.get("session_id", "").strip()
    if not target_id:
        return jsonify({"error": "No session_id provided"}), 400
    if not session_belongs_to_mode(target_id, "science"):
        return jsonify({"error": "Session does not belong to the science tutor."}), 400
    session["science_session_id"] = target_id
    messages = load_messages(target_id)
    return jsonify({"session_id": target_id, "messages": messages, "tokens_used": get_total_tokens(target_id)})


@app.route("/science/sessions/new", methods=["POST"])
def science_new_session():
    """Force a brand-new science tutor session."""
    new_id = f"science:{uuid.uuid4()}"
    session["science_session_id"] = new_id
    return jsonify({"session_id": new_id})


def _build_messages_for_ai(
    session_id: str,
    user_message: str,
    hint_mode: bool,
    check_mode: bool,
    step_by_step_mode: bool = False,
    practice_mode: bool = False,
    ai_config: dict | None = None,
) -> list[dict]:
    """
    Shared helper — builds the full list of messages to send to the AI,
    including all feature injections (SymPy hint, frustration, difficulty, topic memory, etc.)
    """
    conversation = load_messages(session_id)
    sympy_result = detect_and_solve(user_message, ai_config=ai_config)
    is_plot_request = bool(re.search(r'\b(plot|graph|draw|sketch|chart)\b', user_message, re.IGNORECASE)) \
        or bool(re.match(r'^\s*y\s*=', user_message, re.IGNORECASE)) \
        or bool(re.match(r'^\s*f\s*\(\s*x\s*\)\s*=', user_message, re.IGNORECASE))
    follow_up_type = classify_follow_up(user_message, conversation)
    is_follow_up = follow_up_type is not None

    messages_for_ai = list(conversation)

    if is_follow_up:
        follow_up_guidance = {
            "reasoning": (
                "The student is asking why or how a step worked. Focus on the reasoning behind that step. "
                "Use the previous problem as the reference point, and avoid solving the whole problem again unless needed."
            ),
            "similar_practice": (
                "The student wants another similar practice problem. Create one new problem at the same difficulty, "
                "then ask them to try the first step. Do not immediately solve the whole new problem unless they ask. "
                "Respond in English."
            ),
            "check_work": (
                "The student is probably giving an attempted answer or work. Check it against the previous problem. "
                "Compare their attempt to the previous problem and the previous tutor explanation. "
                "If it is right, say it is correct and briefly explain the key reason. "
                "If it is wrong, identify the first mistake, explain why that step is wrong, and give only the next correction step. "
                "Stay encouraging and do not make the student feel dumb."
            ),
            "answer_request": (
                "The student is explicitly asking for the answer or full solution to the previous problem. "
                "It is okay to give the answer now. Solve the previous problem clearly and briefly, showing the key steps. "
                "Do not refuse just because the previous turn was practice or step-by-step mode."
            ),
            "simplify": (
                "The student wants the explanation to be much simpler. Rewrite the idea in a clearly easier style. "
                "Use short sentences, common words, and smaller steps. If they ask for 5th grade language, write like "
                "you are explaining to a 5th grader. Avoid formal phrases like 'deeper look,' 'principle,' "
                "'inverse operation,' 'isolate the variable,' or 'equality true' unless you immediately explain them "
                "with simpler words. Use a simple analogy like a balance scale when helpful. Do not copy the previous "
                "answer with only small changes."
            ),
            "harder_practice": (
                "The student wants a harder challenge. Give one slightly harder problem connected to the previous topic, "
                "and briefly state what makes it harder. Do not solve it immediately unless they ask. "
                "Respond in English."
            ),
            "similar_question": (
                "The student gave a similar new question connected to the previous one. Solve it by explicitly connecting "
                "the method to the previous example, but keep the follow-up format lighter than a brand-new lesson."
            ),
            "general": (
                "The student is continuing the previous conversation. Use the recent context and answer the follow-up directly."
            ),
        }.get(follow_up_type, "Use the recent context and answer the follow-up directly.")

        messages_for_ai.append({"role": "system", "content": (
            "FOLLOW-UP MODE IS ACTIVE. This overrides the normal new-question response format. "
            "Do NOT start by naming the math topic. Do NOT open with 'This is about...' or "
            "'This is a ... problem.' Do NOT open with 'This is a deeper look...' "
            "Start with a friendly bridge that shows it connects to the previous question, such as "
            "'Good follow-up,' 'Exactly, that step is important,' "
            "'This connects to the last step,' or 'Same idea, slightly different setup.' "
            "Then briefly rephrase the previous math topic in simpler words so the student is re-oriented. "
            "Then answer the student's follow-up directly. "
            "Do not restart the full new-question format, and do not repeat the same explanation word-for-word. "
            "Use a new angle, smaller steps, or a simple analogy if helpful. "
            f"Specific follow-up type: {follow_up_type}. {follow_up_guidance}"
        )})

    if follow_up_type == "simplify":
        messages_for_ai.append({"role": "system", "content": (
            "SIMPLIFY LANGUAGE OVERRIDE. The main goal of this response is to make the previous explanation easier. "
            "Use 5th-grade-friendly language if the student asked for it. "
            "Rules for this response: "
            "1) Use short sentences. "
            "2) Use everyday words. "
            "3) Break the idea into tiny steps. "
            "4) Use at most one math vocabulary word at a time, then explain it. "
            "5) Do not use a formal opening. "
            "6) Do not repeat the previous response word-for-word. "
            "7) Prefer examples like 'the equation is like a balance scale' over abstract definitions."
        )})

    if sympy_result:
        messages_for_ai.append({"role": "system", "content": (
            f"SymPy computed the exact answer: {sympy_result}. "
            "Use this verified result to guide your step-by-step explanation. "
            "Make sure your final answer matches SymPy's result."
        )})

    if is_plot_request:
        messages_for_ai.append({"role": "system", "content": (
            "The app is already generating a graph image for this function. "
            "Do NOT generate any TikZ, PGFplots, ASCII art, or diagram code. "
            "Instead, just explain the key features of the function "
            "(e.g. shape, intercepts, symmetry, behavior) in words."
        )})

    if hint_mode:
        messages_for_ai.append({"role": "system", "content": (
            "⚠️ OVERRIDE — HINT MODE IS ACTIVE. This overrides all other instructions. "
            "You MUST NOT give the full solution, the final answer, or any step-by-step working. "
            "Give ONLY one short nudge or observation that points the student in the right direction. "
            "Do NOT show any equations being solved. Do NOT give the answer. "
            "End by asking: 'Would you like another hint?'"
        )})

    if check_mode:
        messages_for_ai.append({"role": "system", "content": (
            "The student wants you to CHECK THEIR WORK. "
            "Their message contains their attempted answer. "
            "Carefully compare their attempt to the problem and recent conversation. "
            "Use this format: "
            "1) Verdict: correct, partly correct, or incorrect. "
            "2) First issue: name the first incorrect step, or say there is no issue. "
            "3) Why: explain the reason in simple language. "
            "4) Next step: give the next correction step only. "
            "If correct, keep it brief and reinforce why the method works. "
            "If incorrect, be encouraging and avoid giving the full final answer unless the student directly asks for it."
        )})

    if follow_up_type == "check_work" and not hint_mode:
        messages_for_ai.append({"role": "system", "content": (
            "WORK CHECKING MODE IS ACTIVE. The student is asking whether their answer or work is correct. "
            "Do not solve from scratch unless necessary to check their work. "
            "Compare the student's attempt against the previous problem in the conversation. "
            "Use this short structure: "
            "Verdict, First issue, Why it matters, Next correction step. "
            "If the attempt is correct, say so clearly and explain the key reason. "
            "If the attempt is partly correct or incorrect, point to the first mistake instead of listing every possible mistake. "
            "Do not make the student feel bad. Do not give a long full solution unless they directly ask for it."
        )})

    if step_by_step_mode and not hint_mode and not check_mode:
        messages_for_ai.append({"role": "system", "content": (
            "INTERACTIVE STEP-BY-STEP MODE IS ACTIVE. Act like a tutor sitting with the student. "
            "Your job is to coach the student's next move, not finish the problem for them. "
            "Do NOT give the full solution all at once. Do NOT reveal the final answer unless the student directly asks for the final answer. "
            "Guide the student through only the next useful step. "
            "Ask exactly one clear question for the student to answer next, and use only one question mark in the response. "
            "If the student just gave a step, check it first: say whether it is correct, partly correct, or incorrect. "
            "If it is correct, briefly explain why and ask for the next step. "
            "If it is incorrect, give a small hint and ask them to try that step again. "
            "If this is the first message for a new problem, briefly identify the goal and ask the student what the first move should be. "
            "Keep the response short and conversational, usually 40-90 words. "
            "Do not include a full worked example, a topic list, or multiple numbered steps."
        )})

    if practice_mode and not hint_mode and not check_mode:
        messages_for_ai.append({"role": "system", "content": (
            "PRACTICE PROBLEM GENERATOR MODE IS ACTIVE. The student clicked a Practice Similar Problem button. "
            "Use the recent conversation to identify the last math topic, skill, and difficulty. "
            "Respond in English, even if earlier messages in the conversation used another language. "
            "Create exactly one new practice problem that is similar but uses different numbers or a slightly different setup. "
            "For this initial practice-problem response, Do NOT solve the practice problem and do NOT give the final answer. "
            "This no-answer rule only applies when generating the practice problem. If the student later explicitly asks for "
            "the answer or solution, give the answer and show the key steps. "
            "After the problem, ask the student to try the first step or send their answer. "
            "Keep it short and friendly."
        )})

    question_count = increment_question_count(session_id)
    if question_count % 5 == 0:
        messages_for_ai.append({"role": "system", "content": (
            f"The student has just asked their {question_count}th question this session! "
            "Briefly acknowledge their effort and encourage them to keep going — "
            "one short sentence is enough, then answer their question as normal."
        )})

    frustration_words = ["don't understand", "dont understand", "confused", "lost", "no idea",
                         "makes no sense", "i give up", "this is hard", "help me", "i'm stuck", "im stuck"]
    if any(phrase in user_message.lower() for phrase in frustration_words):
        messages_for_ai.append({"role": "system", "content": (
            "The student seems frustrated or confused. "
            "Start with a short empathetic acknowledgement (one sentence). "
            "Then re-explain using the simplest possible language — "
            "use a real-world analogy if it helps. Break it into very small steps."
        )})

    advanced_words = ["derive", "proof", "theorem", "integral", "differential", "eigenvalue",
                      "matrix", "vector", "convergence", "series", "laplace"]
    basic_words = ["what is", "how do i", "what does", "explain", "simple", "easy", "basic"]
    msg_lower = user_message.lower()
    if any(w in msg_lower for w in advanced_words):
        messages_for_ai.append({"role": "system", "content": (
            "This is an advanced question. Use precise mathematical language, "
            "show rigorous working, and don't oversimplify."
        )})
    elif any(w in msg_lower for w in basic_words):
        messages_for_ai.append({"role": "system", "content": (
            "This is a basic question. Keep the answer short, friendly, and jargon-free. "
            "Use a simple example if helpful."
        )})

    topic = detect_topic(user_message)
    if topic:
        add_topic(session_id, topic)
    topics_so_far = get_topics(session_id)
    if len(topics_so_far) > 1:
        topics_str = ", ".join(topics_so_far[:-1])
        messages_for_ai.append({"role": "system", "content": (
            f"So far in this session, the student has worked on: {topics_str}. "
            "If relevant, briefly connect today's topic to something they've already covered."
        )})

    # ── Feature #14: Topic personas — adjust style to match the subject ──
    PERSONAS = {
        "Algebra":      ("Be precise and methodical. Show every algebraic step clearly. "
                         "Use exact notation and don't skip steps."),
        "Geometry":     ("Be visual and descriptive. Paint a picture with words — describe shapes, "
                         "angles, and spatial relationships. Use real-world analogies where possible."),
        "Trigonometry": ("Connect everything back to the unit circle and right triangles. "
                         "Use diagrams described in words and highlight the patterns between sin, cos, and tan."),
        "Calculus":     ("Be conceptual and intuitive first, then rigorous. Explain the 'why' "
                         "behind limits, derivatives, and integrals before diving into the mechanics."),
        "Statistics":   ("Ground every explanation in real-world examples. Use relatable scenarios "
                         "like sports stats, test scores, or weather to make abstract concepts concrete."),
    }
    current_topic = detect_topic(user_message)
    if current_topic and current_topic in PERSONAS:
        messages_for_ai.append({"role": "system", "content": (
            f"The student is asking about {current_topic}. Adopt this style: {PERSONAS[current_topic]}"
        )})

    # ── Response structure: full topic map for new questions, lighter flow for follow-ups ──
    if practice_mode and not hint_mode and not check_mode:
        messages_for_ai.append({"role": "system", "content": (
            "For this practice response, do NOT include a '📚 Topics used:' section. "
            "Do NOT include a topic bullet list. "
            "Do NOT use the full new-question solution structure. "
            "Only provide the new practice problem and one short instruction for what the student should try next."
        )})
    elif step_by_step_mode and not hint_mode and not check_mode:
        messages_for_ai.append({"role": "system", "content": (
            "For this step-by-step response, do NOT include a '📚 Topics used:' section. "
            "Do NOT include a topic bullet list. "
            "Do NOT use the full new-question structure. "
            "Do NOT provide the whole solution. "
            "End with exactly one question for the student to answer next. "
            "The final line should be that one question."
        )})
    elif follow_up_type == "check_work":
        messages_for_ai.append({"role": "system", "content": (
            "For this work-checking response, do NOT include a '📚 Topics used:' section. "
            "Do NOT use the full new-question structure. "
            "Keep it focused on the student's attempt. "
            "Close with one next correction step or one short question asking them to try that correction."
        )})
    elif is_follow_up:
        messages_for_ai.append({"role": "system", "content": (
            "For this follow-up response, do NOT include a '📚 Topics used:' section. "
            "Do NOT include a topic bullet list. "
            "Do NOT use the full new-question structure. "
            "Close with one short, natural check-in question."
        )})
    else:
        messages_for_ai.append({"role": "system", "content": (
            "Structure this new-question response like this:\n"
            "1. OPEN with ONE short sentence that names the specific math topic or concept — "
            "e.g. 'This is a quadratic equations problem.' or 'This falls under differentiation in Calculus.' "
            "Do NOT restate the student's question — just name the concept.\n"
            "2. Give your full explanation and solution as normal.\n"
            "3. CLOSE with two things:\n"
            "   a) A short '📚 Topics used:' section — a brief bullet list of the topics and subtopics "
            "needed to solve this problem (e.g. '• Power Rule', '• Factoring', '• SOHCAHTOA'). "
            "Keep each bullet to 2-4 words. This helps the student know what to study further.\n"
            "   b) One friendly follow-up line asking if they want help with the answer or any of the topics listed — "
            "e.g. 'Want me to go deeper on any of these topics, or does any step need more explanation?'"
        )})

    return messages_for_ai


def _build_science_messages_for_ai(
    session_id: str,
    user_message: str,
    step_by_step_mode: bool = False,
    practice_mode: bool = False,
    quiz_mode: bool = False,
) -> list[dict]:
    """Build messages for the science tutor without math solver or graph injections."""
    conversation = load_messages(session_id)
    follow_up_type = classify_follow_up(user_message, conversation)
    is_follow_up = follow_up_type is not None
    is_quiz_continuation = science_quiz_context_active(conversation) and not quiz_mode
    messages_for_ai = list(conversation)

    if is_follow_up:
        follow_up_guidance = {
            "reasoning": (
                "The student is asking why or how a science idea works. Focus on the reasoning, "
                "cause and effect, and the connection to the previous explanation."
            ),
            "similar_practice": (
                "The student wants another science practice question. Create one new question at the same difficulty, "
                "then ask them to try explaining their reasoning. Respond in English."
            ),
            "check_work": (
                "The student is giving an attempted explanation or answer. Check the reasoning against the previous topic. "
                "If it is wrong, identify the first incorrect idea, explain why, and give one next correction."
            ),
            "answer_request": (
                "The student is explicitly asking for the answer or full explanation. It is okay to answer clearly now."
            ),
            "simplify": (
                "The student wants the explanation to be much simpler. Use short sentences, everyday words, "
                "and one small analogy if it helps."
            ),
            "harder_practice": (
                "The student wants a harder science challenge. Give one slightly harder question connected to the previous topic, "
                "briefly state what makes it harder, and do not solve it immediately."
            ),
            "similar_question": (
                "The student gave a similar new science question. Connect the method or idea to the previous example."
            ),
            "general": "Use the recent science context and answer the follow-up directly.",
        }.get(follow_up_type, "Use the recent science context and answer the follow-up directly.")

        messages_for_ai.append({"role": "system", "content": (
            "SCIENCE FOLLOW-UP MODE IS ACTIVE. Do not restart a full lesson unless needed. "
            "Connect the answer to the recent science topic, answer directly, and keep the tone calm and clear. "
            f"Specific follow-up type: {follow_up_type}. {follow_up_guidance}"
        )})

    if step_by_step_mode:
        messages_for_ai.append({"role": "system", "content": (
            "SCIENCE GUIDED MODE IS ACTIVE. Coach the student's next reasoning step instead of giving a long lecture. "
            "Do not give a complete explanation. Give at most one key idea or hint, then end with exactly one clear question "
            "for the student to answer next. The final sentence must be a question, and the whole response must use only one "
            "question mark. "
            "If the student gave an explanation, check it first: correct, partly correct, or incorrect. "
            "Keep the response short and conversational, usually 40-90 words."
        )})

    if practice_mode:
        messages_for_ai.append({"role": "system", "content": (
            "SCIENCE PRACTICE MODE IS ACTIVE. Create exactly one science practice question connected to the recent topic. "
            "Do NOT answer the practice question yet. Ask the student to explain their reasoning or try the first step. "
            "Respond in English, even if earlier messages used another language."
        )})

    if quiz_mode:
        messages_for_ai.append({"role": "system", "content": (
            "SCIENCE QUIZ MODE IS ACTIVE. Start an interactive 5-question science quiz in this chat. "
            "Use the student's requested topic if they named one; otherwise choose a balanced general science topic. "
            "Open with one short sentence that the quiz is starting, then ask Question 1 only. "
            "Do NOT include answers, an answer key, or all five questions at once. "
            "After each student answer later, grade it as correct, partly correct, or incorrect. "
            f"{SCIENCE_QUIZ_GRADING_RULES} "
            "Update a simple score if possible, and ask the next question. "
            "After Question 5, give the final score and two quick review points. Respond in English."
        )})

    if is_quiz_continuation:
        messages_for_ai.append({"role": "system", "content": (
            "SCIENCE QUIZ CONTINUATION MODE IS ACTIVE. Treat the student's latest message as an answer to the most recent "
            "quiz question. Do not restart the quiz. Briefly grade the answer as correct, partly correct, or incorrect, "
            f"{SCIENCE_QUIZ_GRADING_RULES} "
            "Update the score if possible, then ask the next quiz question only. "
            "If the student has answered Question 5, give the final score and two quick review points instead of asking another question."
        )})

    frustration_words = ["don't understand", "dont understand", "confused", "lost", "no idea",
                         "makes no sense", "i give up", "this is hard", "help me", "i'm stuck", "im stuck"]
    if any(phrase in user_message.lower() for phrase in frustration_words):
        messages_for_ai.append({"role": "system", "content": (
            "The student seems frustrated or confused. Start with one short empathetic sentence, "
            "then explain the science idea in the simplest useful way."
        )})

    question_count = increment_question_count(session_id)
    if question_count % 5 == 0:
        messages_for_ai.append({"role": "system", "content": (
            f"The student has just asked their {question_count}th science question this session. "
            "Briefly acknowledge their effort in one sentence, then answer normally."
        )})

    return messages_for_ai


@app.route("/stream", methods=["POST"])
def stream():
    """Stream the AI response word by word using Server-Sent Events."""
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    hint_mode  = data.get("hint_mode", False)
    check_mode = data.get("check_mode", False)
    step_by_step_mode = data.get("step_by_step_mode", False)
    practice_mode = data.get("practice_mode", False)

    if not user_message:
        return jsonify({"error": "Please enter a question."}), 400
    if len(user_message) < 3:
        return jsonify({"error": "Your question is too short."}), 400
    if len(user_message) > 2000:
        return jsonify({"error": "Your question is too long."}), 400

    session_id = get_session_id()
    save_message(session_id, "user", user_message)
    if should_redirect_to_learning(user_message):
        save_message(session_id, "assistant", SAFETY_REDIRECT_REPLY)

        @stream_with_context
        def generate_safety_redirect():
            for word in SAFETY_REDIRECT_REPLY.split(" "):
                safe_word = word.replace("\n", "\\n")
                yield f"data: {safe_word} \n\n"
            total = get_total_tokens(session_id)
            yield f"data: [DONE:{total}]\n\n"

        return Response(generate_safety_redirect(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    ai_config = get_active_ai_config()
    if not ai_config:
        return jsonify({"error": "Choose an AI provider and paste your API key first."}), 400

    messages_for_ai = _build_messages_for_ai(
        session_id,
        user_message,
        hint_mode,
        check_mode,
        step_by_step_mode,
        practice_mode,
        ai_config,
    )

    @stream_with_context
    def generate():
        full_reply = []
        for chunk, is_done, _ in get_math_solution_stream(messages_for_ai, ai_config=ai_config):
            if chunk:
                full_reply.append(chunk)
                # Stream raw chunks immediately so the drip animation starts right away
                safe_chunk = chunk.replace("\n", "\\n")
                yield f"data: {safe_chunk}\n\n"

            if is_done:
                # Normalise the complete reply before saving to DB
                complete_reply = normalise_latex("".join(full_reply))
                save_message(session_id, "assistant", complete_reply)
                total = get_total_tokens(session_id)
                yield f"data: [DONE:{total}]\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/ask", methods=["POST"])
def ask():
    """Handle a math question from the user (non-streaming fallback)."""
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    hint_mode    = data.get("hint_mode", False)
    check_mode   = data.get("check_mode", False)
    step_by_step_mode = data.get("step_by_step_mode", False)
    practice_mode = data.get("practice_mode", False)

    if not user_message:
        return jsonify({"error": "Please enter a question."}), 400
    if len(user_message) < 3:
        return jsonify({"error": "Your question is too short. Try asking a full math question!"}), 400
    if len(user_message) > 2000:
        return jsonify({"error": "Your question is too long. Please keep it under 2000 characters."}), 400

    session_id = get_session_id()
    save_message(session_id, "user", user_message)
    if should_redirect_to_learning(user_message):
        save_message(session_id, "assistant", SAFETY_REDIRECT_REPLY)
        return jsonify({"reply": SAFETY_REDIRECT_REPLY, "tokens_used": get_total_tokens(session_id)})

    ai_config = get_active_ai_config()
    if not ai_config:
        return jsonify({"error": "Choose an AI provider and paste your API key first."}), 400

    messages_for_ai = _build_messages_for_ai(
        session_id,
        user_message,
        hint_mode,
        check_mode,
        step_by_step_mode,
        practice_mode,
        ai_config,
    )

    assistant_reply, tokens_used = get_math_solution(messages_for_ai, ai_config=ai_config)
    save_message(session_id, "assistant", assistant_reply)
    log_tokens(session_id, tokens_used)

    return jsonify({"reply": assistant_reply, "tokens_used": get_total_tokens(session_id)})


@app.route("/science/stream", methods=["POST"])
def science_stream():
    """Stream a science tutor response word by word using Server-Sent Events."""
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    step_by_step_mode = data.get("step_by_step_mode", False)
    practice_mode = data.get("practice_mode", False)
    quiz_mode = data.get("quiz_mode", False)

    if not user_message:
        return jsonify({"error": "Please enter a question."}), 400
    if len(user_message) < 3:
        return jsonify({"error": "Your question is too short."}), 400
    if len(user_message) > 2000:
        return jsonify({"error": "Your question is too long."}), 400

    session_id = get_session_id("science")
    save_message(session_id, "user", user_message)
    if should_redirect_to_learning(user_message):
        save_message(session_id, "assistant", SCIENCE_SAFETY_REDIRECT_REPLY)

        @stream_with_context
        def generate_safety_redirect():
            for word in SCIENCE_SAFETY_REDIRECT_REPLY.split(" "):
                safe_word = word.replace("\n", "\\n")
                yield f"data: {safe_word} \n\n"
            total = get_total_tokens(session_id)
            yield f"data: [DONE:{total}]\n\n"

        return Response(generate_safety_redirect(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    if should_redirect_science_math_tooling(user_message):
        save_message(session_id, "assistant", SCIENCE_MATH_TOOL_REDIRECT_REPLY)

        @stream_with_context
        def generate_math_tool_redirect():
            for word in SCIENCE_MATH_TOOL_REDIRECT_REPLY.split(" "):
                safe_word = word.replace("\n", "\\n")
                yield f"data: {safe_word} \n\n"
            total = get_total_tokens(session_id)
            yield f"data: [DONE:{total}]\n\n"

        return Response(generate_math_tool_redirect(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    ai_config = get_active_ai_config()
    if not ai_config:
        return jsonify({"error": "Choose an AI provider and paste your API key first."}), 400

    messages_for_ai = _build_science_messages_for_ai(
        session_id,
        user_message,
        step_by_step_mode,
        practice_mode,
        quiz_mode,
    )

    @stream_with_context
    def generate():
        full_reply = []
        for chunk, is_done, _ in get_math_solution_stream(
            messages_for_ai,
            system_prompt=SCIENCE_TUTOR_SYSTEM_PROMPT,
            ai_config=ai_config,
        ):
            if chunk:
                full_reply.append(chunk)
                safe_chunk = chunk.replace("\n", "\\n")
                yield f"data: {safe_chunk}\n\n"

            if is_done:
                complete_reply = normalise_latex("".join(full_reply))
                save_message(session_id, "assistant", complete_reply)
                total = get_total_tokens(session_id)
                yield f"data: [DONE:{total}]\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/science/ask", methods=["POST"])
def science_ask():
    """Handle a science question from the user (non-streaming fallback)."""
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    step_by_step_mode = data.get("step_by_step_mode", False)
    practice_mode = data.get("practice_mode", False)
    quiz_mode = data.get("quiz_mode", False)

    if not user_message:
        return jsonify({"error": "Please enter a question."}), 400
    if len(user_message) < 3:
        return jsonify({"error": "Your question is too short. Try asking a full science question!"}), 400
    if len(user_message) > 2000:
        return jsonify({"error": "Your question is too long. Please keep it under 2000 characters."}), 400

    session_id = get_session_id("science")
    save_message(session_id, "user", user_message)
    if should_redirect_to_learning(user_message):
        save_message(session_id, "assistant", SCIENCE_SAFETY_REDIRECT_REPLY)
        return jsonify({"reply": SCIENCE_SAFETY_REDIRECT_REPLY, "tokens_used": get_total_tokens(session_id)})

    if should_redirect_science_math_tooling(user_message):
        save_message(session_id, "assistant", SCIENCE_MATH_TOOL_REDIRECT_REPLY)
        return jsonify({"reply": SCIENCE_MATH_TOOL_REDIRECT_REPLY, "tokens_used": get_total_tokens(session_id)})

    ai_config = get_active_ai_config()
    if not ai_config:
        return jsonify({"error": "Choose an AI provider and paste your API key first."}), 400

    messages_for_ai = _build_science_messages_for_ai(
        session_id,
        user_message,
        step_by_step_mode,
        practice_mode,
        quiz_mode,
    )

    assistant_reply, tokens_used = get_math_solution(
        messages_for_ai,
        system_prompt=SCIENCE_TUTOR_SYSTEM_PROMPT,
        ai_config=ai_config,
    )
    save_message(session_id, "assistant", assistant_reply)
    log_tokens(session_id, tokens_used)

    return jsonify({"reply": assistant_reply, "tokens_used": get_total_tokens(session_id)})


@app.route("/plot", methods=["POST"])
def plot():
    """Return Desmos-ready plot data for a math function or points."""
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    session_id = get_session_id()
    ai_config = get_active_ai_config()

    if not user_message:
        return jsonify({"error": "Please enter a function to plot."}), 400

    result = extract_plot_info(user_message)

    # Multi-turn fallback: if no equation found, use last equation + AI resolver
    if result is None:
        last_eq = get_last_equation(session_id)
        if last_eq:
            resolver_messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a math equation resolver. The student previously plotted the equation: "
                        f"`{last_eq}`. "
                        "They have now asked a follow-up graph modification. "
                        "Your job is to output ONLY the new equation as a plain math expression "
                        "(e.g. `2*x**2 + 1`), with no explanation, no LaTeX, no words. "
                        "Just the raw equation string that Python's SymPy can parse. "
                        "If you cannot determine a new equation, output the original equation unchanged."
                    ),
                },
                {"role": "user", "content": user_message},
            ]
            resolved_eq, _ = get_math_solution(resolver_messages, ai_config=ai_config)
            resolved_eq = resolved_eq.strip().strip("`").strip()
            result = extract_plot_info(f"plot {resolved_eq}")

    if result:
        save_last_equation(session_id, result.get("raw_expression") or result["equation_latex"])
        return jsonify(result)

    return jsonify({
        "error": "I could not graph that yet. Try something like: plot y = x^2, graph sin(x), or plot y = 2x + 1."
    }), 400


@app.route("/clear", methods=["POST"])
def clear():
    """Clear conversation history."""
    session_id = get_session_id()
    clear_messages(session_id)
    return jsonify({"status": "ok"})


@app.route("/science/clear", methods=["POST"])
def science_clear():
    """Clear science conversation history."""
    session_id = get_session_id("science")
    clear_messages(session_id)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=FLASK_DEBUG, port=port, use_reloader=False)
