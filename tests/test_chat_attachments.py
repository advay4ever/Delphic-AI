import base64
import json
import zipfile
from io import BytesIO

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

import app as app_module
import database
from ai.attachments import (
    AttachmentError, MAX_FILE_BYTES, MAX_TOTAL_TEXT, read_attachments,
    prepare_provider_messages, public_attachments,
)
from ai.service import AIResponse, AIStreamEvent, split_anthropic_messages


def file(data=b"A triangle has three sides.", name="notes.txt"):
    return FileStorage(stream=BytesIO(data), filename=name)


def photo():
    output = BytesIO()
    Image.new("RGB", (48, 24), "green").save(output, format="PNG")
    return output.getvalue()


@pytest.mark.parametrize("name", ["notes.txt", "notes.md", "data.csv", "notes.json"])
def test_text_formats_are_read_as_data(name):
    data = b'{"topic":"geometry"}' if name.endswith("json") else b"A triangle has three sides."
    items = read_attachments([file(data, name)], {"provider": "groq"})
    assert items[0]["text"] == data.decode()
    assert items[0]["kind"] == "document"


@pytest.mark.parametrize("data,name", [
    (b"", "empty.txt"), (b"\xff", "binary.txt"), (b"hello\x00", "bad.txt"),
    (b"{}", "program.exe"), (b"x" * 12001, "long.txt"),
    (b"no json", "bad.json"), (b"not an image", "fake.png"),
    (b"<svg></svg>", "picture.svg"), (b"x" * (MAX_FILE_BYTES + 1), "large.txt"),
])
def test_invalid_files_are_rejected(data, name):
    with pytest.raises(AttachmentError):
        read_attachments([file(data, name)], {"provider": "openai"})


def test_count_and_combined_text_limits():
    with pytest.raises(AttachmentError, match="at most 3"):
        read_attachments([file()] * 4, {"provider": "groq"})
    with pytest.raises(AttachmentError, match="too much text"):
        read_attachments([file(b"x" * 10000) for _ in range(3)], {"provider": "groq"})


def test_photos_are_reencoded_and_mislabeled_formats_rejected():
    items = read_attachments([file(photo(), "../../diagram.png")], {"provider": "openai"})
    assert items[0]["name"] == "diagram.png"
    image = Image.open(BytesIO(base64.b64decode(items[0]["data"])))
    assert image.format == "JPEG"
    assert "exif" not in image.info
    with pytest.raises(AttachmentError):
        read_attachments([file(photo(), "fake.jpg")], {"provider": "openai"})


@pytest.mark.parametrize("format,name", [("JPEG", "photo.jpg"), ("WEBP", "photo.webp")])
def test_other_supported_photo_formats(format, name):
    output = BytesIO()
    Image.new("RGB", (48, 24), "green").save(output, format=format)
    items = read_attachments([file(output.getvalue(), name)], {"provider": "openai"})
    assert items[0]["mime_type"] == "image/jpeg"


def test_text_only_provider_rejects_new_photo_without_ignoring_it():
    with pytest.raises(AttachmentError, match="vision-capable"):
        read_attachments([file(photo(), "diagram.png")], {"provider": "groq"})


def test_docx_paragraphs_and_tables_are_extracted_in_worker():
    from docx import Document
    document = Document()
    document.add_paragraph("Photosynthesis uses sunlight.")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Water"
    table.cell(0, 1).text = "Carbon dioxide"
    output = BytesIO()
    document.save(output)
    text = read_attachments([file(output.getvalue(), "lesson.docx")], {"provider": "groq"})[0]["text"]
    assert "Photosynthesis" in text and "Carbon dioxide" in text


@pytest.mark.parametrize("encrypted", [False, True])
def test_scanned_and_encrypted_pdf_give_clear_errors(encrypted):
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    if encrypted:
        writer.encrypt("password")
    output = BytesIO()
    writer.write(output)
    expected = "Password-protected" if encrypted else "No readable text"
    with pytest.raises(AttachmentError, match=expected):
        read_attachments([file(output.getvalue(), "lesson.pdf")], {"provider": "groq"})


