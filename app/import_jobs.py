from __future__ import annotations

from copy import deepcopy
from threading import Lock
from uuid import uuid4


_jobs: dict[str, dict] = {}
_lock = Lock()


def create_job() -> dict:
    job = {
        "id": uuid4().hex,
        "status": "queued",
        "phase": "Waiting to start",
        "current": 0,
        "total": 0,
        "percent": 0,
        "message": "",
    }
    with _lock:
        _jobs[job["id"]] = job
    return deepcopy(job)


def update_job(job_id: str, **changes) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(changes)


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return deepcopy(job) if job else None

