"""
Delphic AI - Flask Application
"""

from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    g,
    abort,
    stream_with_context,
)
from ai.prompt import FLASK_DEBUG, FLASK_SECRET_KEY, SCIENCE_TUTOR_SYSTEM_PROMPT
from ai.service import (
    FINISH_REASON_COMPLETE,
    FINISH_REASON_ERROR,
    FINISH_REASON_LENGTH,
    FINISH_REASON_UNKNOWN,
    MAX_CONTINUATIONS_PER_ANSWER,
    get_default_provider_config,
    get_math_solution,
    get_math_solution_stream,
    get_public_provider_options,
    get_api_key_validation_error,
    get_model_validation_error,
    normalise_latex,
    SUPPORTED_AI_PROVIDERS,
)
from ai.detector import detect_and_solve
from ai.chat_titles import generate_chat_title
from ai.graphing import GraphingError, build_graph_spec
from ai.work_checker import check_math_work, looks_like_work_check_request
from ai.device_credentials import DeviceCredentialError
from science import build_science_diagram
from images.storage import (
    ImageStorageError,
    delete_generated_image as delete_stored_image,
    delete_session_images,
    get_image_storage_root,
    list_session_images,
    public_image_metadata,
    read_generated_image,
    safe_image_download_name,
    store_generated_image,
)
from images import ImageGenerationError, ImageValidationError, generate_checked_image
from images.providers import (
    OPENROUTER_IMAGE_MODEL,
    OPENROUTER_IMAGE_MODELS,
    OpenRouterImageGenerationProvider,
    OpenRouterImageReviewProvider,
)
from images.safety import ImageSafetyError
from database import (
    init_db, save_message, load_messages, load_message_records, load_message_page,
    get_message_record, load_messages_through, replace_message_with_continuation,
    clear_messages,
    log_tokens, get_total_tokens,
    increment_question_count, detect_topic, add_topic, get_topics,
    save_last_equation, get_last_equation, list_all_sessions,
    get_session_title_context, save_session_title,
    set_generated_image_message_id,
    get_generated_image_record,
    create_chat_session, chat_session_is_owned, delete_owned_chat,
    list_study_notes, get_study_note, save_study_note, change_study_note, count_enabled_study_notes, edit_study_note,
)
from version import APP_VERSION
from ai.attachments import AttachmentError, MAX_REQUEST_BYTES, read_attachments
from ai.study_library import StudyLibraryError, StudyLibraryConflict, validate_note, validate_title, retrieve, add_references, retrieval_query
from flask import has_request_context
import json
import secrets
import re
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

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
AI_SETTINGS_REVOKED_IDS: dict[str, float] = {}
AI_SETTINGS_LOCK = threading.RLock()
CHAT_TITLE_LOCK = threading.Lock()
CHAT_TITLES_IN_FLIGHT: set[str] = set()
DEFAULT_AI_SETTINGS_TTL_SECONDS = 8 * 60 * 60
try:
    AI_SETTINGS_TTL_SECONDS = max(
        60,
        int(os.getenv("DELPHIC_AI_SETTINGS_TTL_SECONDS", DEFAULT_AI_SETTINGS_TTL_SECONDS)),
    )
except ValueError:
    AI_SETTINGS_TTL_SECONDS = DEFAULT_AI_SETTINGS_TTL_SECONDS
IMAGE_REQUESTS_BY_ID: dict[str, dict] = {}
IMAGE_REQUEST_LOCK = threading.RLock()
CHAT_WRITE_LOCK = threading.Lock()
CHAT_WRITES_IN_FLIGHT: dict[str, object] = {}
IMAGE_LAST_REQUEST_BY_CHAT: dict[tuple[str, str], float] = {}
IMAGE_REQUEST_TTL_SECONDS = 60 * 60
IMAGE_REQUEST_COOLDOWN_SECONDS = 10
MAX_IMAGE_REQUESTS_PER_CHAT = 5


def image_generation_enabled_from_env() -> bool:
    value = os.getenv("DELPHIC_ENABLE_EXPERIMENTAL_IMAGES", "false").strip().lower()
    if value not in {"true", "false"}:
        # Never log the value: a misplaced API key must remain private.
        app.logger.warning(
            "DELPHIC_ENABLE_EXPERIMENTAL_IMAGES must be true or false; "
            "image generation is disabled. Put the OpenRouter key in OPENROUTER_API_KEY."
        )
        return False
    return value == "true"


IMAGE_GENERATION_ENABLED = image_generation_enabled_from_env()
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

LOCAL_GRAPH_REPLY = (
    "Here is the local graph. Add an AI provider in AI Settings if you also want "
    "a written explanation of what the graph means."
)


def format_stream_text(text: str) -> str:
    return f"event: token\ndata: {json.dumps({'text': text})}\n\n"


def format_stream_completion(
    total_tokens: int,
    finish_reason: str | None,
    message_id: int | None = None,
    session_id: str | None = None,
    can_continue: bool = False,
    continuation_count: int = 0,
    sources: list[dict] | None = None,
    diagram: dict | None = None,
) -> str:
    """Send structured completion metadata and the temporary legacy marker."""
    metadata = json.dumps({
        "tokens_used": total_tokens,
        "finish_reason": finish_reason or FINISH_REASON_UNKNOWN,
        "message_id": message_id,
        "session_id": session_id,
        "can_continue": can_continue,
        "continuation_count": continuation_count,
        "sources": sources or [],
        "diagram": diagram,
    })
    return f"event: complete\ndata: {metadata}\n\ndata: [DONE:{total_tokens}]\n\n"


def continuation_is_available(finish_reason: str | None, guided_mode: bool = False) -> bool:
    """Only length-limited, full-answer responses may be continued."""
    return finish_reason == FINISH_REASON_LENGTH and not guided_mode


def join_continued_response(original: str, continuation: str) -> str:
    """Join continuation text without merging or over-spacing nearby words."""
    if not original:
        return continuation.lstrip()
    if not continuation:
        return original

    left = original.rstrip()
    right = continuation.lstrip()
    max_overlap = min(len(left), len(right), 500)
    for overlap_length in range(max_overlap, 19, -1):
        if left[-overlap_length:].casefold() == right[:overlap_length].casefold():
            right = right[overlap_length:].lstrip()
            break

    if not right:
        return left
    if right[0] in ".,;:!?)]}":
        return left + right
    return left + " " + right

SCIENCE_QUIZ_GRADING_RULES = (
    "Quiz grading rule: Before grading, compare the student's answer with the accepted science answer. "
    "If the student's answer is correct, mark it correct and do not invent a correction. "
    "If the student's answer is partly correct or wrong, explain exactly why in one or two student-friendly sentences, "
    "then name the correct idea. For Earth layer questions, use this order: crust, mantle, outer core, inner core. "
    "The layer directly below the crust is the mantle."
)


def get_chat_owner_id() -> str:
    """Only a server-issued identity in the signed session can own new chats."""
    session_owner = session.get("chat_owner_id")
    try:
        if session_owner:
            return str(uuid.UUID(str(session_owner)))
    except ValueError:
        pass

    owner_id = str(uuid.uuid4())
    session["chat_owner_id"] = owner_id
    return owner_id


def get_image_owner_id() -> str:
    return get_chat_owner_id()


def get_generated_image_storage_root() -> Path:
    """Return the private generated-image folder for this Delphic installation."""
    data_dir = Path(os.getenv("DELPHIC_DATA_DIR") or app.instance_path)
    return get_image_storage_root(data_dir)


def get_public_images_for_session(session_id: str) -> list[dict]:
    """Return only browser-safe metadata for this owner's images in one chat."""
    try:
        records = list_session_images(get_image_owner_id(), session_id)
        return [public_image_metadata(record) for record in records]
    except ImageStorageError:
        return []


def delete_generated_images_for_chat(session_id: str) -> int:
    """Remove this browser owner's saved image files and records for one chat."""
    return delete_session_images(
        owner_id=get_image_owner_id(),
        session_id=session_id,
        storage_root=get_generated_image_storage_root(),
    )


