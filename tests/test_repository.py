from app import database, repository


def test_reimport_preserves_research_and_outreach_status(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    repository.upsert_lecturer(
        {"name": "First Name", "email": "person@utm.my", "faculty": "Old Faculty"}
    )
    lecturer = repository.list_lecturers()[0]
    repository.update_lecturer(
        lecturer["id"],
        {
            "website_status": "found",
            "people_url": "https://people.utm.my/person/",
            "contact_status": "contacted",
            "notes": "Personalized message sent",
        },
    )

    repository.upsert_lecturer(
        {"name": "Updated Name", "email": "person@utm.my", "faculty": "New Faculty"}
    )

    updated = repository.list_lecturers()[0]
    assert updated["name"] == "Updated Name"
    assert updated["faculty"] == "New Faculty"
    assert updated["website_status"] == "found"
    assert updated["contact_status"] == "contacted"
    assert updated["notes"] == "Personalized message sent"


def test_clear_lecturers_removes_only_local_records(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    repository.upsert_lecturer({"name": "Person", "email": "person@utm.my"})
    repository.clear_lecturers()
    assert repository.list_lecturers() == []


def test_checked_at_can_be_saved_for_a_website_result(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    repository.upsert_lecturer({"name": "Person", "email": "person@utm.my"})
    lecturer = repository.list_lecturers()[0]
    repository.update_lecturer(lecturer["id"], {"checked_at": "07 Oct 2026, 10:15"})
    assert repository.get_lecturer(lecturer["id"])["checked_at"] == "07 Oct 2026, 10:15"


def test_checked_filter_includes_any_completed_website_result(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    repository.upsert_lecturer({"name": "Unchecked", "email": "unchecked@utm.my"})
    repository.upsert_lecturer({"name": "Found", "email": "found@utm.my"})
    repository.upsert_lecturer({"name": "Missing", "email": "missing@utm.my"})
    for lecturer in repository.list_lecturers():
        if lecturer["name"] == "Found":
            repository.update_lecturer(lecturer["id"], {"website_status": "found"})
        if lecturer["name"] == "Missing":
            repository.update_lecturer(lecturer["id"], {"website_status": "not_found"})
    assert {row["name"] for row in repository.list_lecturers(website_status="checked")} == {
        "Found",
        "Missing",
    }
