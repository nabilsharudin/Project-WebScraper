from app.scraper import (
    ScrapeError,
    find_department_links,
    parse_department_page,
    parse_profile_email,
    people_url_for_email,
    select_profile_batch,
    validate_utm_url,
)


DEPARTMENT_HTML = """
<div class="hero-section"><h1>Department One</h1><p>Faculty One</p></div>
<div class="staff-card-v2">
  <h5 class="staff-name"> Dr. Example Person </h5>
  <p class="staff-title">Senior Lecturer</p>
  <a href="/directory/staff/example">Profile</a>
</div>
"""


def test_parse_department_page():
    faculty, department, records = parse_department_page(
        DEPARTMENT_HTML, "https://www.utm.my/directory/faculty/faculty-one/department-one"
    )
    assert faculty == "Faculty One"
    assert department == "Department One"
    assert records[0]["name"] == "Dr. Example Person"
    assert records[0]["profile_url"] == "https://www.utm.my/directory/staff/example"


def test_parse_profile_email_uses_utm_address():
    html = '<a href="mailto:person@example.com">Other</a><a href="mailto:person@utm.my">UTM</a>'
    assert parse_profile_email(html) == "person@utm.my"


def test_department_links_stay_below_faculty():
    html = '<a href="/directory/faculty/faculty-one/dept-a">A</a><a href="/directory/faculty/other">Other</a>'
    assert find_department_links(
        html, "https://www.utm.my/directory/faculty/faculty-one"
    ) == ["https://www.utm.my/directory/faculty/faculty-one/dept-a"]


def test_utm_url_validation_and_people_slug():
    assert validate_utm_url("https://science.utm.my/staff")
    assert people_url_for_email("First.Last@utm.my") == "https://people.utm.my/first.last/"
    try:
        validate_utm_url("https://example.com")
        assert False, "Non-UTM URL should be rejected"
    except ScrapeError:
        pass


def test_profile_batch_skips_saved_urls_and_respects_limit():
    records = [
        {"profile_url": "https://www.utm.my/directory/staff/one"},
        {"profile_url": "https://www.utm.my/directory/staff/two"},
        {"profile_url": "https://www.utm.my/directory/staff/three"},
    ]
    batch, skipped = select_profile_batch(
        records, {"https://www.utm.my/directory/staff/one"}, 1
    )
    assert [record["profile_url"] for record in batch] == [
        "https://www.utm.my/directory/staff/two"
    ]
    assert skipped == 1
