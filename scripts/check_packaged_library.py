"""Exercise a desktop executable using disposable data and no provider calls."""

import argparse
from contextlib import contextmanager
from http.cookiejar import CookieJar
from io import BytesIO
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener


MATH = "Linear equations keep equality balanced. Subtract the same number from both sides of an equation to solve for a variable."
SCIENCE = "Photosynthesis allows plants to use sunlight energy and carbon dioxide to make sugars. Chloroplasts in plant cells perform this process."


def sample_pdf():
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=200)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
        DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 10 100 Td (A triangle has three sides. Geometry studies shapes.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class Browser:
    def __init__(self, base):
        self.base = base
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self, path, method="GET", data=None, content_type="application/json", expected=200):
        if isinstance(data, dict):
            data = json.dumps(data).encode()
        request = Request(self.base + path, data=data, method=method)
        if data is not None:
            request.add_header("Content-Type", content_type)
        try:
            response = self.opener.open(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            if response.status != expected:
                raise RuntimeError(f"{method} {path}: expected {expected}, received {response.status}")
            if "application/json" in response.headers.get("Content-Type", ""):
                return json.loads(body)
            return body.decode()

    def preview(self, name, content):
        boundary = "delphic-library-smoke-boundary"
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        return self.request("/library/preview", "POST", body, f"multipart/form-data; boundary={boundary}")


@contextmanager
def running_app(executable, directory, port):
    env = os.environ.copy()
    # A package check must never inherit a developer's provider credentials.
    for name in list(env):
        if name.endswith("API_KEY") or name in {"DELPHIC_ENV_FILE", "FLASK_SECRET_KEY"}:
            env.pop(name)
    env.update(DELPHIC_DATA_DIR=str(directory / "data"), DELPHIC_OPEN_BROWSER="false",
               DELPHIC_HEADLESS="true", FLASK_DEBUG="false", PORT=str(port))
    with (directory / "startup.log").open("ab") as log:
        process = subprocess.Popen([str(executable)], cwd=directory, env=env, stdout=log, stderr=log)
        try:
            probe = Browser(f"http://127.0.0.1:{port}")
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Packaged app exited before it was ready; inspect the build environment.")
                try:
                    probe.request("/")
                    break
                except (URLError, TimeoutError, ConnectionError):
                    time.sleep(0.25)
            else:
                raise RuntimeError("Packaged app did not become ready within 90 seconds.")
            yield
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


def check(executable, port):
    # Refuse occupied ports so an existing student's app cannot be tested by mistake.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
    with tempfile.TemporaryDirectory(prefix="delphic-library-package-") as name:
        directory = Path(name)
        browser = Browser(f"http://127.0.0.1:{port}")
        with running_app(executable, directory, port):
            for page in ["/", "/science"]:
                assert "studyLibraryDialog" in browser.request(page)
            for asset in ["study-library.js", "study-library.css"]:
                assert browser.request("/static/" + asset).strip()
            assert browser.request("/library/notes")["notes"] == []
            assert browser.preview("notes.txt", MATH.encode())["text"] == MATH
            for extension, content in [("md", "# Algebra\n" + MATH), ("csv", "topic,description\nalgebra," + MATH),
                                       ("json", json.dumps({"algebra": MATH}))]:
                assert MATH in browser.preview("notes." + extension, content.encode())["text"]
            assert "triangle" in browser.preview("notes.pdf", sample_pdf())["text"]
            from docx import Document
            document = Document()
            document.add_paragraph(SCIENCE)
            buffer = BytesIO()
            document.save(buffer)
            assert SCIENCE in browser.preview("notes.docx", buffer.getvalue())["text"]
            assert browser.request("/library/notes")["notes"] == []
            ids = []
            for subject, text in [("math", MATH), ("science", SCIENCE), ("both", MATH + SCIENCE)]:
                result = browser.request("/library/notes", "POST", {
                    "title": subject + " test notes", "subject": subject, "text": text, "enabled": True,
                }, expected=201)
                ids.append(result["id"])
            for subject in ["math", "science"]:
                assert browser.request("/library/status?subject=" + subject)["enabled_count"] == 2
            endpoint = "/library/notes/" + ids[0]
            browser.request(endpoint, "PATCH", {"title": "Renamed equations", "enabled": False})
            assert browser.request("/library/status?subject=math")["enabled_count"] == 1
            stranger = Browser(browser.base)
            assert stranger.request("/library/notes")["notes"] == []
            stranger.request(endpoint, "PATCH", {"title": "Wrong owner"}, expected=404)
            stranger.request(endpoint, "DELETE", expected=404)
            browser.request(endpoint, "PATCH", {}, expected=400)
            print("PASS: bundled pages/assets, all six document formats, save, rename, selection, subjects, owner isolation", flush=True)
        with running_app(executable, directory, port):
            notes = browser.request("/library/notes")["notes"]
            assert len(notes) == 3
            renamed = next(note for note in notes if note["id"] == ids[0])
            assert renamed["title"] == "Renamed equations" and not renamed["enabled"]
            assert renamed["text"] == MATH
            for note_id in ids:
                browser.request("/library/notes/" + note_id, "DELETE")
            assert browser.request("/library/notes")["notes"] == []
            assert browser.request("/library/status?subject=math")["enabled_count"] == 0
            print("PASS: notes and browser ownership survive restart; deletion clears future selection", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--port", type=int, default=51274)
    args = parser.parse_args()
    executable = args.executable.resolve()
    if not executable.is_file():
        parser.error("The packaged executable does not exist.")
    check(executable, args.port)


if __name__ == "__main__":
    main()
