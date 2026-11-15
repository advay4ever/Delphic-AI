import json
import os
import sqlite3
import time
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

import app as app_module
import database
import images.storage as image_storage
from images import generate_checked_image
from images.providers import FakeImageGenerationProvider, FakeImageReviewProvider
from images.storage import (
    ImageStorageError,
    delete_generated_image,
    delete_session_images,
    get_image_storage_root,
    list_session_images,
    public_image_metadata,
    read_generated_image,
    remove_orphaned_image_files,
    safe_image_download_name,
    store_generated_image,
)


def image_payload(prompt="Show five red blood cells inside a capillary"):
    return {
        "version": 1,
        "mode": "educational_visual",
        "subject": "science",
        "main_subject": "red blood cells inside a capillary",
        "required_objects": [{"name": "red blood cell", "count": 5}],
        "relationships": ["the cells are inside the capillary"],
        "required_text": [],
        "style": "clear textbook illustration",
        "view": "side view",
        "colors": ["red cells"],
        "avoid": ["extra cells"],
        "aspect_ratio": "4:3",
        "student_prompt": prompt,
    }


def fake_result(prompt="Show five red blood cells inside a capillary"):
    return generate_checked_image(
        image_payload(prompt),
        FakeImageGenerationProvider(),
        FakeImageReviewProvider(),
    )


@pytest.fixture
def private_image_database(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "chat.db"))
    database.init_db()
    return get_image_storage_root(tmp_path)


def test_database_migration_adds_generated_images_table(monkeypatch, tmp_path):
    db_path = tmp_path / "old-chat.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT)"
        )
    monkeypatch.setattr(database, "DB_PATH", str(db_path))

    database.init_db()

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(generated_images)").fetchall()
        }
    assert {
        "id",
        "owner_id",
        "session_id",
        "message_id",
        "local_filename",
        "image_request_json",
        "review_json",
    } <= columns


def test_stores_bytes_outside_sqlite_and_reads_them_for_the_owner(private_image_database):
    owner_id = str(uuid.uuid4())
    session_id = f"science:{uuid.uuid4()}"

    record = store_generated_image(
        fake_result(),
        owner_id=owner_id,
        session_id=session_id,
        storage_root=private_image_database,
    )
    stored = read_generated_image(
        record["id"],
        owner_id=owner_id,
        storage_root=private_image_database,
    )

    assert stored is not None
    assert stored.data.startswith(b"\x89PNG\r\n\x1a\n")
    assert stored.record["owner_id"] == owner_id
    assert stored.record["session_id"] == session_id
    image_path = private_image_database / owner_id / record["local_filename"]
    assert image_path.is_file()
    if os.name != "nt":
        assert image_path.stat().st_mode & 0o777 == 0o600


def test_storage_rejects_unsafe_results_before_writing(private_image_database):
    result = fake_result()
    unsafe = replace(result, review=replace(result.review, passed=False, safety_problem=True))
    with pytest.raises(ImageStorageError, match="student safety check"):
        store_generated_image(
            unsafe,
            owner_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            storage_root=private_image_database,
        )
    assert not private_image_database.exists()


@pytest.mark.parametrize("review", [
    {"passed": False, "safety_problem": True},
    {"passed": True, "safety_problem": "false"},
    {},
])
def test_old_unsafe_or_unreviewed_records_are_hidden(private_image_database, monkeypatch, review):
    owner_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    record = store_generated_image(
        fake_result(), owner_id=owner_id, session_id=session_id,
        storage_root=private_image_database,
    )
    with sqlite3.connect(database.DB_PATH) as connection:
        connection.execute(
            "UPDATE generated_images SET review_json = ? WHERE id = ?",
            (json.dumps(review), record["id"]),
        )
    assert read_generated_image(
        record["id"], owner_id=owner_id, storage_root=private_image_database,
    ) is None
    assert list_session_images(owner_id, session_id) == []
    with pytest.raises(ImageStorageError):
        public_image_metadata({**record, "review": review})

    monkeypatch.setattr(app_module, "get_image_owner_id", lambda: owner_id)
    monkeypatch.setattr(app_module, "get_generated_image_storage_root", lambda: private_image_database)
    client = app_module.app.test_client()
    assert client.get(f"/images/{record['id']}").status_code == 404
    assert client.get(f"/images/{record['id']}?download=1").status_code == 404