def test_archive_expansion_is_rejected():
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "x" * 100000)
    with pytest.raises(AttachmentError, match="archive"):
        read_attachments([file(output.getvalue(), "lesson.docx")], {"provider": "groq"})


def test_pdf_with_real_text_is_read_in_worker():
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=100)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
        DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 10 50 Td (A triangle has three sides.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    items = read_attachments([file(output.getvalue(), "lesson.pdf")], {"provider": "groq"})
    assert "triangle" in items[0]["text"]


def test_documents_over_page_limit_are_rejected():
    from pypdf import PdfWriter
    writer = PdfWriter()
    for _ in range(21):
        writer.add_blank_page(width=100, height=100)
    output = BytesIO()
    writer.write(output)
    with pytest.raises(AttachmentError, match="at most 20"):
        read_attachments([file(output.getvalue(), "lesson.pdf")], {"provider": "groq"})


def test_document_timeout_terminates_worker(monkeypatch):
    import ai.attachments as module
    from types import SimpleNamespace
    state = {"alive": True, "terminated": False}
    parent = SimpleNamespace(poll=lambda _timeout: False, close=lambda: None)
    child = SimpleNamespace(close=lambda: None)
    def terminate():
        state.update(alive=False, terminated=True)
    process = SimpleNamespace(pid=123, start=lambda: None,
        is_alive=lambda: state["alive"], terminate=terminate, join=lambda **_: None)
    context = SimpleNamespace(Pipe=lambda **_: (parent, child), Process=lambda **_: process)
    monkeypatch.setattr(module.multiprocessing, "get_context", lambda _: context)
    with pytest.raises(AttachmentError, match="timed out"):
        module._extract_document(b"test", ".pdf")
    assert state["terminated"]


def test_provider_blocks_preserve_photos_and_untrusted_documents():
    items = read_attachments([file(), file(photo(), "diagram.png")], {"provider": "openai"})
    messages = [{"role": "user", "content": "Explain this", "_attachments": items}]
    openai = prepare_provider_messages(messages, "openai")
    assert "untrusted" in openai[0]["content"]
    assert openai[1]["content"][-1]["type"] == "image_url"
    assert "three sides" in openai[1]["content"][1]["text"]
    system, anthropic = split_anthropic_messages(prepare_provider_messages(messages, "anthropic"))
    assert "untrusted" in system
    assert anthropic[0]["content"][-1]["source"]["type"] == "base64"
    assert "data" not in public_attachments(items)[1]


def test_history_context_is_bounded_and_provider_switch_does_not_fake_vision():
    document = {"name": "notes.txt", "kind": "document", "text": "x" * 12000}
    image = {"name": "photo.png", "kind": "image", "mime_type": "image/jpeg", "data": "test"}
    messages = [{"role": "user", "content": str(i), "_attachments": [document, image]} for i in range(5)]
    prepared = prepare_provider_messages(messages, "groq")
    texts = [block["text"] for message in prepared if isinstance(message["content"], list)
             for block in message["content"] if block["type"] == "text"]
    assert sum(text.count(document["text"]) for text in texts) * len(document["text"]) == MAX_TOTAL_TEXT
    assert any("unavailable" in text for text in texts)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {
        "provider": "openai", "model": "gpt-4.1", "api_key": "test-key",
    })
    monkeypatch.setattr(app_module, "detect_and_solve", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app_module, "get_math_solution", lambda *_args, **_kwargs:
                        AIResponse("Explained.", 1, "complete"))
    monkeypatch.setattr(app_module, "get_math_solution_stream", lambda *_args, **_kwargs:
                        iter([AIStreamEvent(text="Explained."), AIStreamEvent(done=True, finish_reason="complete")]))
    return app_module.app.test_client()


