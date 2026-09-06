"""The editor, over HTTP.

Driven through the real app with a real store on a real repository. The things
worth testing here are the joins -- that a form post becomes a commit, that a
broken calendar still lets you in to fix it, that publishing is a separate act
from saving -- and every one of those is a join between parts that a mocked
store would hold apart.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web.app import create_app
from web.auth import Auth, hash_password
from web.store import Store

PASSWORD = "correct horse"

CSV = """\
date,start_date,end_date,type,label,notes
2400-08-31,,,first_day,First Day,
2400-09-07,,,no_school,Labor Day,
2400-10-15,,,ptsa_event,Curriculum Night,
,2400-11-26,2400-11-27,no_school,Thanksgiving Break,
2401-06-16,,,last_day,Last Day of School,
"""

TOML = """\
[calendar]
organization = "Test PTSA"

[dates]
early_release_start = 2400-09-09
last_day = 2401-06-16
boxed_days = [2400-08-31, 2401-06-16]
"""


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    seed = tmp_path / "seed"
    (seed / "data" / "years").mkdir(parents=True)
    (seed / "data" / "all_events.csv").write_text(CSV)
    (seed / "data" / "years" / "2400-01.toml").write_text(TOML)
    git(seed, "init", "-q", "-b", "main")
    git(seed, "config", "user.name", "Seed")
    git(seed, "config", "user.email", "seed@example.com")
    git(seed, "add", "-A")
    git(seed, "commit", "-qm", "initial")
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "--bare", "-q", str(seed), str(bare)], check=True)
    return bare


@pytest.fixture
def store(remote: Path, tmp_path: Path) -> Store:
    return Store.clone(str(remote), tmp_path / "clone")


@pytest.fixture
def client(store: Store) -> TestClient:
    app = create_app(store=store,
                     auth=Auth(password_hash=hash_password(PASSWORD),
                               secret="test-secret"))
    app.state.secure_cookies = False
    return TestClient(app)


@pytest.fixture
def signed_in(client: TestClient) -> TestClient:
    client.post("/login", data={"password": PASSWORD, "name": "Allison"},
                follow_redirects=False)
    return client


def form_from(html: str) -> dict[str, str]:
    """Every input and selected option in the dates form, as the browser would
    post it. Keeps these tests honest about the real field names."""
    fields = {}
    for name, value in re.findall(
            r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', html):
        fields[name] = value
    for name in re.findall(r'<input[^>]*name="(row-\d+-label)"(?![^>]*value)', html):
        fields.setdefault(name, "")
    for block in re.findall(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>',
                            html, re.S):
        name, body = block
        chosen = re.search(r'value="([^"]+)"[^>]*selected', body)
        fields[name] = chosen.group(1) if chosen else ""
    return fields


# --- getting in ------------------------------------------------------------

def test_the_editor_needs_the_password(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_a_wrong_password_does_not_let_you_in(client):
    response = client.post("/login", data={"password": "guess"},
                           follow_redirects=False)
    assert response.status_code == 200
    assert "not right" in response.text
    assert client.get("/", follow_redirects=False).status_code == 303


def test_the_right_password_lets_you_in(client):
    response = client.post("/login", data={"password": PASSWORD, "name": "Allison"},
                           follow_redirects=False)
    assert response.status_code == 303
    assert client.get("/").status_code == 200


def test_repeated_wrong_guesses_get_shut_out(client):
    for _ in range(8):
        client.post("/login", data={"password": "guess"}, follow_redirects=False)
    response = client.post("/login", data={"password": PASSWORD},
                           follow_redirects=False)
    assert response.status_code == 429, "the rate limit did not engage"
    assert "Too many" in response.text


def test_the_password_is_never_in_a_page(signed_in):
    assert PASSWORD not in signed_in.get("/").text


# --- the dates page --------------------------------------------------------

def test_the_dates_page_lists_every_row(signed_in):
    html = signed_in.get("/").text
    for label in ("First Day", "Labor Day", "Curriculum Night",
                  "Thanksgiving Break", "Last Day of School"):
        assert label in html


def test_the_type_dropdown_comes_from_the_registry(signed_in):
    """Offering a type the renderer does not know would put an unbuildable
    calendar one click away."""
    from calendar_gen import event_types
    html = signed_in.get("/").text
    for kind in event_types.choices():
        assert f'value="{kind.name}"' in html
    assert "Just listed" in html, "the human labels are not being shown"


def test_a_date_range_shows_in_both_boxes(signed_in):
    html = signed_in.get("/").text
    fields = form_from(html)
    i = next(n for n in range(20)
             if fields.get(f"row-{n}-label") == "Thanksgiving Break")
    assert fields[f"row-{i}-from"] == "2400-11-26"
    assert fields[f"row-{i}-to"] == "2400-11-27"


# --- saving ----------------------------------------------------------------

def test_saving_a_moved_date_commits_it(signed_in, store):
    fields = form_from(signed_in.get("/").text)
    i = next(n for n in range(20)
             if fields.get(f"row-{n}-label") == "Curriculum Night")
    fields[f"row-{i}-from"] = "2400-10-22"

    signed_in.post("/save", data=fields, follow_redirects=False)

    moved = [r for r in store.rows() if r.label == "Curriculum Night"]
    assert [r.date for r in moved] == ["2400-10-22"]


def test_the_commit_says_what_happened_in_plain_words(signed_in, store):
    fields = form_from(signed_in.get("/").text)
    i = next(n for n in range(20)
             if fields.get(f"row-{n}-label") == "Curriculum Night")
    fields[f"row-{i}-from"] = "2400-10-22"
    signed_in.post("/save", data=fields, follow_redirects=False)

    latest = store.history()[0]
    assert latest.author == "Allison"
    assert latest.summary == "Curriculum Night: moved from Oct 15 to Oct 22"


def test_a_deleted_row_goes(signed_in, store):
    fields = form_from(signed_in.get("/").text)
    i = next(n for n in range(20) if fields.get(f"row-{n}-label") == "Labor Day")
    fields[f"row-{i}-deleted"] = "1"
    signed_in.post("/save", data=fields, follow_redirects=False)

    assert not any(r.label == "Labor Day" for r in store.rows())
    assert store.history()[0].summary == "Labor Day: removed from Sep 7"


def test_an_added_row_arrives(signed_in, store):
    fields = form_from(signed_in.get("/").text)
    fields.update({
        "row-99-from": "2400-12-05", "row-99-to": "",
        "row-99-type": "ptsa_event", "row-99-label": "Winter Social",
        "row-99-notes": "", "row-99-deleted": "0",
    })
    signed_in.post("/save", data=fields, follow_redirects=False)

    assert any(r.label == "Winter Social" and r.date == "2400-12-05"
               for r in store.rows())


def test_a_one_day_range_is_saved_as_a_single_date(signed_in, store):
    """Same From and To means one day. Storing it as a range would earn a
    validation warning for something the person did not do wrong."""
    fields = form_from(signed_in.get("/").text)
    fields.update({
        "row-99-from": "2400-12-05", "row-99-to": "2400-12-05",
        "row-99-type": "ptsa_event", "row-99-label": "Winter Social",
        "row-99-notes": "", "row-99-deleted": "0",
    })
    signed_in.post("/save", data=fields, follow_redirects=False)

    row = next(r for r in store.rows() if r.label == "Winter Social")
    assert (row.date, row.start_date, row.end_date) == ("2400-12-05", "", "")


def test_an_empty_added_row_is_ignored(signed_in, store):
    """Someone clicks Add, changes their mind, saves. That must not become a
    validation error about a blank line they cannot see."""
    before = len(store.rows())
    fields = form_from(signed_in.get("/").text)
    fields.update({"row-99-from": "", "row-99-to": "", "row-99-type": "ptsa_event",
                   "row-99-label": "", "row-99-notes": "", "row-99-deleted": "0"})
    signed_in.post("/save", data=fields, follow_redirects=False)
    assert len(store.rows()) == before


def test_the_notes_column_survives_a_save(signed_in, store, remote, tmp_path):
    """Nothing in the editor shows the notes, so nothing in the editor may lose
    them -- they carry the provenance of the district dates."""
    seed = Store.clone(str(remote), tmp_path / "seeder")
    rows = seed.rows()
    rows[0].notes = "Verified against the district PDF, revision 8/2400."
    seed.save(rows, "Seeder", "added a note")
    seed.publish()

    fields = form_from(signed_in.get("/").text)
    fields["row-0-label"] = "First Day of School"
    signed_in.post("/save", data=fields, follow_redirects=False)

    assert any("Verified against the district PDF" in r.notes
               for r in store.rows())


# --- publishing ------------------------------------------------------------

def test_saving_does_not_publish(signed_in, store, remote):
    fields = form_from(signed_in.get("/").text)
    i = next(n for n in range(20)
             if fields.get(f"row-{n}-label") == "Curriculum Night")
    fields[f"row-{i}-from"] = "2400-10-22"
    signed_in.post("/save", data=fields, follow_redirects=False)

    assert "2400-10-22" not in git(remote, "show", "main:data/all_events.csv")
    assert store.has_unpublished_changes() is True


def test_the_page_says_there_are_unpublished_changes(signed_in):
    fields = form_from(signed_in.get("/").text)
    i = next(n for n in range(20)
             if fields.get(f"row-{n}-label") == "Curriculum Night")
    fields[f"row-{i}-from"] = "2400-10-22"
    signed_in.post("/save", data=fields, follow_redirects=False)

    html = signed_in.get("/").text
    assert "Unpublished changes" in html
    assert "moved from Oct 15 to Oct 22" in html


def test_publishing_sends_it(signed_in, store, remote):
    fields = form_from(signed_in.get("/").text)
    i = next(n for n in range(20)
             if fields.get(f"row-{n}-label") == "Curriculum Night")
    fields[f"row-{i}-from"] = "2400-10-22"
    signed_in.post("/save", data=fields, follow_redirects=False)

    response = signed_in.post("/publish", follow_redirects=False)
    assert response.status_code == 303

    assert "2400-10-22" in git(remote, "show", "main:data/all_events.csv")
    assert store.has_unpublished_changes() is False


def test_the_publish_page_shows_the_changes_before_you_commit_to_them(signed_in):
    fields = form_from(signed_in.get("/").text)
    i = next(n for n in range(20)
             if fields.get(f"row-{n}-label") == "Curriculum Night")
    fields[f"row-{i}-from"] = "2400-10-22"
    signed_in.post("/save", data=fields, follow_redirects=False)

    html = signed_in.get("/publish").text
    assert "Curriculum Night" in html
    assert "moved from Oct 15 to Oct 22" in html


def test_a_calendar_that_will_not_fit_cannot_be_published(signed_in, store):
    """The button is disabled, but a stale page must not get past it either."""
    rows = store.rows()
    for n in range(70):
        rows.append(type(rows[0])(
            date=f"2400-09-{n % 28 + 1:02d}", type="ptsa_event",
            label=f"Fundraiser planning meeting number {n}"))
    store.save(rows, "Allison", "far too many")

    response = signed_in.post("/publish", follow_redirects=False)
    assert response.status_code == 422
    assert "fit on one" in response.text
    assert store.has_unpublished_changes() is True, "it published anyway"


# --- when things are broken ------------------------------------------------

def test_a_broken_calendar_still_lets_you_in_to_fix_it(signed_in, store):
    """The state someone needs the editor for most is the one where the
    calendar will not build. Refusing to load would leave them with no way in
    but the CSV."""
    rows = store.rows()
    rows[0].type = "not_a_real_type"
    store.save(rows, "Someone", "broke it")

    response = signed_in.get("/")
    assert response.status_code == 200
    assert "cannot be built" in response.text
    assert "not_a_real_type" in response.text
    assert "First Day" in response.text, "the rows are still editable"


def test_a_broken_calendar_cannot_be_published(signed_in, store):
    rows = store.rows()
    rows[0].type = "not_a_real_type"
    store.save(rows, "Someone", "broke it")

    assert signed_in.post("/publish", follow_redirects=False).status_code == 422
    assert store.has_unpublished_changes() is True


def test_a_broken_calendar_can_be_fixed_from_the_page(signed_in, store):
    rows = store.rows()
    rows[0].type = "not_a_real_type"
    store.save(rows, "Someone", "broke it")

    fields = form_from(signed_in.get("/").text)
    fields["row-0-type"] = "first_day"
    signed_in.post("/save", data=fields, follow_redirects=False)

    assert "cannot be built" not in signed_in.get("/").text


# --- preview ---------------------------------------------------------------

def test_the_preview_is_a_real_pdf(signed_in):
    response = signed_in.get("/preview.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_the_preview_is_marked_as_a_draft_when_downloaded(signed_in):
    """It gets emailed around for review. The filename is the only thing that
    travels with it."""
    disposition = signed_in.get("/preview.pdf").headers["content-disposition"]
    assert "DRAFT-" in disposition


def test_the_preview_shows_what_was_saved(signed_in, store):
    import pypdf, io
    fields = form_from(signed_in.get("/").text)
    fields.update({"row-99-from": "2400-12-05", "row-99-to": "",
                   "row-99-type": "ptsa_event", "row-99-label": "Winter Social",
                   "row-99-notes": "", "row-99-deleted": "0"})
    signed_in.post("/save", data=fields, follow_redirects=False)

    pdf = pypdf.PdfReader(io.BytesIO(signed_in.get("/preview.pdf").content))
    assert "Winter Social" in pdf.pages[0].extract_text()


def test_the_preview_needs_the_password(client):
    assert client.get("/preview.pdf", follow_redirects=False).status_code == 303


# --- history ---------------------------------------------------------------

def test_history_lists_the_saves(signed_in):
    fields = form_from(signed_in.get("/").text)
    i = next(n for n in range(20)
             if fields.get(f"row-{n}-label") == "Curriculum Night")
    fields[f"row-{i}-from"] = "2400-10-22"
    signed_in.post("/save", data=fields, follow_redirects=False)

    html = signed_in.get("/history").text
    assert "Allison" in html
    assert "moved from Oct 15 to Oct 22" in html


def test_restoring_puts_the_old_dates_back_as_a_draft(signed_in, store, remote):
    original = store.head()
    fields = form_from(signed_in.get("/").text)
    i = next(n for n in range(20)
             if fields.get(f"row-{n}-label") == "Curriculum Night")
    fields[f"row-{i}-from"] = "2400-10-22"
    signed_in.post("/save", data=fields, follow_redirects=False)
    signed_in.post("/publish", follow_redirects=False)

    response = signed_in.post(f"/history/{original}/restore", follow_redirects=False)
    assert response.status_code == 303

    assert any(r.date == "2400-10-15" for r in store.rows())
    assert store.has_unpublished_changes() is True, (
        "a restore must not publish itself")
    assert "2400-10-22" in git(remote, "show", "main:data/all_events.csv")


def test_looking_at_a_version_says_what_changed_since(signed_in, store):
    original = store.head()
    fields = form_from(signed_in.get("/").text)
    i = next(n for n in range(20)
             if fields.get(f"row-{n}-label") == "Curriculum Night")
    fields[f"row-{i}-from"] = "2400-10-22"
    signed_in.post("/save", data=fields, follow_redirects=False)

    html = signed_in.get(f"/history/{original}").text
    # Read forwards, as "what has changed since then" -- which is what the
    # heading says and what restoring would undo. Stating it the other way
    # round would mean the same list read differently on two pages.
    assert "moved from Oct 15 to Oct 22" in html
    assert "Restoring undoes exactly this" in html


def test_an_unknown_version_says_so_rather_than_crashing(signed_in):
    response = signed_in.get(f"/history/{'0' * 40}")
    assert response.status_code == 404
    assert "went wrong" in response.text


def test_history_needs_the_password(client):
    assert client.get("/history", follow_redirects=False).status_code == 303


# --- operational -----------------------------------------------------------

def test_healthz_needs_no_password(client):
    """The host pings this to decide whether the container is alive."""
    assert client.get("/healthz").json() == {"ok": True}


def test_an_alias_type_is_shown_by_what_it_does_and_not_rewritten(signed_in, store):
    """Seven shipped rows are spelled with an accepted alias, not a mistake.

    Showing the raw alias makes those rows look broken to someone who has never
    heard of it. Rewriting them to the canonical spelling would put seven type
    changes into the diff of an unrelated edit. Neither is acceptable, so the
    option reads as what the type does and keeps the value the file had.
    """
    rows = store.rows()
    rows[0].type = "grades_due"          # an alias for informational
    store.save(rows, "Seeder", "used an alias")

    html = signed_in.get("/").text
    assert '<option value="grades_due" selected' in html
    assert "Just listed" in html

    fields = form_from(html)
    assert fields["row-0-type"] == "grades_due"
    fields["row-0-label"] = "Renamed but same type"
    signed_in.post("/save", data=fields, follow_redirects=False)

    assert store.rows()[0].type == "grades_due", "the alias was rewritten"
    assert "changed from" not in store.history()[0].summary


# --- things a review found ------------------------------------------------

@pytest.mark.parametrize("target,expected", [
    ("/history", "/history"),
    ("https://evil.example/phish", "/"),
    ("//evil.example/phish", "/"),          # protocol-relative, not a path
    ("", "/"),
    (None, "/"),
])
def test_login_only_redirects_to_this_site(client, target, expected):
    """`next` is redirected to after a successful login.

    Unchecked, /login?next=https://evil.example/ signs a volunteer in and drops
    them somewhere that can ask for the shared password again -- with the real
    host sitting in their history to make it look right.
    """
    data = {"password": PASSWORD}
    if target is not None:
        data["next"] = target
    response = client.post("/login", data=data, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == expected


def test_an_expired_session_does_not_silently_discard_a_save(client):
    """A 303 on POST makes the browser re-issue it as a GET with no body, so
    somebody who left the tab open past the expiry and pressed Save would watch
    ten edits vanish -- and land on a /save that does not answer GET."""
    response = client.post("/save", data={"row-0-from": "2400-10-15"},
                           follow_redirects=False)
    assert response.status_code == 401
    assert "expired" in response.text
    assert "Back button" in response.text


def test_publishing_refuses_a_draft_it_did_not_check(signed_in, store, remote,
                                                     tmp_path):
    """The gate and the push have to be looking at the same thing.

    publish() syncs on its way to the push. If the draft moved between the page
    being checked and the button being pressed, the calendar that was validated
    is not the calendar that goes out.
    """
    fields = form_from(signed_in.get("/").text)
    i = next(n for n in range(20)
             if fields.get(f"row-{n}-label") == "Curriculum Night")
    fields[f"row-{i}-from"] = "2400-10-22"
    signed_in.post("/save", data=fields, follow_redirects=False)
    # The sha the publish page showed, carried in its form.
    reviewed = re.search(r'name="reviewed" value="([0-9a-f]+)"',
                         signed_in.get("/publish").text).group(1)

    # Someone else pushes to draft between the check and the press.
    sam = Store.clone(str(remote), tmp_path / "sam")
    rows = sam.rows()
    rows.append(type(rows[0])(date="2401-02-02", type="ptsa_event",
                              label="Something nobody reviewed"))
    sam.save(rows, "Sam", "a change nobody looked at")

    response = signed_in.post("/publish", data={"reviewed": reviewed},
                              follow_redirects=False)
    assert response.status_code == 409
    assert "while this page was open" in response.text
    assert "Something nobody reviewed" not in git(
        remote, "show", "main:data/all_events.csv")


def test_one_page_view_lays_the_calendar_out_once(signed_in, store):
    """The dates page needs the page laid out for publish_problems(), and the
    browser then fetches the preview image as a separate request. Without a
    cache that is two full WeasyPrint layouts -- about 1.5s -- for one view."""
    from calendar_gen import pipeline

    calls = []
    original = pipeline.build

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    pipeline.build = counted
    try:
        signed_in.get("/")
        signed_in.get("/preview.png")
    finally:
        pipeline.build = original

    assert len(calls) == 1, f"built the calendar {len(calls)} times for one view"


def test_the_cache_does_not_serve_a_stale_calendar(signed_in, store):
    """Cached against the commit, so a save has to invalidate it."""
    before = signed_in.get("/preview.png").content

    fields = form_from(signed_in.get("/").text)
    fields.update({"row-99-from": "2400-12-05", "row-99-to": "",
                   "row-99-type": "ptsa_event", "row-99-label": "Winter Social",
                   "row-99-notes": "", "row-99-deleted": "0"})
    signed_in.post("/save", data=fields, follow_redirects=False)

    assert signed_in.get("/preview.png").content != before


def test_the_preview_image_is_a_real_png(signed_in):
    """There was no test on /preview.png at all, and its Pillow dependency
    arrived only transitively through WeasyPrint."""
    response = signed_in.get("/preview.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


# --- starting a new school year --------------------------------------------

def test_the_new_year_form_offers_the_year_after_the_newest(signed_in):
    html = signed_in.get("/new-year").text
    assert "Start the 2401-02 calendar" in html
    assert "lwsd.org/calendar" in html


def test_the_new_year_form_insists_on_the_dates_it_needs(signed_in):
    response = signed_in.post("/new-year", data={"start_year": 2401,
                                                 "first_day": "",
                                                 "last_day": "",
                                                 "early_release_start": ""})
    assert response.status_code == 400
    assert "Please fill in" in response.text


def new_year_step_one(client, **overrides):
    data = {"start_year": 2401, "first_day": "2401-08-30",
            "last_day": "2402-06-15", "early_release_start": "2401-09-08"}
    data.update(overrides)
    return client.post("/new-year", data=data)


def test_the_second_screen_proposes_last_years_dates(signed_in):
    html = new_year_step_one(signed_in).text
    assert "Curriculum Night" in html
    assert "2401-10-14" in html, "expected the 364-day shift of 2400-10-15"
    assert "suggestions, not" in html, "the page must not present these as data"


def test_nothing_unticked_is_carried_over(signed_in, store):
    """The ticking is the review. A row nobody ticked is not sent at all --
    its inputs have no name until the checkbox gives them one -- so an
    unreviewed guess cannot reach the CSV even by mistake.
    """
    # Compared by date as well as label: the fixture already has a row called
    # "Last Day of School" for the current year.
    before = {(r.first_day, r.label) for r in store.rows()}
    response = signed_in.post("/new-year/create", data={
        "start_year": 2401, "first_day": "2401-08-30",
        "last_day": "2402-06-15", "early_release_start": "2401-09-08",
    }, follow_redirects=False)
    assert response.status_code == 303

    added = [r for r in store.rows() if (r.first_day, r.label) not in before]
    # Only the first and last days, which the person typed themselves.
    assert sorted(r.label for r in added) == ["First Day (Grades 1-12)",
                                              "Last Day of School"]
    assert not any(r.label == "Curriculum Night" and r.first_day.startswith("2401")
                   for r in store.rows()), "an unticked suggestion was written"


def test_a_ticked_date_is_carried_over(signed_in, store):
    signed_in.post("/new-year/create", data={
        "start_year": 2401, "first_day": "2401-08-30",
        "last_day": "2402-06-15", "early_release_start": "2401-09-08",
        "row-0-from": "2401-10-14", "row-0-to": "", "row-0-type": "ptsa_event",
        "row-0-label": "Curriculum Night", "row-0-notes": "",
        "row-0-deleted": "0",
    }, follow_redirects=False)

    carried = [r for r in store.rows()
               if r.label == "Curriculum Night" and r.date == "2401-10-14"]
    assert len(carried) == 1


def test_creating_a_year_writes_a_config_that_builds(signed_in, store):
    signed_in.post("/new-year/create", data={
        "start_year": 2401, "first_day": "2401-08-30",
        "last_day": "2402-06-15", "early_release_start": "2401-09-08",
        "kindergarten_first_day": "2401-09-02",
        "row-0-from": "2401-10-14", "row-0-to": "", "row-0-type": "ptsa_event",
        "row-0-label": "Curriculum Night", "row-0-notes": "",
        "row-0-deleted": "0",
    }, follow_redirects=False)

    from calendar_gen import pipeline
    built = pipeline.build(store.csv_path, store.years_dir, requested=2401)
    assert built.label == "2401-02"
    assert built.fits_one_page() is True
    assert any("Curriculum Night" in d.label for d in built.important)


def test_creating_a_year_does_not_disturb_the_published_one(signed_in, store):
    """Staging next year must leave this year's calendar exactly as it is --
    that is the whole point of being able to prepare it early."""
    from calendar_gen import pipeline
    before = pipeline.build(store.csv_path, store.years_dir, 2400).html

    signed_in.post("/new-year/create", data={
        "start_year": 2401, "first_day": "2401-08-30",
        "last_day": "2402-06-15", "early_release_start": "2401-09-08",
    }, follow_redirects=False)

    after = pipeline.build(store.csv_path, store.years_dir, 2400)
    assert after.html == before, "staging next year changed this year's page"
    assert store.has_unpublished_changes() is True, "it published itself"


def test_staging_next_year_does_not_steal_the_published_slot(tmp_path):
    """Which calendar `calendar.pdf` means must not move because a year was
    staged. Deliberately built with no year requested: naming one bypasses
    resolve_start_year, the single piece of logic that decides this.

    On real years, not the fixture's 2400 -- with no config for the year we are
    actually in, resolve_start_year falls back to the newest one it has, which
    is deliberate ("so the build keeps working in the gap") and would make this
    look broken when it is not.
    """
    from calendar_gen import school_year

    from web import newyear

    this_year = school_year.current_start_year()
    for start in (this_year, this_year + 1):
        (tmp_path / f"{school_year.label_for(start)}.toml").write_text(
            newyear.config_toml(
                organization="T", label=school_year.label_for(start),
                early_release_start=f"{start}-09-09",
                last_day=f"{start + 1}-06-16",
                boxed_days=[f"{start}-08-31", f"{start + 1}-06-16"]))

    resolved, why = school_year.resolve_start_year(tmp_path)
    assert resolved == this_year, (
        f"staging {this_year + 1} moved the published year to {resolved} ({why})")


def test_you_can_switch_to_editing_the_year_you_just_created(signed_in):
    """Creating next year is useless if there is then no way to look at it."""
    signed_in.post("/new-year/create", data={
        "start_year": 2401, "first_day": "2401-08-30",
        "last_day": "2402-06-15", "early_release_start": "2401-09-08",
    }, follow_redirects=False)

    html = signed_in.get("/?year=2401-02").text
    assert "2401-02 dates" in html
    assert 'id="year-picker"' in html, "no way to switch between the two years"

    import io, pypdf
    pdf = pypdf.PdfReader(io.BytesIO(
        signed_in.get("/preview.pdf?year=2401-02").content))
    assert "2401-02" in pdf.pages[0].extract_text()


def test_a_year_that_already_exists_is_refused(signed_in, store):
    response = signed_in.post("/new-year/create", data={
        "start_year": 2400, "first_day": "2400-08-30",
        "last_day": "2401-06-15", "early_release_start": "2400-09-08",
    }, follow_redirects=False)
    assert response.status_code == 409
    assert "already exists" in response.text


def test_the_new_year_needs_the_password(client):
    assert client.get("/new-year", follow_redirects=False).status_code == 303


def test_a_year_whose_dates_do_not_build_is_not_created_at_all(signed_in, store):
    """One mistyped year in a date box used to leave a year nothing could fix.

    There is no page that edits a year config; add_year refuses a label that
    already exists; next_year_after has moved past it; and restore cannot help
    because `git checkout <sha> -- data` does not delete a file added since. The
    only remedy was editing git by hand -- the thing the editor exists to avoid.
    """
    before = store.head()
    response = signed_in.post("/new-year/create", data={
        "start_year": 2401, "first_day": "2401-08-30",
        # 2401 rather than 2402: one keystroke, and the year cannot be built.
        "last_day": "2401-06-15", "early_release_start": "2401-09-08",
    }, follow_redirects=False)

    assert response.status_code == 400
    assert "has not been created" in response.text
    assert store.head() == before, "it committed a year that cannot be built"
    assert not (store.years_dir / "2401-02.toml").exists()
    assert signed_in.get("/new-year").status_code == 200


def test_the_boundary_dates_are_not_added_twice(signed_in, store):
    """The first and last days are appended from the form, and are also on
    offer in the carry-over list. Both would land the same event on two dates:
    build_important_dates groups by label and unions them, so the page reads
    "8/30, 9/1  First Day" and the extra day earns a stray asterisk."""
    signed_in.post("/new-year/create", data={
        "start_year": 2401, "first_day": "2401-08-30",
        "last_day": "2402-06-15", "early_release_start": "2401-09-08",
        # The same first day, ticked in the carry-over list.
        "row-0-from": "2401-08-30", "row-0-to": "", "row-0-type": "first_day",
        "row-0-label": "First Day (Grades 1-12)", "row-0-notes": "",
        "row-0-deleted": "0",
    }, follow_redirects=False)

    firsts = [r for r in store.rows()
              if r.type == "first_day" and r.first_day.startswith("2401-08")]
    assert len(firsts) == 1, f"the first day was written {len(firsts)} times"


def test_it_will_not_invent_an_organization_name(signed_in, store):
    """It used to fall back to the literal string "PTSA", which printed a wrong
    name on the sheet families receive -- a guess becoming data, in the one
    flow whose whole design is that guesses cannot."""
    (store.years_dir / "2400-01.toml").write_text("this is not toml [[[")
    response = signed_in.post("/new-year/create", data={
        "start_year": 2401, "first_day": "2401-08-30",
        "last_day": "2402-06-15", "early_release_start": "2401-09-08",
    }, follow_redirects=False)
    assert response.status_code == 409
    assert "headed with a guess" in response.text


@pytest.mark.parametrize("bad", [
    {"start_year": ""},
    {"start_year": "not a year"},
    {"first_day": ""},
    {"last_day": "Sept 2"},
])
def test_a_malformed_create_says_so_rather_than_committing_it(signed_in, store,
                                                              bad):
    """These arrive in hidden fields and are interpolated straight into TOML.
    An empty one produced `last_day = `, which is not parseable at all, in a
    file that was then committed and pushed."""
    data = {"start_year": 2401, "first_day": "2401-08-30",
            "last_day": "2402-06-15", "early_release_start": "2401-09-08"}
    data.update(bad)
    before = store.head()
    response = signed_in.post("/new-year/create", data=data,
                              follow_redirects=False)
    assert response.status_code == 400
    assert store.head() == before


def test_a_staged_year_that_cannot_build_blocks_publishing(signed_in, store):
    """Publishing pushes the whole CSV, and on 1 August the scheduled build
    switches which year calendar.pdf means. A gate that only looked at today's
    year would let a broken staged year sit on main with CI green and take the
    calendar down on the day it became current."""
    signed_in.post("/new-year/create", data={
        "start_year": 2401, "first_day": "2401-08-30",
        "last_day": "2402-06-15", "early_release_start": "2401-09-08",
    }, follow_redirects=False)

    # Break next year only. This year is untouched and still builds.
    rows = store.rows()
    for row in rows:
        if row.first_day.startswith("2401-08"):
            row.type = "not_a_real_type"
    store.save(rows, "Someone", "broke next year")

    response = signed_in.post("/publish", follow_redirects=False)
    assert response.status_code == 422
    assert "2401-02" in response.text
    assert store.has_unpublished_changes() is True


def test_saving_keeps_you_on_the_year_you_were_editing(signed_in, store):
    signed_in.post("/new-year/create", data={
        "start_year": 2401, "first_day": "2401-08-30",
        "last_day": "2402-06-15", "early_release_start": "2401-09-08",
    }, follow_redirects=False)

    html = signed_in.get("/?year=2401-02").text
    assert '<input type="hidden" name="year" value="2401-02">' in html

    fields = form_from(html)
    response = signed_in.post("/save", data=fields, follow_redirects=False)
    assert response.headers["location"] == "/?year=2401-02"


def test_the_year_picker_is_outside_the_unsaved_changes_form(signed_in, store):
    """A <select> fires a bubbling `input` event before `change`. Inside the
    form that set the dirty flag, so every year switch asked "Leave site?" on a
    page nobody had edited -- and answering Stay left the picker showing one
    year beside another year's page."""
    signed_in.post("/new-year/create", data={
        "start_year": 2401, "first_day": "2401-08-30",
        "last_day": "2402-06-15", "early_release_start": "2401-09-08",
    }, follow_redirects=False)

    html = signed_in.get("/").text
    picker = html.index('id="year-picker"')
    form = html.index('id="dates-form"')
    assert picker < form, "the picker is inside the form that guards edits"