@app.after_request
def add_security_headers(response):
    """Apply browser protections that are safe for the local HTTP app."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if request.endpoint != "static" and not response.cache_control.no_store:
        response.headers["Cache-Control"] = "private, no-store"
    return response


@app.before_request
def use_one_local_browser_address():
    """Keep local browser tabs on one origin so they share the same session cookie."""
    if (
        request.method == "GET"
        and request.headers.get("Sec-Fetch-Mode", "").lower() == "navigate"
        and request.host.partition(":")[0].lower() == "localhost"
    ):
        port = request.host.partition(":")[2]
        if port and (not port.isdigit() or not 1 <= int(port) <= 65535):
            return None
        canonical_host = f"127.0.0.1:{port}" if port else "127.0.0.1"
        query = request.query_string.decode("latin-1")
        suffix = f"?{query}" if query else ""
        return redirect(
            f"{request.scheme}://{canonical_host}{request.path}{suffix}",
            code=302,
        )
    return None


def get_library_owner_id() -> str:
    if "study_library_id" not in session:
        session["study_library_id"] = str(uuid.uuid4())
    return session["study_library_id"]


@app.before_request
def initialize_study_library():
    if request.method == "GET" and request.path in {"/", "/science"}:
        get_library_owner_id()
    if request.path.startswith("/library/") and request.method != "GET":
        origin = request.headers.get("Origin")
        if (origin and origin != request.host_url.rstrip("/")) or request.headers.get("Sec-Fetch-Site") == "cross-site":
            return jsonify({"error": "Use Study Library from this app's own page."}), 403


def public_study_note(note):
    fields = ("id", "title", "subject", "text", "enabled", "created_at", "updated_at", "revision")
    return {field: note[field] for field in fields}


@app.route("/library/notes", methods=["GET", "POST"])
def library_notes():
    owner = get_library_owner_id()
    if request.method == "GET":
        response = jsonify({"notes": [public_study_note(note) for note in list_study_notes(owner)]})
        response.headers["Cache-Control"] = "no-store"
        return response
    data, error = get_json_object()
    if error:
        return error
    try:
        title, subject, text = validate_note(data.get("title"), data.get("subject"), data.get("text"))
        enabled = data.get("enabled", True)
        if not isinstance(enabled, bool):
            raise StudyLibraryError("Note selection must be true or false.")
        note_id = save_study_note(owner, title, subject, text, enabled)
    except StudyLibraryError as error:
        return jsonify({"error": str(error), "suggested_subject": error.suggested_subject}), 400
    return jsonify({"id": note_id}), 201


@app.route("/library/notes/<note_id>", methods=["PATCH", "DELETE"])
def library_note_change(note_id):
    enabled, title = None, None
    if request.method == "PATCH":
        data, error = get_json_object()
        if error:
            return error
        if "text" in data or "subject" in data:
            if set(data) != {"title", "subject", "text", "revision"}:
                return jsonify({"error": "Send the title, subject, text, and revision together."}), 400
            if type(data["revision"]) is not int or not 1 <= data["revision"] <= 2**63 - 1:
                return jsonify({"error": "Load the saved note before editing it."}), 400
            try:
                title, subject, text = validate_note(data["title"], data["subject"], data["text"])
                note = edit_study_note(get_library_owner_id(), note_id, title, subject, text, data["revision"])
            except StudyLibraryConflict as error:
                return jsonify({"error": str(error), "conflict": True}), 409
            except StudyLibraryError as error:
                return jsonify({"error": str(error), "field": error.field,
                                "suggested_subject": error.suggested_subject}), 400
            if note is None:
                return jsonify({"error": "That note was not found in your library. Your draft is still here."}), 404
            return jsonify({"ok": True, "note": public_study_note(note)})
        if not data or set(data) - {"enabled", "title"}:
            return jsonify({"error": "Change a note's title or selection."}), 400
        if "enabled" in data:
            enabled = data["enabled"]
            if not isinstance(enabled, bool):
                return jsonify({"error": "Note selection must be true or false."}), 400
        if "title" in data:
            try:
                title = validate_title(data["title"])
            except StudyLibraryError as error:
                return jsonify({"error": str(error)}), 400
    if not change_study_note(get_library_owner_id(), note_id, enabled, title):
        return jsonify({"error": "That note was not found in your library."}), 404
    if request.method == "PATCH":
        note = get_study_note(get_library_owner_id(), note_id)
        if note is None:
            return jsonify({"error": "That note was deleted in another tab."}), 404
        return jsonify({"ok": True, "note": public_study_note(note)})
    return jsonify({"ok": True})


@app.route("/library/status")
def library_status():
    subject = request.args.get("subject", "")
    if subject not in {"math", "science"}:
        return jsonify({"error": "Choose Math or Science for library status."}), 400
    response = jsonify({"subject": subject, "enabled_count": count_enabled_study_notes(get_library_owner_id(), subject)})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/library/preview", methods=["POST"])
def library_preview():
    request.max_content_length = 5 * 1024 * 1024
    files = request.files.getlist("file")
    if len(files) != 1 or len(request.files) != 1:
        return jsonify({"error": "Choose one document to preview."}), 400
    if Path(files[0].filename or "").suffix.lower() not in {".txt", ".md", ".csv", ".json", ".pdf", ".docx"}:
        return jsonify({"error": "Use TXT, MD, CSV, JSON, text PDF, or DOCX for saved notes. Photos belong in chat attachments."}), 400
    try:
        item = read_attachments(files, None)[0]
    except AttachmentError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"title": item["name"][:80], "text": item["text"]})


def library_references(mode, query, conversation):
    if not has_request_context():
        return []
    prior = list(conversation)
    if prior and prior[-1].get("role") == "user" and prior[-1].get("content") == query:
        prior.pop()
    search = retrieval_query(query, prior, classify_follow_up(query, prior))
    return retrieve(list_study_notes(get_library_owner_id(), mode), search)


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
    owner_id = get_chat_owner_id()
    requested = request.headers.get("X-Delphic-Chat-ID")
    if requested is not None:
        if not chat_session_is_owned(requested, owner_id, mode):
            abort(Response('{"error":"That chat was not found. Refresh or start a new chat."}',
                           status=404, mimetype="application/json"))
        return requested
    current = session.get(key)
    if not isinstance(current, str) or not chat_session_is_owned(current, owner_id, mode):
        session[key] = create_chat_session(owner_id, mode)
    return session[key]


@app.before_request
def reserve_chat_write():
    """Keep costly or destructive writes to one chat from overlapping."""
    if request.method not in {"POST", "DELETE"}:
        return None
    endpoint = request.endpoint
    targets = []
    if endpoint in {"delete_session", "science_delete_session", "delete_many_sessions", "science_delete_many_sessions"}:
        mode = "science" if request.path.startswith("/science/") else "math"
        if endpoint in {"delete_many_sessions", "science_delete_many_sessions"}:
            targets, error = get_requested_session_ids_for_mode(mode)
        else:
            target, error = get_requested_session_id_for_mode(mode)
            targets = [target]
        if error:
            return error
    elif endpoint in {"ask", "stream", "science_ask", "science_stream", "continue_response",
                      "clear", "science_clear", "save_local_graph_message", "generate_image"}:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return None
        mode = "science" if request.path.startswith("/science/") else "math"
        if endpoint == "generate_image":
            mode = data.get("area", "math")
            if mode not in {"math", "science"}:
                return None
        targets = [get_session_id(mode)]
    elif endpoint == "generated_image_file" and request.method == "DELETE":
        record = get_generated_image_record(request.view_args["image_id"], get_image_owner_id())
        if record:
            targets = [record["session_id"]]
    if not targets:
        return None
    with CHAT_WRITE_LOCK:
        if any(target in CHAT_WRITES_IN_FLIGHT for target in targets):
            return jsonify({"error": "This chat is busy finishing a request. Please try again when it finishes."}), 409
        lease = object()
        for target in targets:
            CHAT_WRITES_IN_FLIGHT[target] = lease
    g.chat_write_reservation = (tuple(targets), lease)
    return None


def release_chat_write(reservation):
    if not reservation:
        return
    targets, lease = reservation
    with CHAT_WRITE_LOCK:
        for target in targets:
            if CHAT_WRITES_IN_FLIGHT.get(target) is lease:
                del CHAT_WRITES_IN_FLIGHT[target]


@app.after_request
def finish_chat_write(response):
    reservation = g.pop("chat_write_reservation", None)
    if not reservation:
        return response
    if not response.is_streamed:
        release_chat_write(reservation)
        return response
    original = response.response

    def guarded_stream():
        try:
            yield from original
        finally:
            try:
                if hasattr(original, "close"):
                    original.close()
            finally:
                release_chat_write(reservation)

    response.response = guarded_stream()
    response.call_on_close(lambda: release_chat_write(reservation))
    return response


@app.teardown_request
def release_failed_chat_write(_error):
    release_chat_write(g.pop("chat_write_reservation", None))


def get_ai_settings_id() -> str:
    """Create a server-side settings bucket without putting the API key in the cookie."""
    settings_id = session.get("ai_settings_id")
    with AI_SETTINGS_LOCK:
        _cleanup_expired_ai_settings_locked()
        if not settings_id or settings_id in AI_SETTINGS_REVOKED_IDS:
            settings_id = str(uuid.uuid4())
            session["ai_settings_id"] = settings_id
    return settings_id


def _cleanup_expired_ai_settings_locked(now: float | None = None) -> None:
    """Remove temporary keys and old revocation markers after their timeout."""
    current_time = time.monotonic() if now is None else now
    expired_settings = [
        settings_id
        for settings_id, config in AI_SETTINGS_BY_SESSION.items()
        if current_time - float(config.get("last_used_at", 0)) >= AI_SETTINGS_TTL_SECONDS
    ]
    for settings_id in expired_settings:
        AI_SETTINGS_BY_SESSION.pop(settings_id, None)

    expired_revocations = [
        settings_id
        for settings_id, revoked_at in AI_SETTINGS_REVOKED_IDS.items()
        if current_time - revoked_at >= AI_SETTINGS_TTL_SECONDS
    ]
    for settings_id in expired_revocations:
        AI_SETTINGS_REVOKED_IDS.pop(settings_id, None)


def get_temporary_ai_config(settings_id: str | None, *, touch: bool = True) -> dict | None:
    """Return one unexpired server-side setting without its internal timestamp."""
    if not settings_id:
        return None
    with AI_SETTINGS_LOCK:
        now = time.monotonic()
        _cleanup_expired_ai_settings_locked(now)
        config = AI_SETTINGS_BY_SESSION.get(settings_id)
        if config is None or settings_id in AI_SETTINGS_REVOKED_IDS:
            return None
        if touch:
            config["last_used_at"] = now
        return {
            "provider": config["provider"],
            "api_key": config["api_key"],
            "model": config["model"],
            "image_model": config.get("image_model", OPENROUTER_IMAGE_MODEL),
            "source": "session",
        }


def save_temporary_ai_config(
    settings_id: str,
    provider: str,
    api_key: str,
    model: str,
    image_model: str = OPENROUTER_IMAGE_MODEL,
) -> None:
    """Save a temporary key in process memory, never in the browser session."""
    with AI_SETTINGS_LOCK:
        _cleanup_expired_ai_settings_locked()
        AI_SETTINGS_REVOKED_IDS.pop(settings_id, None)
        AI_SETTINGS_BY_SESSION[settings_id] = {
            "provider": provider,
            "api_key": api_key,
            "model": model,
            "image_model": image_model,
            "last_used_at": time.monotonic(),
        }


def forget_temporary_ai_config() -> None:
    """Immediately remove and revoke this browser session's temporary key."""
    settings_id = session.pop("ai_settings_id", None)
    if not settings_id:
        return
    with AI_SETTINGS_LOCK:
        now = time.monotonic()
        _cleanup_expired_ai_settings_locked(now)
        AI_SETTINGS_BY_SESSION.pop(settings_id, None)
        AI_SETTINGS_REVOKED_IDS[settings_id] = now