def test_another_owner_cannot_read_list_or_delete_an_image(private_image_database):
    owner_id = str(uuid.uuid4())
    other_owner = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    record = store_generated_image(
        fake_result(),
        owner_id=owner_id,
        session_id=session_id,
        storage_root=private_image_database,
    )

    assert read_generated_image(
        record["id"], owner_id=other_owner, storage_root=private_image_database
    ) is None
    assert list_session_images(other_owner, session_id) == []
    assert not delete_generated_image(
        record["id"], owner_id=other_owner, storage_root=private_image_database
    )
    assert read_generated_image(
        record["id"], owner_id=owner_id, storage_root=private_image_database
    ) is not None


def test_public_metadata_never_exposes_private_paths_or_internal_provider_prompt(
    private_image_database,
):
    owner_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    record = store_generated_image(
        fake_result(),
        owner_id=owner_id,
        session_id=session_id,
        storage_root=private_image_database,
    )

    public = public_image_metadata(record)

    assert public["url"] == f"/images/{record['id']}"
    assert public["review_passed"] is True
    assert "owner_id" not in public
    assert "local_filename" not in public
    assert "provider" not in public
    assert "model" not in public
    assert "image_request" not in public


def test_deleting_one_image_removes_its_record_and_file(private_image_database):
    owner_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    record = store_generated_image(
        fake_result(),
        owner_id=owner_id,
        session_id=session_id,
        storage_root=private_image_database,
    )
    target = private_image_database / owner_id / record["local_filename"]

    assert delete_generated_image(
        record["id"], owner_id=owner_id, storage_root=private_image_database
    )
    assert not target.exists()
    assert database.get_generated_image_record(record["id"], owner_id) is None


def test_deleting_a_chat_removes_only_that_chats_images(private_image_database):
    owner_id = str(uuid.uuid4())
    first_session = str(uuid.uuid4())
    second_session = str(uuid.uuid4())
    first = store_generated_image(
        fake_result("First image"),
        owner_id=owner_id,
        session_id=first_session,
        storage_root=private_image_database,
    )
    second = store_generated_image(
        fake_result("Second image"),
        owner_id=owner_id,
        session_id=second_session,
        storage_root=private_image_database,
    )

    assert delete_session_images(
        owner_id=owner_id,
        session_id=first_session,
        storage_root=private_image_database,
    ) == 1
    assert read_generated_image(
        first["id"], owner_id=owner_id, storage_root=private_image_database
    ) is None
    assert read_generated_image(
        second["id"], owner_id=owner_id, storage_root=private_image_database
    ) is not None


def test_corrupted_or_path_tampered_records_are_not_served(private_image_database):
    owner_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corrupted = store_generated_image(
        fake_result(),
        owner_id=owner_id,
        session_id=session_id,
        storage_root=private_image_database,
    )
    target = private_image_database / owner_id / corrupted["local_filename"]
    target.write_bytes(b"not an image")

    assert read_generated_image(
        corrupted["id"], owner_id=owner_id, storage_root=private_image_database
    ) is None

    valid = store_generated_image(
        fake_result(),
        owner_id=owner_id,
        session_id=session_id,
        storage_root=private_image_database,
    )
    with database.get_connection() as connection:
        connection.execute(
            "UPDATE generated_images SET local_filename = ? WHERE id = ?",
            ("../../outside.png", valid["id"]),
        )
    assert read_generated_image(
        valid["id"], owner_id=owner_id, storage_root=private_image_database
    ) is None


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink permissions vary")
def test_owner_directory_symlink_is_never_followed(private_image_database, tmp_path):
    owner_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    record = store_generated_image(
        fake_result(),
        owner_id=owner_id,
        session_id=session_id,
        storage_root=private_image_database,
    )
    owner_dir = private_image_database / owner_id
    original_dir = tmp_path / "original-owner-files"
    owner_dir.rename(original_dir)
    owner_dir.symlink_to(original_dir, target_is_directory=True)

    assert read_generated_image(
        record["id"], owner_id=owner_id, storage_root=private_image_database
    ) is None


def test_database_failure_removes_the_untracked_image_file(
    monkeypatch,
    private_image_database,
):
    owner_id = str(uuid.uuid4())

    def fail_to_save(**_kwargs):
        raise sqlite3.OperationalError("database unavailable")

    monkeypatch.setattr(image_storage, "save_generated_image_record", fail_to_save)

    with pytest.raises(ImageStorageError, match="could not save"):
        store_generated_image(
            fake_result(),
            owner_id=owner_id,
            session_id=str(uuid.uuid4()),
            storage_root=private_image_database,
        )

    owner_dir = private_image_database / owner_id
    assert list(owner_dir.iterdir()) == []