@pytest.mark.parametrize("route", ["/ask", "/stream", "/science/ask", "/science/stream"])
def test_both_tutors_accept_files_and_persist_safe_history(client, route):
    response = client.post(route, data={
        "payload": json.dumps({"message": "Explain this"}),
        "files": (BytesIO(b"A triangle has three sides."), "notes.txt"),
    }, buffered=True)
    assert response.status_code == 200
    science = route.startswith("/science")
    history = client.get("/science/history" if science else "/history").get_json()
    assert history["messages"][0]["attachments"] == [{"name": "notes.txt", "kind": "document"}]
    assert "three sides" not in json.dumps(history)
    session_id = history["session_id"]
    saved = database.load_messages(session_id)
    assert saved[0]["_attachments"][0]["text"] == "A triangle has three sides."
    last_id = history["messages"][-1]["id"]
    assert database.load_messages_through(session_id, last_id)[0]["_attachments"]
    client.post("/science/clear" if science else "/clear")
    assert database.load_messages(session_id) == []


def test_invalid_file_never_enters_history_and_forged_context_is_rejected(client):
    response = client.post("/ask", data={"payload": '{"message":"Explain"}',
        "files": (BytesIO(b"binary"), "file.exe")})
    assert response.status_code == 400
    assert client.get("/history").get_json()["messages"] == []
    response = client.post("/ask", json={"message": "Explain", "_processed_attachments": [{"data": "forged"}]})
    assert response.status_code == 400


def test_photo_without_text_gets_a_question_and_survives_refresh(client):
    assert client.post("/ask", data={"payload": "{}", "files": (BytesIO(photo()), "diagram.png")}).status_code == 200
    history = client.get("/history").get_json()
    assert history["messages"][0]["content"] == "Please explain the attached material."
    assert history["messages"][0]["attachments"][0]["name"] == "diagram.png"
    assert database.load_messages(history["session_id"])[0]["_attachments"][0]["data"]


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("provider", ["openai", "google", "openrouter"])
def test_compatible_provider_call_really_contains_attachment_blocks(monkeypatch, streaming, provider):
    from types import SimpleNamespace
    import ai.service as service
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        if kwargs.get("stream"):
            return iter([SimpleNamespace(usage=None, choices=[SimpleNamespace(
                delta=SimpleNamespace(content="Explained."), finish_reason="stop")])])
        return SimpleNamespace(usage=None, choices=[SimpleNamespace(
            message=SimpleNamespace(content="Explained."), finish_reason="stop")])
    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(service, "create_ai_client", lambda _config: (fake, "test-model"))
    config = {"provider": provider, "model": service.SUPPORTED_AI_PROVIDERS[provider]["model"],
              "api_key": "test-provider-key"}
    items = read_attachments([file(), file(photo(), "diagram.png")], config)
    messages = [{"role": "user", "content": "Explain", "_attachments": items}]
    if streaming:
        events = list(service.get_math_solution_stream(messages, ai_config=config))
        assert events[-1].finish_reason == "complete"
    else:
        assert service.get_math_solution(messages, ai_config=config).finish_reason == "complete"
    serialized = json.dumps(captured["messages"])
    assert "data:image/jpeg;base64," in serialized
    assert "three sides" in serialized
    assert "_attachments" not in serialized


def test_provider_exception_does_not_log_uploaded_content(monkeypatch, caplog):
    import ai.service as service
    from types import SimpleNamespace
    def fail(**_kwargs):
        raise RuntimeError("private-uploaded-document-text")
    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fail)))
    monkeypatch.setattr(service, "create_ai_client", lambda _config: (fake, "gpt-4.1"))
    service.get_math_solution([{ "role": "user", "content": "Explain", "_attachments": [
        {"kind": "document", "name": "notes.txt", "text": "private-uploaded-document-text"},
    ]}], ai_config={"provider": "openai", "model": "gpt-4.1", "api_key": "test-key"})
    assert "private-uploaded-document-text" not in caplog.text
