from __future__ import annotations

import sqlite3
from typing import Any, Iterable

from .database import connect
from .roles import is_lecturer_position


FIELDS = (
    "name",
    "email",
    "faculty",
    "department",
    "position",
    "profile_url",
    "people_url",
    "website_status",
    "website_title",
    "website_note",
    "contact_status",
    "notes",
)


def list_lecturers(
    search: str = "",
    faculty: str = "",
    website_status: str = "",
    department: str = "",
    lecturers_only: bool = False,
) -> list[sqlite3.Row]:
    clauses: list[str] = []
    parameters: list[str] = []
    if search:
        clauses.append("(name LIKE ? OR email LIKE ? OR department LIKE ?)")
        needle = f"%{search}%"
        parameters.extend([needle, needle, needle])
    if faculty:
        clauses.append("faculty = ?")
        parameters.append(faculty)
    if department:
        clauses.append("department = ?")
        parameters.append(department)
    if website_status == "checked":
        clauses.append("website_status <> 'unchecked'")
    elif website_status:
        clauses.append("website_status = ?")
        parameters.append(website_status)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as connection:
        rows = connection.execute(
            f"SELECT * FROM lecturers {where} ORDER BY faculty, name", parameters
        ).fetchall()
    if lecturers_only:
        return [row for row in rows if is_lecturer_position(row["position"])]
    return rows


def faculties() -> list[str]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT DISTINCT faculty FROM lecturers WHERE faculty <> '' ORDER BY faculty"
        ).fetchall()
    return [row["faculty"] for row in rows]


def departments(lecturers_only: bool = False) -> list[str]:
    rows = list_lecturers(lecturers_only=lecturers_only)
    return sorted({row["department"] for row in rows if row["department"]})


def counts(lecturers_only: bool = False) -> dict[str, int]:
    rows = list_lecturers(lecturers_only=lecturers_only)
    return {
        "total": len(rows),
        "found": sum(row["website_status"] == "found" for row in rows),
        "unchecked": sum(row["website_status"] == "unchecked" for row in rows),
        "contacted": sum(row["contact_status"] == "contacted" for row in rows),
    }


def get_lecturer(lecturer_id: int) -> sqlite3.Row | None:
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM lecturers WHERE id = ?", (lecturer_id,)
        ).fetchone()


def upsert_lecturer(data: dict[str, Any]) -> bool:
    values = {field: str(data.get(field, "") or "").strip() for field in FIELDS}
    values["email"] = values["email"].lower()
    if not values["name"] or not values["email"]:
        return False
    if not values["website_status"]:
        values["website_status"] = "unchecked"
    if not values["contact_status"]:
        values["contact_status"] = "not_contacted"

    columns = ", ".join(FIELDS)
    placeholders = ", ".join(f":{field}" for field in FIELDS)
    # Re-importing directory data should refresh identity fields without erasing
    # website research or outreach progress already recorded by the user.
    refreshable_fields = {
        "name",
        "faculty",
        "department",
        "position",
        "profile_url",
        "people_url",
    }
    updates = ", ".join(
        f"{field} = CASE WHEN excluded.{field} <> '' THEN excluded.{field} ELSE lecturers.{field} END"
        for field in FIELDS
        if field in refreshable_fields
    )
    with connect() as connection:
        before = connection.total_changes
        connection.execute(
            f"""
            INSERT INTO lecturers ({columns}) VALUES ({placeholders})
            ON CONFLICT(email) DO UPDATE SET {updates}, updated_at = CURRENT_TIMESTAMP
            """,
            values,
        )
        return connection.total_changes > before


def bulk_upsert(records: Iterable[dict[str, Any]]) -> int:
    return sum(1 for record in records if upsert_lecturer(record))


def update_lecturer(lecturer_id: int, data: dict[str, Any]) -> None:
    allowed = {
        "people_url",
        "website_status",
        "website_title",
        "website_note",
        "checked_at",
        "contact_status",
        "notes",
    }
    selected = {key: value for key, value in data.items() if key in allowed}
    if not selected:
        return
    assignments = ", ".join(f"{key} = ?" for key in selected)
    with connect() as connection:
        connection.execute(
            f"UPDATE lecturers SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [*selected.values(), lecturer_id],
        )


def delete_lecturer(lecturer_id: int) -> None:
    with connect() as connection:
        connection.execute("DELETE FROM lecturers WHERE id = ?", (lecturer_id,))


def clear_lecturers() -> None:
    with connect() as connection:
        connection.execute("DELETE FROM lecturers")