def test_the_kindergarten_date_survives_a_validation_error(signed_in):
    """It is optional, so a person is unlikely to notice it being cleared --
    and would end up with no kindergarten box on the calendar."""
    response = signed_in.post("/new-year", data={
        "start_year": 2401, "first_day": "2401-08-30",
        "kindergarten_first_day": "2401-09-02",
        "last_day": "2402-06-15", "early_release_start": "",
    })
    assert response.status_code == 400
    assert 'value="2401-09-02"' in response.text


def test_last_years_leftover_config_does_not_block_publishing(signed_in, store):
    """After a year roll the old config is normally still on disk while its
    rows are not, so it no longer builds -- and never will again, because
    resolve_start_year only moves forward.

    Gating it blocked publishing on the real repository permanently, with no
    way for anyone to clear it: the fix would have been deleting a file the
    editor has no page for. Found by running the editor against the shipped
    data rather than the fixture.
    """
    from calendar_gen import school_year

    # A year that has certainly ended, with no rows anywhere near it.
    past = school_year.current_start_year() - 3
    label = school_year.label_for(past)
    (store.years_dir / f"{label}.toml").write_text(
        f'[calendar]\norganization = "T"\n\n[dates]\n'
        f'early_release_start = {past}-09-09\nlast_day = {past + 1}-06-16\n'
        f'boxed_days = [{past}-08-31, {past + 1}-06-16]\n')

    rows = store.rows()
    rows.append(type(rows[0])(date="2400-12-05", type="ptsa_event",
                              label="Winter Social"))
    store.save(rows, "Allison", "something to publish")

    assert label not in signed_in.get("/publish").text, (
        "an ended year is being reported as a reason not to publish")
    assert signed_in.post("/publish", follow_redirects=False).status_code == 303