def get_active_ai_config() -> dict | None:
    settings_id = session.get("ai_settings_id")
    return get_temporary_ai_config(settings_id) or get_device_ai_config() or get_default_provider_config()


def get_device_credential_store():
    # Only the desktop launcher enables this; headers, cookies, and JSON cannot.
    store = app.extensions.get("desktop_credentials")
    if store is not None and (
        request.remote_addr not in {"127.0.0.1", "::1"}
        or request.host.split(":", 1)[0].lower() not in {"127.0.0.1", "localhost"}
    ):
        abort(403)
    return store


def get_device_ai_config():
    store = get_device_credential_store()
    saved = store.load() if store else None
    if not saved:
        return None
    provider = saved.get("provider")
    if (provider not in SUPPORTED_AI_PROVIDERS
            or get_api_key_validation_error(saved.get("api_key"))
            or get_model_validation_error(saved.get("model"), provider)
            or saved.get("image_model") not in {item["id"] for item in OPENROUTER_IMAGE_MODELS}):
        store.error = "The saved connection is no longer supported. Choose a model and reconnect, or forget the saved key."
        return None
    return {**saved, "source": "device"}


def get_ai_status() -> dict:
    active_config = get_active_ai_config()
    provider = active_config.get("provider") if active_config else "groq"
    model = (active_config or {}).get("model") or SUPPORTED_AI_PROVIDERS[provider]["model"]
    image_model = (active_config or {}).get("image_model") or OPENROUTER_IMAGE_MODEL
    source = active_config.get("source") if active_config else None
    store = get_device_credential_store()
    saved = store.load() if store else None
    remembered = bool(saved and not store.error and active_config and saved["provider"] == provider
                      and saved["api_key"] == active_config.get("api_key"))
    return {
        "configured": bool(active_config and active_config.get("api_key")),
        "provider": provider,
        "model": model,
        "image_model": image_model,
        "image_models": list(OPENROUTER_IMAGE_MODELS),
        "source": source,
        "can_forget": source in {"session", "device"} or bool(saved) or bool(store and store.error),
        "device_storage": store is not None,
        "device_storage_available": bool(store and store.available),
        "device_storage_error": store.error if store else "",
        "remember_key": remembered,
        "has_saved_key": bool(saved) or bool(store and store.error),
        "providers": get_public_provider_options(),
    }


