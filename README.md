# UTM Site Scout

A private, local web app for organizing public UTM lecturer contacts, grouping them by faculty, and checking for likely `people.utm.my` websites. It deliberately does not send bulk email: outreach stays human-reviewed.

## Run locally in VS Code

Open the integrated PowerShell terminal in this folder, then run:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

If PowerShell blocks activation, you can skip it and use the virtual environment directly:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## What the MVP does

- Imports one UTM directory faculty or department URL at a time in resumable batches.
- Imports and exports active lecturer/professor positions by default while retaining an optional all-staff view.
- Shows live progress while scanning departments and lecturer profiles.
- Accepts manual entries and CSV files.
- Groups and filters lecturers by faculty.
- Checks the likely People@UTM URL derived from each UTM email username.
- Stores website and outreach status in a local SQLite database.
- Exports the current list as CSV.

CSV files require `name` and `email` headers. Optional headers include `faculty`, `department`, `position`, `profile_url`, and `people_url`.

## Data and responsible use

The local database is created at `data/site_scout.db` and is ignored by Git. The importer accepts only HTTPS pages on the `utm.my` domain, spaces requests apart with jitter, retries only once, and caps each batch at 25 profiles. Ten profiles per batch is the recommended default. Re-importing the same URL skips saved profiles and continues the faculty. If UTM times out or asks the importer to slow down, stop and retry later. Confirm site terms and applicable rules before collecting or using contact data, personalize messages, and honor requests not to be contacted.
