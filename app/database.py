from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "site_scout.db"


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS lecturers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                faculty TEXT NOT NULL DEFAULT '',
                department TEXT NOT NULL DEFAULT '',
                position TEXT NOT NULL DEFAULT '',
                profile_url TEXT NOT NULL DEFAULT '',
                people_url TEXT NOT NULL DEFAULT '',
                website_status TEXT NOT NULL DEFAULT 'unchecked',
                website_title TEXT NOT NULL DEFAULT '',
                website_note TEXT NOT NULL DEFAULT '',
                contact_status TEXT NOT NULL DEFAULT 'not_contacted',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_lecturers_faculty
                ON lecturers(faculty);
            CREATE INDEX IF NOT EXISTS idx_lecturers_website_status
                ON lecturers(website_status);
            """
        )


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()