def get_json_object():
    """Return a JSON object or a clear client error for malformed request bodies."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "Send a JSON object."}), 400)
    return data, None


def get_json_text(data: dict, field_name: str) -> str:
    """Read one text field without allowing malformed values to crash a route."""
    value = data.get(field_name, "")
    return value.strip() if isinstance(value, str) else ""


@app.errorhandler(413)
def upload_too_large(_error):
    return jsonify({"error": "The upload is too large. Attach at most 3 files, under 4 MiB each."}), 413


def get_tutor_request():
    """Retain JSON compatibility and accept actual files only as multipart uploads."""
    if request.mimetype != "multipart/form-data":
        data, error = get_json_object()
        if not error and "_processed_attachments" in data:
            return None, (jsonify({"error": "Upload actual files, not attachment data in JSON."}), 400)
        return data, error
    request.max_content_length = MAX_REQUEST_BYTES
    try:
        data = json.loads(request.form.get("payload", ""))
        if not isinstance(data, dict) or "_processed_attachments" in data:
            raise ValueError
    except (ValueError, TypeError):
        return None, (jsonify({"error": "Send a valid message with your files."}), 400)
    config = get_active_ai_config()
    if not config:
        return None, (jsonify({"error": "Choose an AI provider and paste your API key first."}), 400)
    if set(request.files) - {"files"}:
        return None, (jsonify({"error": "Send attachments in the files field."}), 400)
    try:
        data["_processed_attachments"] = read_attachments(request.files.getlist("files"), config)
    except AttachmentError as error:
        return None, (jsonify({"error": str(error)}), 400)
    if not get_json_text(data, "message") and data["_processed_attachments"]:
        data["message"] = "Please explain the attached material."
    return data, None


@app.route("/ai-settings", methods=["GET", "POST", "DELETE"])
def ai_settings():
    """Save or report the AI provider settings for this local app session."""
    origin = request.headers.get("Origin")
    if (origin and origin != request.host_url.rstrip("/")) or request.headers.get("Sec-Fetch-Site") == "cross-site":
        return jsonify({"error": "Open AI Settings from Delphic's own page."}), 403
    store = get_device_credential_store()
    if request.method == "GET":
        return jsonify(get_ai_status())

    if request.method == "DELETE":
        with AI_SETTINGS_LOCK:
            if store:
                try:
                    store.clear()
                except DeviceCredentialError as exc:
                    return jsonify({"error": str(exc)}), 503
            forget_temporary_ai_config()
        return jsonify(get_ai_status())

    data, error = get_json_object()
    if error:
        return error
    provider = get_json_text(data, "provider").lower()
    api_key = get_json_text(data, "api_key")
    reuse_existing_key = not api_key
    model = get_json_text(data, "model")
    image_model = get_json_text(data, "image_model")
    if "remember_key" in data and not isinstance(data["remember_key"], bool):
        return jsonify({"error": "Remember key must be true or false."}), 400
    if data.get("remember_key") and not store:
        return jsonify({"error": "Remember key is available only in the desktop app."}), 400

    if provider not in SUPPORTED_AI_PROVIDERS:
        return jsonify({"error": "Choose a supported AI provider."}), 400
    current_config = get_active_ai_config()
    if not image_model:
        image_model = (
            current_config.get("image_model", OPENROUTER_IMAGE_MODEL)
            if current_config and current_config.get("provider") == provider
            else OPENROUTER_IMAGE_MODEL
        )
    if not api_key:
        if current_config and current_config.get("provider") == provider:
            api_key = str(current_config.get("api_key", ""))
        else:
            return jsonify({"error": "Paste an API key for the selected provider."}), 400

    validation_error = get_api_key_validation_error(api_key)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    if not model:
        model = SUPPORTED_AI_PROVIDERS[provider]["model"]
    model_validation_error = get_model_validation_error(model, provider)
    if model_validation_error:
        return jsonify({"error": model_validation_error}), 400

    allowed_image_models = {item["id"] for item in OPENROUTER_IMAGE_MODELS}
    if image_model not in allowed_image_models:
        return jsonify({"error": "Choose one of the listed image models."}), 400

    with AI_SETTINGS_LOCK:
        if reuse_existing_key:
            latest_config = get_active_ai_config()
            if (not latest_config or latest_config.get("provider") != provider
                    or latest_config.get("api_key") != api_key):
                return jsonify({"error": "The AI connection changed while saving. Reopen Settings and try again."}), 409
        if store:
            saved = store.load()
            remember = data.get("remember_key", bool(saved and saved["provider"] == provider and saved["api_key"] == api_key))
            try:
                if remember:
                    store.save({"provider": provider, "api_key": api_key, "model": model, "image_model": image_model})
                else:
                    store.clear()
            except DeviceCredentialError as exc:
                return jsonify({"error": str(exc)}), 503
        settings_id = get_ai_settings_id()
        save_temporary_ai_config(settings_id, provider, api_key, model, image_model)
    return jsonify(get_ai_status())


def session_belongs_to_mode(session_id: str, mode: str) -> bool:
    """Keep math and science session history separated in the shared DB."""
    if mode == "math":
        return not session_id.startswith("science:")
    return session_id.startswith(f"{mode}:")


def list_sessions_for_mode(mode: str) -> list[dict]:
    return list_all_sessions(owner_id=get_chat_owner_id(), mode=mode)


def get_requested_session_id_for_mode(mode: str):
    """Validate a session action without allowing Math and Science chats to mix."""
    data = request.get_json(silent=True)
    target_id = str(data.get("session_id", "")).strip() if isinstance(data, dict) else ""
    if not target_id:
        return None, (jsonify({"error": "Choose a chat first."}), 400)
    if not session_belongs_to_mode(target_id, mode):
        return None, (jsonify({"error": "That chat belongs to a different tutor."}), 400)
    if not chat_session_is_owned(target_id, get_chat_owner_id(), mode):
        return None, (jsonify({"error": "That chat was not found."}), 404)
    return target_id, None


def get_requested_session_ids_for_mode(mode: str, maximum: int = 100):
    """Validate a bounded list of chats before a bulk session action."""
    data = request.get_json(silent=True)
    raw_ids = data.get("session_ids") if isinstance(data, dict) else None
    if not isinstance(raw_ids, list) or not raw_ids:
        return None, (jsonify({"error": "Choose at least one chat."}), 400)
    if len(raw_ids) > maximum:
        return None, (jsonify({"error": f"Choose no more than {maximum} chats at once."}), 400)

    target_ids = []
    for raw_id in raw_ids:
        if not isinstance(raw_id, str) or not raw_id.strip():
            return None, (jsonify({"error": "One of the selected chats is invalid."}), 400)
        target_id = raw_id.strip()
        if not session_belongs_to_mode(target_id, mode):
            return None, (jsonify({"error": "One selected chat belongs to a different tutor."}), 400)
        if target_id not in target_ids:
            target_ids.append(target_id)

    if any(not chat_session_is_owned(target_id, get_chat_owner_id(), mode) for target_id in target_ids):
        return None, (jsonify({"error": "One of the selected chats was not found."}), 404)
    return target_ids, None


def delete_sessions_for_mode(mode: str, target_ids: list[str]):
    """Delete validated chats and replace the active chat only once when needed."""
    current_id = get_session_id(mode)
    for target_id in target_ids:
        delete_generated_images_for_chat(target_id)
        delete_owned_chat(target_id, get_chat_owner_id(), mode)

    if current_id in target_ids:
        replacement_id = create_chat_session(get_chat_owner_id(), mode)
        session_key = "session_id" if mode == "math" else f"{mode}_session_id"
        session[session_key] = replacement_id
        current_id = replacement_id
    return current_id


def delete_session_for_mode(mode: str, target_id: str):
    """Delete one chat and start a blank replacement if it was the active chat."""
    return delete_sessions_for_mode(mode, [target_id])


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


@app.route("/_launcher/ready")
def launcher_ready():
    token = os.getenv("DELPHIC_STARTUP_TOKEN", "")
    provided = request.headers.get("X-Delphic-Launcher", "")
    if not token or not secrets.compare_digest(provided.encode("utf-8"), token.encode("utf-8")):
        abort(404)
    return Response(status=204, headers={
        "X-Delphic-Launcher": token,
        "Cache-Control": "no-store",
    })


@app.route("/")
def index():
    """Serve the main chat page."""
    get_session_id()  # Make sure a session ID exists
    return render_template(
        "index.html",
        app_version=APP_VERSION,
        image_generation_enabled=IMAGE_GENERATION_ENABLED,
    )


@app.route("/science")
def science():
    """Serve the separate science tutor workspace on the same Flask app."""
    get_session_id("science")
    return render_template(
        "science.html",
        app_version=APP_VERSION,
        image_generation_enabled=IMAGE_GENERATION_ENABLED,
    )


@app.route("/history", methods=["GET"])
def history():
    """Return the conversation history for the current session."""
    session_id = get_session_id()
    return chat_history_payload(session_id, request.args)


def chat_history_payload(session_id: str, values=None):
    values = values or {}
    try:
        cursors = {}
        for field in ("before_id", "snapshot_id"):
            value = values.get(field)
            if value is not None:
                if isinstance(value, bool) or not re.fullmatch(r"[0-9]{1,19}", str(value)):
                    raise ValueError("Use a valid history cursor.")
                cursors[field] = int(value)
        page = load_message_page(session_id, **cursors)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    ids = {message.get("id") for message in page["messages"]}
    images = [image for image in get_public_images_for_session(session_id)
              if image.get("message_id") in ids or (image.get("message_id") is None and "before_id" not in cursors)]
    return jsonify({"session_id": session_id, **page, "images": images,
                    "tokens_used": get_total_tokens(session_id)})


@app.route("/sessions", methods=["GET"])
def sessions_list():
    """Return all sessions with preview info."""
    current = get_session_id()
    all_sessions = list_sessions_for_mode("math")
    return jsonify({"current_session_id": current, "sessions": all_sessions})


@app.route("/sessions/switch", methods=["POST"])
def switch_session():
    """Switch the active session to an existing one."""
    data, error = get_json_object()
    if error:
        return error
    target_id = get_json_text(data, "session_id")
    if not target_id:
        return jsonify({"error": "No session_id provided"}), 400
    if not session_belongs_to_mode(target_id, "math"):
        return jsonify({"error": "Session does not belong to the math tutor."}), 400
    if not chat_session_is_owned(target_id, get_chat_owner_id(), "math"):
        return jsonify({"error": "That chat was not found."}), 404
    session["session_id"] = target_id
    return chat_history_payload(target_id)


@app.route("/sessions/new", methods=["POST"])
def new_session():
    """Force a brand-new session."""
    new_id = create_chat_session(get_chat_owner_id(), "math")
    session["session_id"] = new_id
    return jsonify({"session_id": new_id})


@app.route("/sessions/title", methods=["POST"], defaults={"mode": "math"})
@app.route("/science/sessions/title", methods=["POST"], defaults={"mode": "science"})
def summarize_session_title(mode):
    """Name a chat separately from its answer, using the selected AI provider."""
    session_id, error = get_requested_session_id_for_mode(mode)
    if error:
        return error

    def result():
        context = get_session_title_context(session_id)
        return jsonify({
            "session_id": session_id,
            "title": context["title"] if context else "",
            "title_generated": bool(context and context["title"]),
            "tokens_used": get_total_tokens(session_id),
        })

    context = get_session_title_context(session_id)
    if not context or context["title"] or len(context["messages"]) < 2:
        return result()
    ai_config = get_active_ai_config()
    if not ai_config:
        return result()
    with CHAT_TITLE_LOCK:
        if session_id in CHAT_TITLES_IN_FLIGHT:
            return result()
        CHAT_TITLES_IN_FLIGHT.add(session_id)
    try:
        # Another request may have finished between the first read and the lock.
        context = get_session_title_context(session_id)
        if context and not context["title"] and len(context["messages"]) == 2:
            title = generate_chat_title(context["messages"], ai_config)
            save_session_title(
                session_id, context["first_message_id"], title.text, title.tokens_used,
            )
    finally:
        with CHAT_TITLE_LOCK:
            CHAT_TITLES_IN_FLIGHT.discard(session_id)
    return result()


@app.route("/sessions/messages", methods=["POST"])
def session_messages():
    """Return one Math chat for a transcript download without changing the active chat."""
    target_id, error = get_requested_session_id_for_mode("math")
    if error:
        return error
    return chat_history_payload(target_id, request.get_json(silent=True))


@app.route("/sessions/delete", methods=["POST"])
def delete_session():
    """Permanently delete one Math chat."""
    target_id, error = get_requested_session_id_for_mode("math")
    if error:
        return error
    current_id = delete_session_for_mode("math", target_id)
    return jsonify({"deleted_session_id": target_id, "current_session_id": current_id})


@app.route("/sessions/delete-many", methods=["POST"])
def delete_many_sessions():
    """Permanently delete several selected Math chats in one request."""
    target_ids, error = get_requested_session_ids_for_mode("math")
    if error:
        return error
    current_id = delete_sessions_for_mode("math", target_ids)
    return jsonify({"deleted_session_ids": target_ids, "current_session_id": current_id})


@app.route("/science/history", methods=["GET"])
def science_history():
    """Return the conversation history for the science tutor session."""
    session_id = get_session_id("science")
    return chat_history_payload(session_id, request.args)


@app.route("/science/sessions", methods=["GET"])
def science_sessions_list():
    """Return science tutor sessions with preview info."""
    current = get_session_id("science")
    science_sessions = list_sessions_for_mode("science")
    return jsonify({"current_session_id": current, "sessions": science_sessions})


@app.route("/science/sessions/switch", methods=["POST"])
def science_switch_session():
    """Switch the active science session to an existing one."""
    data, error = get_json_object()
    if error:
        return error
    target_id = get_json_text(data, "session_id")
    if not target_id:
        return jsonify({"error": "No session_id provided"}), 400
    if not session_belongs_to_mode(target_id, "science"):
        return jsonify({"error": "Session does not belong to the science tutor."}), 400
    if not chat_session_is_owned(target_id, get_chat_owner_id(), "science"):
        return jsonify({"error": "That chat was not found."}), 404
    session["science_session_id"] = target_id
    return chat_history_payload(target_id)


@app.route("/science/sessions/new", methods=["POST"])
def science_new_session():
    """Force a brand-new science tutor session."""
    new_id = create_chat_session(get_chat_owner_id(), "science")
    session["science_session_id"] = new_id
    return jsonify({"session_id": new_id})


@app.route("/science/sessions/messages", methods=["POST"])
def science_session_messages():
    """Return one Science chat for a transcript download without changing the active chat."""
    target_id, error = get_requested_session_id_for_mode("science")
    if error:
        return error
    return chat_history_payload(target_id, request.get_json(silent=True))


@app.route("/science/sessions/delete", methods=["POST"])
def science_delete_session():
    """Permanently delete one Science chat."""
    target_id, error = get_requested_session_id_for_mode("science")
    if error:
        return error
    current_id = delete_session_for_mode("science", target_id)
    return jsonify({"deleted_session_id": target_id, "current_session_id": current_id})


@app.route("/science/sessions/delete-many", methods=["POST"])
def science_delete_many_sessions():
    """Permanently delete several selected Science chats in one request."""
    target_ids, error = get_requested_session_ids_for_mode("science")
    if error:
        return error
    current_id = delete_sessions_for_mode("science", target_ids)
    return jsonify({"deleted_session_ids": target_ids, "current_session_id": current_id})


def _build_messages_for_ai(
    session_id: str,
    user_message: str,
    hint_mode: bool,
    check_mode: bool,
    step_by_step_mode: bool = False,
    practice_mode: bool = False,
    ai_config: dict | None = None,
    source_metadata: list[dict] | None = None,
) -> list[dict]:
    """
    Shared helper — builds the full list of messages to send to the AI,
    including all feature injections (SymPy hint, frustration, difficulty, topic memory, etc.)
    """
    conversation = load_messages(session_id)
    prior_conversation = list(conversation)
    if (
        prior_conversation
        and prior_conversation[-1].get("role") == "user"
        and prior_conversation[-1].get("content") == user_message
    ):
        prior_conversation.pop()
    is_plot_request = bool(re.search(r'\b(plot|graph|draw|sketch|chart)\b', user_message, re.IGNORECASE)) \
        or bool(re.match(r'^\s*y\s*=', user_message, re.IGNORECASE)) \
        or bool(re.match(r'^\s*f\s*\(\s*x\s*\)\s*=', user_message, re.IGNORECASE)) \
        or bool(re.match(r'^\s*z\s*=', user_message, re.IGNORECASE))
    follow_up_type = classify_follow_up(user_message, conversation)
    is_follow_up = follow_up_type is not None
    explicit_work_check = bool(
        check_mode
        or follow_up_type == "check_work"
        or looks_like_work_check_request(user_message)
    )
    should_try_work_check = explicit_work_check or bool(step_by_step_mode and prior_conversation)
    verified_work_check = (
        check_math_work(
            user_message,
            prior_conversation,
            compare_to_reference=bool(follow_up_type == "check_work" or step_by_step_mode),
        )
        if should_try_work_check
        else None
    )
    work_check_active = explicit_work_check or verified_work_check is not None
    sympy_result = (
        None
        if should_try_work_check
        else detect_and_solve(user_message, ai_config=ai_config)
    )

    messages_for_ai = list(conversation)

    references = library_references("math", user_message, prior_conversation)
    if source_metadata is not None:
        source_metadata.extend(references)
    messages_for_ai = add_references(messages_for_ai, references)

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

    if verified_work_check is not None:
        messages_for_ai.append({
            "role": "system",
            "content": verified_work_check.to_prompt_context(),
        })

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

    if work_check_active and not hint_mode:
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

    if practice_mode and not hint_mode and not work_check_active:
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
    if practice_mode and not hint_mode and not work_check_active:
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
    elif work_check_active:
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
    source_metadata: list[dict] | None = None,
    diagram_spec: dict | None = None,
) -> list[dict]:
    """Build messages for the science tutor without math solver or graph injections."""
    conversation = load_messages(session_id)
    follow_up_type = classify_follow_up(user_message, conversation)
    is_follow_up = follow_up_type is not None
    is_quiz_continuation = science_quiz_context_active(conversation) and not quiz_mode
    messages_for_ai = list(conversation)
    references = library_references("science", user_message, conversation)
    if source_metadata is not None:
        source_metadata.extend(references)
    messages_for_ai = add_references(messages_for_ai, references)

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

    if diagram_spec is not None:
        messages_for_ai.append({"role": "system", "content": (
            f"The app will show a reviewed local diagram titled '{diagram_spec['title']}'. "
            "Explain what the diagram teaches in words and connect the labels to the student's question. "
            "Do not output SVG, HTML, JavaScript, TikZ, ASCII art, or other diagram code."
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
    data, error = get_tutor_request()
    if error:
        return error
    user_message = get_json_text(data, "message")
    hint_mode  = data.get("hint_mode", False)
    check_mode = data.get("check_mode", False)
    step_by_step_mode = data.get("step_by_step_mode", False)
    practice_mode = data.get("practice_mode", False)

    if not user_message:
        return jsonify({"error": "Please enter a question."}), 400
    if len(user_message) > 2000:
        return jsonify({"error": "Your question is too long."}), 400

    session_id = get_session_id()
    save_message(session_id, "user", user_message, attachments=data.get("_processed_attachments"))
    if should_redirect_to_learning(user_message):
        message_id = save_message(
            session_id,
            "assistant",
            SAFETY_REDIRECT_REPLY,
            finish_reason=FINISH_REASON_COMPLETE,
        )

        @stream_with_context
        def generate_safety_redirect():
            for word in SAFETY_REDIRECT_REPLY.split(" "):
                yield format_stream_text(word + " ")
            total = get_total_tokens(session_id)
            yield format_stream_completion(
                total,
                FINISH_REASON_COMPLETE,
                message_id=message_id,
                session_id=session_id,
            )

        return Response(generate_safety_redirect(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    ai_config = get_active_ai_config()
    if not ai_config:
        return jsonify({"error": "Choose an AI provider and paste your API key first."}), 400

    sources = []
    messages_for_ai = _build_messages_for_ai(
        session_id,
        user_message,
        hint_mode,
        check_mode,
        step_by_step_mode,
        practice_mode,
        ai_config,
        sources,
    )

    @stream_with_context
    def generate():
        full_reply = []
        for event in get_math_solution_stream(messages_for_ai, ai_config=ai_config):
            if event.text:
                full_reply.append(event.text)
                # Stream raw chunks immediately so the drip animation starts right away
                yield format_stream_text(event.text)

            if event.done:
                # Normalise the complete reply before saving to DB
                complete_reply = normalise_latex("".join(full_reply))
                can_continue = continuation_is_available(
                    event.finish_reason,
                    guided_mode=step_by_step_mode,
                )
                message_id = save_message(
                    session_id,
                    "assistant",
                    complete_reply,
                    finish_reason=event.finish_reason,
                    continuation_allowed=can_continue,
                    sources=sources,
                )
                if event.tokens_used:
                    log_tokens(session_id, event.tokens_used)
                total = get_total_tokens(session_id)
                yield format_stream_completion(
                    total,
                    event.finish_reason,
                    message_id=message_id,
                    session_id=session_id,
                    can_continue=can_continue,
                    sources=sources,
                )

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/ask", methods=["POST"])
def ask():
    """Handle a math question from the user (non-streaming fallback)."""
    data, error = get_tutor_request()
    if error:
        return error
    user_message = get_json_text(data, "message")
    hint_mode    = data.get("hint_mode", False)
    check_mode   = data.get("check_mode", False)
    step_by_step_mode = data.get("step_by_step_mode", False)
    practice_mode = data.get("practice_mode", False)

    if not user_message:
        return jsonify({"error": "Please enter a question."}), 400
    if len(user_message) > 2000:
        return jsonify({"error": "Your question is too long. Please keep it under 2000 characters."}), 400

    session_id = get_session_id()
    save_message(session_id, "user", user_message, attachments=data.get("_processed_attachments"))
    if should_redirect_to_learning(user_message):
        message_id = save_message(
            session_id,
            "assistant",
            SAFETY_REDIRECT_REPLY,
            finish_reason=FINISH_REASON_COMPLETE,
        )
        return jsonify({
            "reply": SAFETY_REDIRECT_REPLY,
            "tokens_used": get_total_tokens(session_id),
            "finish_reason": FINISH_REASON_COMPLETE,
            "message_id": message_id,
            "session_id": session_id,
            "can_continue": False,
            "continuation_count": 0,
        })

    ai_config = get_active_ai_config()
    if not ai_config:
        return jsonify({"error": "Choose an AI provider and paste your API key first."}), 400

    sources = []
    messages_for_ai = _build_messages_for_ai(
        session_id,
        user_message,
        hint_mode,
        check_mode,
        step_by_step_mode,
        practice_mode,
        ai_config,
        sources,
    )

    ai_response = get_math_solution(messages_for_ai, ai_config=ai_config)
    can_continue = continuation_is_available(
        ai_response.finish_reason,
        guided_mode=step_by_step_mode,
    )
    message_id = save_message(
        session_id,
        "assistant",
        ai_response.text,
        finish_reason=ai_response.finish_reason,
        continuation_allowed=can_continue,
        sources=sources,
    )
    log_tokens(session_id, ai_response.tokens_used)

    return jsonify({
        "reply": ai_response.text,
        "tokens_used": get_total_tokens(session_id),
        "finish_reason": ai_response.finish_reason,
        "message_id": message_id,
        "session_id": session_id,
        "can_continue": can_continue,
        "continuation_count": 0,
        "sources": sources,
    })


@app.route("/science/stream", methods=["POST"])
def science_stream():
    """Stream a science tutor response word by word using Server-Sent Events."""
    data, error = get_tutor_request()
    if error:
        return error
    user_message = get_json_text(data, "message")
    step_by_step_mode = data.get("step_by_step_mode", False)
    practice_mode = data.get("practice_mode", False)
    quiz_mode = data.get("quiz_mode", False)

    if not user_message:
        return jsonify({"error": "Please enter a question."}), 400
    if len(user_message) > 2000:
        return jsonify({"error": "Your question is too long."}), 400

    session_id = get_session_id("science")
    save_message(session_id, "user", user_message, attachments=data.get("_processed_attachments"))
    if should_redirect_to_learning(user_message):
        message_id = save_message(
            session_id,
            "assistant",
            SCIENCE_SAFETY_REDIRECT_REPLY,
            finish_reason=FINISH_REASON_COMPLETE,
        )

        @stream_with_context
        def generate_safety_redirect():
            for word in SCIENCE_SAFETY_REDIRECT_REPLY.split(" "):
                yield format_stream_text(word + " ")
            total = get_total_tokens(session_id)
            yield format_stream_completion(
                total,
                FINISH_REASON_COMPLETE,
                message_id=message_id,
                session_id=session_id,
            )

        return Response(generate_safety_redirect(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    if should_redirect_science_math_tooling(user_message):
        message_id = save_message(
            session_id,
            "assistant",
            SCIENCE_MATH_TOOL_REDIRECT_REPLY,
            finish_reason=FINISH_REASON_COMPLETE,
        )

        @stream_with_context
        def generate_math_tool_redirect():
            for word in SCIENCE_MATH_TOOL_REDIRECT_REPLY.split(" "):
                yield format_stream_text(word + " ")
            total = get_total_tokens(session_id)
            yield format_stream_completion(
                total,
                FINISH_REASON_COMPLETE,
                message_id=message_id,
                session_id=session_id,
            )

        return Response(generate_math_tool_redirect(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    ai_config = get_active_ai_config()
    if not ai_config:
        return jsonify({"error": "Choose an AI provider and paste your API key first."}), 400

    sources = []
    diagram = build_science_diagram(user_message)
    messages_for_ai = _build_science_messages_for_ai(
        session_id,
        user_message,
        step_by_step_mode,
        practice_mode,
        quiz_mode,
        source_metadata=sources,
        diagram_spec=diagram,
    )

    @stream_with_context
    def generate():
        full_reply = []
        for event in get_math_solution_stream(
            messages_for_ai,
            system_prompt=SCIENCE_TUTOR_SYSTEM_PROMPT,
            ai_config=ai_config,
        ):
            if event.text:
                full_reply.append(event.text)
                yield format_stream_text(event.text)

            if event.done:
                complete_reply = normalise_latex("".join(full_reply))
                can_continue = continuation_is_available(
                    event.finish_reason,
                    guided_mode=step_by_step_mode,
                )
                message_id = save_message(
                    session_id,
                    "assistant",
                    complete_reply,
                    finish_reason=event.finish_reason,
                    continuation_allowed=can_continue,
                    sources=sources,
                    diagram=diagram,
                )
                if event.tokens_used:
                    log_tokens(session_id, event.tokens_used)
                total = get_total_tokens(session_id)
                yield format_stream_completion(
                    total,
                    event.finish_reason,
                    message_id=message_id,
                    session_id=session_id,
                    can_continue=can_continue,
                    sources=sources,
                    diagram=diagram,
                )

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/science/ask", methods=["POST"])
def science_ask():
    """Handle a science question from the user (non-streaming fallback)."""
    data, error = get_tutor_request()
    if error:
        return error
    user_message = get_json_text(data, "message")
    step_by_step_mode = data.get("step_by_step_mode", False)
    practice_mode = data.get("practice_mode", False)
    quiz_mode = data.get("quiz_mode", False)

    if not user_message:
        return jsonify({"error": "Please enter a question."}), 400
    if len(user_message) > 2000:
        return jsonify({"error": "Your question is too long. Please keep it under 2000 characters."}), 400

    session_id = get_session_id("science")
    save_message(session_id, "user", user_message, attachments=data.get("_processed_attachments"))
    if should_redirect_to_learning(user_message):
        message_id = save_message(
            session_id,
            "assistant",
            SCIENCE_SAFETY_REDIRECT_REPLY,
            finish_reason=FINISH_REASON_COMPLETE,
        )
        return jsonify({
            "reply": SCIENCE_SAFETY_REDIRECT_REPLY,
            "tokens_used": get_total_tokens(session_id),
            "finish_reason": FINISH_REASON_COMPLETE,
            "message_id": message_id,
            "session_id": session_id,
            "can_continue": False,
            "continuation_count": 0,
        })

    if should_redirect_science_math_tooling(user_message):
        message_id = save_message(
            session_id,
            "assistant",
            SCIENCE_MATH_TOOL_REDIRECT_REPLY,
            finish_reason=FINISH_REASON_COMPLETE,
        )
        return jsonify({
            "reply": SCIENCE_MATH_TOOL_REDIRECT_REPLY,
            "tokens_used": get_total_tokens(session_id),
            "finish_reason": FINISH_REASON_COMPLETE,
            "message_id": message_id,
            "session_id": session_id,
            "can_continue": False,
            "continuation_count": 0,
        })

    ai_config = get_active_ai_config()
    if not ai_config:
        return jsonify({"error": "Choose an AI provider and paste your API key first."}), 400

    sources = []
    diagram = build_science_diagram(user_message)
    messages_for_ai = _build_science_messages_for_ai(
        session_id,
        user_message,
        step_by_step_mode,
        practice_mode,
        quiz_mode,
        source_metadata=sources,
        diagram_spec=diagram,
    )

    ai_response = get_math_solution(
        messages_for_ai,
        system_prompt=SCIENCE_TUTOR_SYSTEM_PROMPT,
        ai_config=ai_config,
    )
    can_continue = continuation_is_available(
        ai_response.finish_reason,
        guided_mode=step_by_step_mode,
    )
    message_id = save_message(
        session_id,
        "assistant",
        ai_response.text,
        finish_reason=ai_response.finish_reason,
        continuation_allowed=can_continue,
        sources=sources,
        diagram=diagram,
    )
    log_tokens(session_id, ai_response.tokens_used)

    return jsonify({
        "reply": ai_response.text,
        "tokens_used": get_total_tokens(session_id),
        "finish_reason": ai_response.finish_reason,
        "message_id": message_id,
        "session_id": session_id,
        "can_continue": can_continue,
        "continuation_count": 0,
        "sources": sources,
        "diagram": diagram,
    })


@app.route("/responses/continue", methods=["POST"])
@app.route("/science/responses/continue", methods=["POST"])
def continue_response():
    """Continue one length-limited answer owned by the active tutor chat."""
    data, error = get_json_object()
    if error:
        return error

    mode = "science" if request.path.startswith("/science/") else "math"
    active_session_id = get_session_id(mode)
    requested_session_id = get_json_text(data, "session_id")
    if not requested_session_id:
        return jsonify({"error": "This response is missing its chat ID. Refresh and try again."}), 400
    if requested_session_id != active_session_id:
        return jsonify({"error": "That response does not belong to the active chat."}), 403

    raw_message_id = data.get("message_id")
    if isinstance(raw_message_id, bool) or not isinstance(raw_message_id, int) or raw_message_id <= 0:
        return jsonify({"error": "This response is missing a valid message ID."}), 400

    message = get_message_record(active_session_id, raw_message_id)
    if message is None:
        return jsonify({"error": "That response was not found."}), 404
    if message["role"] != "assistant":
        return jsonify({"error": "Only tutor responses can be continued."}), 409
    if message["finish_reason"] != FINISH_REASON_LENGTH or not message["can_continue"]:
        return jsonify({"error": "That response does not need to be continued."}), 409
    if message["continuation_count"] >= MAX_CONTINUATIONS_PER_ANSWER:
        return jsonify({"error": "This response has already used its continuation."}), 409

    ai_config = get_active_ai_config()
    if not ai_config:
        return jsonify({"error": "Choose an AI provider and paste your API key first."}), 400

    messages_for_ai = load_messages_through(active_session_id, raw_message_id)
    messages_for_ai = add_references(messages_for_ai, message.get("sources", []))
    messages_for_ai.append({
        "role": "user",
        "content": (
            "Continue the immediately preceding tutor response from the exact point where it stopped. "
            "Do not repeat the question, earlier steps, headings, or text already given. "
            "Start directly with the missing words or next step, keep the same language and level, "
            "and finish the explanation clearly."
        ),
    })
    system_prompt = SCIENCE_TUTOR_SYSTEM_PROMPT if mode == "science" else None
    if system_prompt is None:
        ai_response = get_math_solution(messages_for_ai, ai_config=ai_config)
    else:
        ai_response = get_math_solution(
            messages_for_ai,
            system_prompt=system_prompt,
            ai_config=ai_config,
        )

    if ai_response.finish_reason == FINISH_REASON_ERROR or not ai_response.text.strip():
        return jsonify({
            "error": "The AI provider could not continue this response. Please try again.",
        }), 502

    joined_reply = normalise_latex(
        join_continued_response(message["content"], ai_response.text)
    )
    next_count = message["continuation_count"] + 1
    can_continue = (
        ai_response.finish_reason == FINISH_REASON_LENGTH
        and next_count < MAX_CONTINUATIONS_PER_ANSWER
    )
    updated = replace_message_with_continuation(
        active_session_id,
        raw_message_id,
        joined_reply,
        ai_response.finish_reason,
        can_continue,
        MAX_CONTINUATIONS_PER_ANSWER,
    )
    if not updated:
        return jsonify({"error": "This response was already continued in another tab."}), 409

    if ai_response.tokens_used:
        log_tokens(active_session_id, ai_response.tokens_used)
    return jsonify({
        "reply": joined_reply,
        "tokens_used": get_total_tokens(active_session_id),
        "finish_reason": ai_response.finish_reason,
        "message_id": raw_message_id,
        "session_id": active_session_id,
        "can_continue": can_continue,
        "continuation_count": next_count,
        "sources": message.get("sources", []),
        "diagram": message.get("diagram"),
    })


@app.route("/plot", methods=["POST"])
def plot():
    """Return local-renderer graph data for a math function, points, or surface."""
    data, error = get_json_object()
    if error:
        return error
    user_message = get_json_text(data, "message")
    session_id = get_session_id()
    ai_config = get_active_ai_config()

    if not user_message:
        return jsonify({"error": "Please enter a function to plot."}), 400

    graph_error = None
    try:
        result = build_graph_spec(user_message)
    except GraphingError as error:
        result = None
        graph_error = str(error)

    # Multi-turn fallback: if no equation found, use last equation + AI resolver
    if result is None and graph_error is None:
        last_eq = get_last_equation(session_id)
        if last_eq and ai_config:
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
            ai_response = get_math_solution(resolver_messages, ai_config=ai_config)
            resolved_eq = ai_response.text.strip().strip("`").strip()
            try:
                result = build_graph_spec(f"plot {resolved_eq}")
            except GraphingError as error:
                graph_error = str(error)

    if result:
        if data.get("restore_only") is not True:
            save_last_equation(session_id, result.get("raw_expression") or result["equation_latex"], only_if_active=True)
        return jsonify(result)

    return jsonify({
        "error": graph_error
        or "I could not graph that yet. Try y = x^2 - 4, x^2 + y^2 = 25, r = 2sin(3theta), or z = x^2 + y^2."
    }), 400


@app.route("/local-graph-message", methods=["POST"])
def save_local_graph_message():
    """Save a local-only graph request when no AI provider is configured."""
    data, error = get_json_object()
    if error:
        return error
    user_message = get_json_text(data, "message")
    if not user_message:
        return jsonify({"error": "Please enter a function to plot."}), 400

    try:
        graph = build_graph_spec(user_message)
    except GraphingError as error:
        return jsonify({"error": str(error)}), 400
    if graph is None:
        return jsonify({"error": "Type a supported graph equation first."}), 400

    session_id = get_session_id()
    save_message(session_id, "user", user_message)
    save_message(session_id, "assistant", LOCAL_GRAPH_REPLY)
    return jsonify({
        "reply": LOCAL_GRAPH_REPLY,
        "tokens_used": get_total_tokens(session_id),
        "finish_reason": FINISH_REASON_COMPLETE,
    })


@app.route("/images", methods=["GET"])
def generated_images_list():
    """List this browser owner's generated images for the active tutor chat."""
    tutor_area = request.args.get("area", "math").strip().lower()
    if tutor_area not in {"math", "science"}:
        return jsonify({"error": "Choose the Math or Science image area."}), 400
    session_id = get_session_id(tutor_area)
    return jsonify({
        "session_id": session_id,
        "images": get_public_images_for_session(session_id),
    })


