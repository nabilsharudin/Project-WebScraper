from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import repository
from .database import init_db
from .import_jobs import create_job, get_job, update_job
from .roles import is_lecturer_position
from .scraper import EMAIL_RE, ScrapeError, check_people_site, scrape_directory


ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="UTM Site Scout")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")


@app.on_event("startup")
def startup() -> None:
    init_db()


def redirect(message: str, kind: str = "success") -> RedirectResponse:
    return RedirectResponse(
        f"/?message={quote(message)}&kind={quote(kind)}", status_code=303
    )


@app.get("/")
def dashboard(
    request: Request,
    search: str = "",
    faculty: str = "",
    website_status: str = "",
    role: str = "lecturers",
    message: str = "",
    kind: str = "success",
):
    lecturers_only = role != "all"
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "lecturers": repository.list_lecturers(
                search, faculty, website_status, lecturers_only=lecturers_only
            ),
            "faculties": repository.faculties(),
            "counts": repository.counts(lecturers_only=lecturers_only),
            "filters": {
                "search": search,
                "faculty": faculty,
                "website_status": website_status,
                "role": role,
            },
            "message": message,
            "kind": kind,
        },
    )


@app.post("/lecturers")
def add_lecturer(
    name: str = Form(...),
    email: str = Form(...),
    faculty: str = Form(""),
    department: str = Form(""),
    position: str = Form("PENSYARAH"),
    people_url: str = Form(""),
):
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        return redirect("Enter a valid @utm.my email address.", "error")
    repository.upsert_lecturer(
        {
            "name": name,
            "email": email,
            "faculty": faculty,
            "department": department,
            "position": position,
            "people_url": people_url,
        }
    )
    return redirect(f"Saved {name.strip()}.")


def run_import_job(
    job_id: str, source_url: str, batch_size: int, lecturers_only: bool
) -> None:
    update_job(job_id, status="running", phase="Preparing import", percent=1)
    try:
        existing_profiles = {
            row["profile_url"]
            for row in repository.list_lecturers()
            if row["profile_url"]
        }
        result = scrape_directory(
            source_url,
            batch_size=batch_size,
            skip_profile_urls=existing_profiles,
            lecturers_only=lecturers_only,
            progress_callback=lambda phase, current, total, percent: update_job(
                job_id,
                phase=phase,
                current=current,
                total=total,
                percent=percent,
            ),
        )
    except (ScrapeError, OSError, ValueError) as error:
        update_job(
            job_id,
            status="failed",
            phase="Import stopped",
            message=str(error),
        )
        return
    except Exception as error:
        update_job(
            job_id,
            status="failed",
            phase="Import stopped",
            message=f"The directory could not be imported: {type(error).__name__}",
        )
        return
    saved = repository.bulk_upsert(result.records)
    remaining = max(
        0, result.discovered_profiles - result.skipped_existing - len(result.records)
    )
    if saved == 0 and remaining == 0:
        message = "This directory is already fully imported."
    else:
        message = f"Imported {saved} records gently."
        if remaining:
            message += f" About {remaining} remain; use Import again later to continue."
        if result.failed_requests:
            message += f" Skipped {result.failed_requests} requests that did not respond."
    update_job(
        job_id,
        status="completed",
        phase="Import complete",
        current=len(result.records),
        total=len(result.records),
        percent=100,
        message=message,
    )


@app.post("/imports/start")
def start_import(
    background_tasks: BackgroundTasks,
    source_url: str = Form(...),
    batch_size: int = Form(10),
    lecturers_only: bool = Form(False),
):
    job = create_job()
    background_tasks.add_task(
        run_import_job, job["id"], source_url, batch_size, lecturers_only
    )
    return {"job_id": job["id"]}


@app.get("/imports/{job_id}")
def import_progress(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found")
    return job


@app.post("/import/csv")
async def import_csv(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".csv"):
        return redirect("Please upload a CSV file.", "error")
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        records = []
        for row in reader:
            normalized = {str(key).strip().lower(): (value or "").strip() for key, value in row.items()}
            email = normalized.get("email", "").lower()
            position = normalized.get("position", "")
            position_is_eligible = is_lecturer_position(position)
            if normalized.get("name") and EMAIL_RE.match(email) and position_is_eligible:
                normalized["email"] = email
                records.append(normalized)
    except (UnicodeDecodeError, csv.Error):
        return redirect("That CSV file could not be read.", "error")
    saved = repository.bulk_upsert(records)
    return redirect(f"Imported {saved} valid CSV records.")


@app.post("/lecturers/{lecturer_id}/check")
def check_website(lecturer_id: int):
    lecturer = repository.get_lecturer(lecturer_id)
    if lecturer is None:
        return redirect("Lecturer not found.", "error")
    result = check_people_site(lecturer["email"], lecturer["people_url"])
    repository.update_lecturer(
        lecturer_id,
        {
            "people_url": result.url,
            "website_status": result.status,
            "website_title": result.title,
            "website_note": result.note,
        },
    )
    label = "Website found" if result.status == "found" else "Website check complete"
    return redirect(f"{label} for {lecturer['name']}.")


@app.post("/websites/check")
def check_all_websites():
    lecturers = repository.list_lecturers(
        website_status="unchecked", lecturers_only=True
    )
    checked = 0
    for lecturer in lecturers[:50]:
        result = check_people_site(lecturer["email"], lecturer["people_url"])
        repository.update_lecturer(
            lecturer["id"],
            {
                "people_url": result.url,
                "website_status": result.status,
                "website_title": result.title,
                "website_note": result.note,
            },
        )
        checked += 1
    suffix = " (maximum 50 per batch)" if len(lecturers) > 50 else ""
    return redirect(f"Checked {checked} lecturer websites{suffix}.")


@app.post("/lecturers/{lecturer_id}/update")
def update_lecturer(
    lecturer_id: int,
    people_url: str = Form(""),
    contact_status: str = Form("not_contacted"),
    notes: str = Form(""),
):
    if contact_status not in {"not_contacted", "contacted", "replied", "declined"}:
        contact_status = "not_contacted"
    repository.update_lecturer(
        lecturer_id,
        {"people_url": people_url.strip(), "contact_status": contact_status, "notes": notes.strip()},
    )
    return redirect("Lecturer details updated.")


@app.post("/lecturers/{lecturer_id}/delete")
def delete_lecturer(lecturer_id: int):
    repository.delete_lecturer(lecturer_id)
    return redirect("Lecturer removed.")


@app.get("/export.csv")
def export_csv(lecturers_only: bool = True):
    rows = repository.list_lecturers(lecturers_only=lecturers_only)
    output = io.StringIO()
    fields = [
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
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows({field: row[field] for field in fields} for row in rows)
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="utm-site-scout.csv"'},
    )
