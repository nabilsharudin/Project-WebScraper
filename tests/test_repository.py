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