def _image_request_result(
    request_id: str,
    owner_id: str,
    session_id: str,
) -> tuple[dict, int] | None:
    with IMAGE_REQUEST_LOCK:
        record = IMAGE_REQUESTS_BY_ID.get(request_id)
        if (
            record
            and record.get("owner_id") == owner_id
            and record.get("session_id") == session_id
            and record.get("state") == "finished"
        ):
            finished = dict(record)
        else:
            return None
    return _validated_image_request_result(finished)


def _validated_image_request_result(record: dict) -> tuple[dict, int]:
    payload, status = dict(record["payload"]), int(record["status"])
    if status == 201:
        try:
            stored = read_generated_image(
                payload["image"]["id"],
                owner_id=record["owner_id"],
                storage_root=get_generated_image_storage_root(),
            )
        except ImageStorageError:
            return {"error": "Delphic could not check the saved image. Try again later; no new image was created."}, 503
        if stored is None or stored.record["session_id"] != record["session_id"]:
            return {"error": "This request's saved image is no longer available. Start a new image request to create another."}, 410
    return payload, status


def _finish_image_request(request_id: str, payload: dict, status: int) -> None:
    with IMAGE_REQUEST_LOCK:
        record = IMAGE_REQUESTS_BY_ID.get(request_id)
        if record is not None:
            record.update(state="finished", payload=dict(payload), status=status)


