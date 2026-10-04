from app.import_jobs import create_job, get_job, update_job


def test_import_job_progress_is_recorded():
    job = create_job()
    update_job(
        job["id"],
        status="running",
        phase="Reading lecturer profiles respectfully",
        current=3,
        total=10,
        percent=49,
    )
    updated = get_job(job["id"])
    assert updated["status"] == "running"
    assert updated["current"] == 3
    assert updated["total"] == 10
    assert updated["percent"] == 49

