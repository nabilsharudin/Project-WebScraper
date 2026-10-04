from __future__ import annotations

import re
import random
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .roles import is_lecturer_position


USER_AGENT = "UTMSiteScout/0.1 (local research tool; respectful request rate)"
DIRECTORY_ROOT = "https://www.utm.my"
EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@utm\.my$", re.IGNORECASE)
DEFAULT_REQUEST_DELAY = 1.5
MAX_BATCH_SIZE = 25
ProgressCallback = Callable[[str, int, int, int], None]


class ScrapeError(ValueError):
    pass


@dataclass
class ScrapeResult:
    records: list[dict[str, str]]
    discovered_profiles: int
    skipped_existing: int
    failed_requests: int


def clean(value: str | None) -> str:
    return " ".join((value or "").split())


def validate_utm_url(url: str) -> str:
    parsed = urlparse(url.strip())
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        hostname == "utm.my" or hostname.endswith(".utm.my")
    ):
        raise ScrapeError("Use an HTTPS URL on the utm.my domain.")
    return url.strip()


def parse_department_page(html: str, page_url: str) -> tuple[str, str, list[dict[str, str]]]:
    soup = BeautifulSoup(html, "html.parser")
    hero = soup.select_one(".hero-section")
    department = clean(hero.select_one("h1").get_text()) if hero and hero.select_one("h1") else ""
    faculty = clean(hero.select_one("p").get_text()) if hero and hero.select_one("p") else ""
    records: list[dict[str, str]] = []
    for card in soup.select(".staff-card-v2"):
        link = card.select_one('a[href*="/directory/staff/"]')
        name = card.select_one(".staff-name")
        if not link or not name:
            continue
        title = card.select_one(".staff-title")
        records.append(
            {
                "name": clean(name.get_text()),
                "position": clean(title.get_text()) if title else "",
                "faculty": faculty,
                "department": department if department != faculty else "",
                "profile_url": urljoin(page_url, link.get("href", "")),
            }
        )
    return faculty, department, records