def _claim_image_request(
    request_id: str,
    owner_id: str,
    session_id: str,
) -> tuple[dict, int] | None:
    now = time.monotonic()
    with IMAGE_REQUEST_LOCK:
        expired = [
            key for key, value in IMAGE_REQUESTS_BY_ID.items()
            if now - float(value.get("created_at", 0)) >= IMAGE_REQUEST_TTL_SECONDS
        ]
        for key in expired:
            IMAGE_REQUESTS_BY_ID.pop(key, None)

        existing = IMAGE_REQUESTS_BY_ID.get(request_id)
        if existing is not None:
            if existing.get("owner_id") != owner_id or existing.get("session_id") != session_id:
                return {"error": "That image request ID is already in use."}, 409
            if existing.get("state") == "finished":
                return _validated_image_request_result(existing)
            return {"error": "That image is already being created."}, 409

        chat_key = (owner_id, session_id)
        last_started = IMAGE_LAST_REQUEST_BY_CHAT.get(chat_key)
        if last_started is not None and now - last_started < IMAGE_REQUEST_COOLDOWN_SECONDS:
            wait_seconds = max(1, int(IMAGE_REQUEST_COOLDOWN_SECONDS - (now - last_started) + 0.999))
            return {"error": f"Wait {wait_seconds} seconds before creating another image."}, 429

        IMAGE_LAST_REQUEST_BY_CHAT[chat_key] = now
        IMAGE_REQUESTS_BY_ID[request_id] = {
            "owner_id": owner_id,
            "session_id": session_id,
            "created_at": now,
            "state": "processing",
        }
    return None