def test_old_orphans_are_removed_but_recent_and_unrelated_files_remain(
    private_image_database,
):
    owner_id = str(uuid.uuid4())
    owner_dir = private_image_database / owner_id
    owner_dir.mkdir(parents=True)
    old_orphan = owner_dir / f"{uuid.uuid4().hex}.png"
    fresh_orphan = owner_dir / f"{uuid.uuid4().hex}.png"
    unrelated = owner_dir / "keep-me.txt"
    for path in (old_orphan, fresh_orphan, unrelated):
        path.write_bytes(b"test")
    old_time = time.time() - image_storage.ORPHAN_GRACE_SECONDS - 10
    os.utime(old_orphan, (old_time, old_time))

    removed = remove_orphaned_image_files(
        owner_id=owner_id,
        storage_root=private_image_database,
    )

    assert removed == 1
    assert not old_orphan.exists()
    assert fresh_orphan.exists()
    assert unrelated.exists()


def test_download_filename_is_ascii_and_cannot_inject_headers():
    name = safe_image_download_name('Plant cell\r\nBad: "header"', "image/png")

    assert name == "delphic-plant-cell-bad-header.png"
    assert "\r" not in name and "\n" not in name


def test_image_routes_restore_download_and_protect_owner(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "routes.db"))
    monkeypatch.setenv("DELPHIC_DATA_DIR", str(tmp_path))
    database.init_db()
    owner_id = str(uuid.uuid4())
    other_owner = str(uuid.uuid4())
    session_id = database.create_chat_session(owner_id, "math")
    root = get_image_storage_root(tmp_path)
    record = store_generated_image(
        fake_result(),
        owner_id=owner_id,
        session_id=session_id,
        storage_root=root,
    )

    owner_client = app_module.app.test_client()
    with owner_client.session_transaction() as browser_session:
        browser_session["chat_owner_id"] = owner_id
        browser_session["session_id"] = session_id
    other_client = app_module.app.test_client()
    with other_client.session_transaction() as browser_session:
        browser_session["chat_owner_id"] = other_owner
        browser_session["session_id"] = session_id

    history = owner_client.get("/history").get_json()
    assert history["images"][0]["id"] == record["id"]
    listed = owner_client.get("/images?area=math").get_json()
    assert listed["images"][0]["id"] == record["id"]
    assert owner_client.get(f"/images/{record['id']}").status_code == 200
    download = owner_client.get(f"/images/{record['id']}?download=1")
    assert download.status_code == 200
    assert download.headers["Content-Disposition"].startswith("attachment;")
    assert download.headers["Cache-Control"] == "private, no-store"
    assert other_client.get(f"/images/{record['id']}").status_code == 404
    assert other_client.delete(f"/images/{record['id']}").status_code == 404
    assert other_client.get(f"/images/{record['id']}", headers={"X-Delphic-Corpus-Owner": owner_id}).status_code == 404

    deleted = owner_client.delete(f"/images/{record['id']}")
    assert deleted.status_code == 200
    assert owner_client.get(f"/images/{record['id']}").status_code == 404


def test_image_list_rejects_an_unknown_tutor_area():
    response = app_module.app.test_client().get("/images?area=history")

    assert response.status_code == 400
    assert "Math or Science" in response.get_json()["error"]


def test_clearing_chat_removes_its_saved_images(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "clear.db"))
    monkeypatch.setenv("DELPHIC_DATA_DIR", str(tmp_path))
    database.init_db()
    owner_id = str(uuid.uuid4())
    session_id = database.create_chat_session(owner_id, "math")
    root = get_image_storage_root(tmp_path)
    record = store_generated_image(
        fake_result(),
        owner_id=owner_id,
        session_id=session_id,
        storage_root=root,
    )
    client = app_module.app.test_client()
    with client.session_transaction() as browser_session:
        browser_session["chat_owner_id"] = owner_id
        browser_session["session_id"] = session_id

    response = client.post("/clear")

    assert response.status_code == 200
    assert database.get_generated_image_record(record["id"], owner_id) is None
    assert not (root / owner_id / record["local_filename"]).exists()