def parse_profile_email(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.select('a[href^="mailto:"]'):
        email = link.get("href", "").removeprefix("mailto:").split("?", 1)[0].strip()
        if EMAIL_RE.match(email):
            return email.lower()
    return ""


def find_department_links(html: str, source_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    source_path = urlparse(source_url).path.rstrip("/")
    prefix = source_path + "/"
    links: list[str] = []
    for anchor in soup.select('a[href*="/directory/faculty/"]'):
        absolute = urljoin(source_url, anchor.get("href", ""))
        path = urlparse(absolute).path.rstrip("/")
        if path.startswith(prefix) and path != source_path and absolute not in links:
            links.append(absolute)
    return links


def select_profile_batch(
    records: list[dict[str, str]], skip_profile_urls: set[str], batch_size: int
) -> tuple[list[dict[str, str]], int]:
    unique: dict[str, dict[str, str]] = {}
    for record in records:
        profile_url = record.get("profile_url", "")
        if profile_url and profile_url not in unique:
            unique[profile_url] = record
    pending = [record for url, record in unique.items() if url not in skip_profile_urls]
    skipped = len(unique) - len(pending)
    return pending[:batch_size], skipped


def polite_pause(request_delay: float) -> None:
    # A small jitter prevents requests from arriving in a machine-like rhythm.
    time.sleep(request_delay + random.uniform(0.15, 0.55))


def scrape_directory(
    source_url: str,
    request_delay: float = DEFAULT_REQUEST_DELAY,
    batch_size: int = 10,
    skip_profile_urls: set[str] | None = None,
    progress_callback: ProgressCallback | None = None,
    lecturers_only: bool = True,
) -> ScrapeResult:
    source_url = validate_utm_url(source_url)
    batch_size = max(1, min(int(batch_size), MAX_BATCH_SIZE))
    skip_profile_urls = skip_profile_urls or set()
    report = progress_callback or (lambda phase, current, total, percent: None)
    path_parts = [part for part in urlparse(source_url).path.split("/") if part]
    if len(path_parts) < 3 or path_parts[:2] != ["directory", "faculty"]:
        raise ScrapeError("Choose one faculty or department page from the UTM directory.")

    timeout = httpx.Timeout(20.0)
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
        transport=httpx.HTTPTransport(retries=1),
    ) as client:
        report("Connecting to the UTM directory", 0, 1, 4)
        try:
            response = client.get(source_url)
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise ScrapeError(
                "UTM did not respond in time. Stop importing for now and try again later."
            ) from error
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {429, 503}:
                raise ScrapeError(
                    "UTM asked the importer to slow down. Please wait before trying again."
                ) from error
            raise ScrapeError(
                f"UTM returned HTTP {error.response.status_code}. Please try again later."
            ) from error
        except httpx.HTTPError as error:
            raise ScrapeError("Could not connect to the UTM directory.") from error
        report("Connected to the UTM directory", 1, 1, 10)
        faculty, department, direct_records = parse_department_page(response.text, source_url)

        failed_requests = 0
        if direct_records:
            records = direct_records
        else:
            department_links = find_department_links(response.text, source_url)
            if not department_links:
                raise ScrapeError("No staff or department links were found on that page.")
            records = []
            for index, link in enumerate(department_links, start=1):
                report(
                    "Scanning faculty departments",
                    index - 1,
                    len(department_links),
                    10 + round(20 * (index - 1) / len(department_links)),
                )
                polite_pause(request_delay)
                try:
                    child = client.get(link)
                    child.raise_for_status()
                except httpx.HTTPError:
                    failed_requests += 1
                    continue
                child_faculty, _, child_records = parse_department_page(child.text, link)
                for record in child_records:
                    record["faculty"] = record["faculty"] or child_faculty or faculty
                records.extend(child_records)
                report(
                    "Scanning faculty departments",
                    index,
                    len(department_links),
                    10 + round(20 * index / len(department_links)),
                )

        if lecturers_only:
            records = [
                record
                for record in records
                if is_lecturer_position(record.get("position", ""))
            ]
        discovered_profiles = len({record["profile_url"] for record in records})
        batch, skipped_existing = select_profile_batch(
            records, skip_profile_urls, batch_size
        )
        completed: list[dict[str, str]] = []
        if not batch:
            report("All discovered profiles are already saved", 0, 0, 95)
        for index, record in enumerate(batch, start=1):
            profile_url = record["profile_url"]
            report(
                "Reading lecturer profiles respectfully",
                index - 1,
                len(batch),
                30 + round(65 * (index - 1) / len(batch)),
            )
            polite_pause(request_delay)
            try:
                profile = client.get(profile_url)
                profile.raise_for_status()
                record["email"] = parse_profile_email(profile.text)
            except httpx.HTTPError:
                record["email"] = ""
                failed_requests += 1
            if record["email"]:
                completed.append(record)
            report(
                "Reading lecturer profiles respectfully",
                index,
                len(batch),
                30 + round(65 * index / len(batch)),
            )
        return ScrapeResult(
            records=completed,
            discovered_profiles=discovered_profiles,
            skipped_existing=skipped_existing,
            failed_requests=failed_requests,
        )


@dataclass
class WebsiteResult:
    url: str
    status: str
    title: str = ""
    note: str = ""


def people_url_for_email(email: str) -> str:
    local_part = email.split("@", 1)[0].strip().lower()
    safe_slug = re.sub(r"[^a-z0-9._-]", "", local_part)
    return f"https://people.utm.my/{safe_slug}/"


def check_people_site(email: str, existing_url: str = "") -> WebsiteResult:
    candidate = existing_url.strip() or people_url_for_email(email)
    try:
        parsed = urlparse(validate_utm_url(candidate))
    except ScrapeError as error:
        return WebsiteResult(candidate, "error", note=str(error))
    if parsed.hostname != "people.utm.my":
        return WebsiteResult(candidate, "error", note="Only People@UTM URLs are checked here.")

    try:
        with httpx.Client(
            timeout=12.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = client.get(candidate)
        text = response.text.lower()
        missing_markers = ("page not found", "nothing found", "error 404", "site not found")
        if response.status_code == 404 or any(marker in text for marker in missing_markers):
            return WebsiteResult(candidate, "not_found", note="No site was found at the email-based URL.")
        if response.status_code >= 400:
            return WebsiteResult(candidate, "error", note=f"Website returned HTTP {response.status_code}.")
        soup = BeautifulSoup(response.text, "html.parser")
        title = clean(soup.title.get_text()) if soup.title else ""
        return WebsiteResult(
            str(response.url),
            "found",
            title=title,
            note="Found using the UTM email username. Review the site to confirm the owner.",
        )
    except httpx.HTTPError as error:
        return WebsiteResult(candidate, "error", note=f"Could not check site: {type(error).__name__}")