@app.route("/images/generate", methods=["POST"])
def generate_image():
    """Generate, review, sanitize, and save one private development image."""
    if not IMAGE_GENERATION_ENABLED:
        return jsonify({
            "error": "Experimental image generation is not enabled in this Delphic installation."
        }), 403

    data, error = get_json_object()
    if error:
        return error
    allowed_fields = {"prompt", "mode", "area", "request_id"}
    if set(data) - allowed_fields:
        return jsonify({"error": "The image request contains an unsupported field."}), 400

    prompt = get_json_text(data, "prompt")
    mode = get_json_text(data, "mode")
    area = get_json_text(data, "area").lower()
    raw_request_id = get_json_text(data, "request_id")
    if area not in {"math", "science"}:
        return jsonify({"error": "Choose the Math or Science image area."}), 400
    try:
        request_id = str(uuid.UUID(raw_request_id))
    except ValueError:
        return jsonify({"error": "Start a new image request and try again."}), 400

    session_id = get_session_id(area)
    owner_id = get_image_owner_id()
    cached = _image_request_result(request_id, owner_id, session_id)
    if cached is not None:
        payload, status = cached
        return jsonify(payload), status

    active_config = get_active_ai_config()
    if not active_config or active_config.get("provider") != "openrouter":
        return jsonify({
            "error": "Choose OpenRouter in AI Settings and add its API key before creating an image."
        }), 400

    stored_image_id = None
    try:
        current_images = list_session_images(owner_id, session_id)
    except ImageStorageError:
        return jsonify({"error": "Delphic could not check this chat's image limit."}), 500
    if len(current_images) >= MAX_IMAGE_REQUESTS_PER_CHAT:
        return jsonify({
            "error": f"This chat has reached its limit of {MAX_IMAGE_REQUESTS_PER_CHAT} images."
        }), 429

    claim_error = _claim_image_request(request_id, owner_id, session_id)
    if claim_error is not None:
        payload, status = claim_error
        return jsonify(payload), status

    image_payload = {
        "version": 1,
        "mode": mode,
        "subject": area,
        "main_subject": prompt[:300],
        "required_objects": [],
        "relationships": [],
        "required_text": [],
        "style": {
            "educational_visual": "clear textbook illustration",
            "realistic_image": "realistic educational image",
            "creative_illustration": "colorful educational illustration",
        }.get(mode, ""),
        "view": "clear centered view",
        "colors": [],
        "avoid": ["unrequested text", "watermarks"],
        "aspect_ratio": "1:1",
        "student_prompt": prompt,
    }

    try:
        generator = OpenRouterImageGenerationProvider(
            active_config["api_key"],
            model_id=active_config.get("image_model", OPENROUTER_IMAGE_MODEL),
        )
        reviewer = OpenRouterImageReviewProvider(active_config["api_key"])
        result = generate_checked_image(
            image_payload,
            generator,
            reviewer,
        )
        record = store_generated_image(
            result,
            owner_id=owner_id,
            session_id=session_id,
            storage_root=get_generated_image_storage_root(),
        )
        stored_image_id = record["id"]
        save_message(session_id, "user", prompt)
        assistant_text = "Here is the AI-generated image. Check important details before using it."
        if not result.review.passed:
            assistant_text += " The accuracy review found a detail that may still need correction."
        message_id = save_message(
            session_id,
            "assistant",
            assistant_text,
            finish_reason=FINISH_REASON_COMPLETE,
        )
        if not set_generated_image_message_id(record["id"], owner_id, message_id):
            raise ImageStorageError("Delphic could not attach the image to this chat.")
        record["message_id"] = message_id
        total_cost = sum(
            (attempt.generation_cost_usd or 0) + (attempt.review_cost_usd or 0)
            for attempt in result.attempts
        )
        payload = {
            "session_id": session_id,
            "message": {
                "id": message_id,
                "role": "assistant",
                "content": assistant_text,
                "finish_reason": FINISH_REASON_COMPLETE,
            },
            "image": public_image_metadata(record),
            "attempt_count": result.attempt_count,
            "review_passed": result.review.passed,
            "cost_usd": round(total_cost, 6),
        }
        _finish_image_request(request_id, payload, 201)
        return jsonify(payload), 201
    except (ImageValidationError, ImageSafetyError) as generation_error:
        payload = {"error": str(generation_error)}
        status = 400
    except ImageGenerationError as generation_error:
        payload = {"error": str(generation_error)}
        status = 502
    except ImageStorageError:
        payload = {"error": "Delphic created the image but could not save it safely."}
        status = 500
    except Exception:
        app.logger.exception("Unexpected image generation failure")
        payload = {"error": "Delphic could not complete this image request."}
        status = 500

    if stored_image_id is not None:
        try:
            delete_stored_image(
                stored_image_id,
                owner_id=owner_id,
                storage_root=get_generated_image_storage_root(),
            )
        except ImageStorageError:
            pass

    _finish_image_request(request_id, payload, status)
    return jsonify(payload), status


@app.route("/images/<image_id>", methods=["GET", "DELETE"])
def generated_image_file(image_id: str):
    """Read, download, or delete one generated image only for its owner."""
    owner_id = get_image_owner_id()
    record = get_generated_image_record(image_id, owner_id)
    mode = "science" if record and record["session_id"].startswith("science:") else "math"
    if not record or not chat_session_is_owned(record["session_id"], owner_id, mode):
        return jsonify({"error": "That image was not found."}), 404
    storage_root = get_generated_image_storage_root()

    try:
        if request.method == "DELETE":
            deleted = delete_stored_image(
                image_id,
                owner_id=owner_id,
                storage_root=storage_root,
            )
            if not deleted:
                return jsonify({"error": "That image was not found."}), 404
            return jsonify({"deleted_image_id": image_id})

        stored = read_generated_image(
            image_id,
            owner_id=owner_id,
            storage_root=storage_root,
        )
    except ImageStorageError:
        return jsonify({"error": "That image was not found."}), 404

    if stored is None:
        return jsonify({"error": "That image was not found."}), 404

    response = Response(stored.data, mimetype=stored.record["mime_type"])
    response.headers["Cache-Control"] = "private, no-store"
    if request.args.get("download") == "1":
        filename = safe_image_download_name(
            stored.record["prompt"],
            stored.record["mime_type"],
        )
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@app.route("/clear", methods=["POST"])
def clear():
    """Clear conversation history."""
    session_id = get_session_id()
    delete_generated_images_for_chat(session_id)
    clear_messages(session_id)
    return jsonify({"status": "ok"})


@app.route("/science/clear", methods=["POST"])
def science_clear():
    """Clear science conversation history."""
    session_id = get_session_id("science")
    delete_generated_images_for_chat(session_id)
    clear_messages(session_id)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(host="127.0.0.1", debug=FLASK_DEBUG, port=port, use_reloader=False)
