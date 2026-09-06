"""The calendar editor.

What this is: a form over `data/all_events.csv`, a preview, and a publish
button. What it is emphatically not: a second way to draw a calendar. Every
page it shows comes from `calendar_gen`, and the PDF that goes to families is
built by the same deploy workflow that has always built it. `DECISIONS.md`
records what happened the last time this repo had two things that could render
a calendar; the answer is not "be careful", it is "have one".

So the division is:

    calendar_gen.pipeline   decides what is valid and what the page looks like
    web.store               remembers, with git doing the remembering
    this module             turns those into pages and buttons

If a rule about dates ever needs writing here, it is in the wrong place.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from calendar_gen import event_types, pipeline
from calendar_gen import school_year as school_year_mod

from . import changes as changes_mod
from . import csvio, newyear
from .auth import COOKIE_NAME, SESSION_MAX_AGE, Auth, LoginRateLimit
from .store import Conflict, Store, StoreError

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def _bool_env(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes"}


def safe_next(target: str | None) -> str:
    """A path on this site, or "/".

    `next` arrives from the query string and is redirected to after a
    successful login. Unchecked, a link like
    /login?next=https://evil.example/ signs a volunteer in and lands them
    somewhere else that can ask for the shared password again -- with the real
    host sitting in their history to make it look right. Only a single-slash
    path is allowed: "//evil.example" is a protocol-relative URL, not a path.
    """
    if not target or not target.startswith("/") or target.startswith("//"):
        return "/"
    # Backslashes and control characters go too. Browsers normalise "\" to "/"
    # inside a URL, so "/\evil.example" is delivered as "//evil.example" -- a
    # protocol-relative URL to somebody else's host, straight through a check
    # that only looked for a doubled forward slash. A control character in a
    # redirect has no business being there either.
    if "\\" in target or any(c < " " or c == "\x7f" for c in target):
        return "/"
    return target


def create_app(store: Store | None = None, auth: Auth | None = None) -> FastAPI:
    """Build the app.

    Takes its store and auth as arguments so the tests can hand it a throwaway
    repository and a known password. Nothing here reads the environment except
    as a fallback, which is what keeps the tests exercising the same wiring the
    deployment uses rather than a special path of their own.
    """
    app = FastAPI(title="PTSA Calendar Editor",
                  # No API for anyone to consume, so no schema to publish.
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store or _store_from_env()
    app.state.auth = auth or Auth.from_env()
    app.state.limiter = LoginRateLimit()
    #: {(sha, year): (Build | None, error | None)}. Keyed by year as well as
    #: commit: with two years configured, one slot meant two people looking at
    #: two years evicted each other on every request and each paid the ~0.75s
    #: layout the cache exists to avoid. Cleared wholesale when the draft
    #: moves, which is what keeps it from serving a stale page.
    app.state.build_cache = {}
    # Cookies go out Secure unless told otherwise, so a misconfigured proxy
    # cannot quietly downgrade the session to plain HTTP. Tests and local
    # development set it to false explicitly.
    app.state.secure_cookies = _bool_env("SECURE_COOKIES", True)

    templates = Jinja2Templates(directory=str(HERE / "templates"))

    def resolved_type(name: str):
        """The declared type a stored value means, or None if it means nothing.

        Seven of the shipped rows are spelled with an alias -- kinder_family_conn,
        grades_due -- which are accepted spellings, not mistakes. Showing the raw
        alias in the dropdown makes those rows look broken to someone who has
        never heard of them; rewriting them to the canonical name would put
        seven type changes in the diff of an unrelated edit. So the option is
        labelled with what the type actually does and still carries the value
        the file already had.
        """
        try:
            return event_types.resolve(name)
        except event_types.UnknownEventType:
            return None

    templates.env.globals["resolved_type"] = resolved_type
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

    def render(request: Request, template: str, /, status_code: int = 200,
               **context) -> HTMLResponse:
        # template is positional-only because one of the context keys is "name"
        # (whoever is editing) and a parameter of that name would collide.
        # status_code is named explicitly rather than swept into **context,
        # where it would silently become a template variable and leave every
        # error page returning 200 -- which is what it did.
        return templates.TemplateResponse(request, template, context,
                                          status_code=status_code)

    # --- session ---------------------------------------------------------

    def session(request: Request) -> dict:
        data = app.state.auth.read(request.cookies.get(COOKIE_NAME))
        if data is None:
            raise HTTPException(status_code=401)
        return data

    @app.exception_handler(401)
    async def to_login(request: Request, exc: HTTPException):
        if request.method == "POST":
            # Never redirect a POST here. A 303 makes the browser re-issue it as
            # a GET with no body, so somebody who left the tab open past the
            # session expiry, edited ten dates and pressed Save would watch all
            # of it vanish -- and land on a /save that does not answer GET. The
            # page they typed on is still one Back away, so say so.
            return render(request, "login.html", next="/", status_code=401,
                          error="Your session expired, so that was not saved. "
                                "Sign in again, then press your browser's Back "
                                "button -- your changes are still on the page.")
        return RedirectResponse(f"/login?next={safe_next(request.url.path)}",
                                status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request, next: str = "/"):
        return render(request, "login.html", next=safe_next(next), error=None)

    @app.post("/login")
    def login(request: Request, password: str = Form(""),
              name: str = Form(""), next: str = Form("/")):
        who = request.client.host if request.client else "?"
        if app.state.limiter.blocked(who):
            return render(request, "login.html", next=next, status_code=429,
                          error="Too many tries. Wait a few minutes and try again.")
        if not app.state.auth.check(password):
            app.state.limiter.record_failure(who)
            return render(request, "login.html", next=next,
                          error="That password is not right.")

        app.state.limiter.clear(who)
        response = RedirectResponse(safe_next(next), status_code=303)
        response.set_cookie(
            COOKIE_NAME, app.state.auth.issue(name),
            max_age=SESSION_MAX_AGE, httponly=True,
            secure=app.state.secure_cookies, samesite="lax",
        )
        return response

    @app.post("/logout")
    def logout():
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(COOKIE_NAME)
        return response

    # --- the calendar ----------------------------------------------------

    def build_current(store: Store, year: int | None = None):
        """The draft as `build.py` would build it, or the reason it cannot.

        Returns (Build, error, sha). A calendar too broken to render still has
        to be editable -- that is the state someone needs the editor for most --
        so a failure here is something to show at the top of the page, never
        something to refuse to load.

        ``year`` selects which school year to look at; None means the one
        `build.py` would pick, which is the one that gets published. The CSV
        holds every year at once, so this is a view, not a filter on the data.

        Cached against the commit it was built from and the year asked for.
        Laying the page out costs about 0.75s and a single view of the dates
        page needs it twice: once for publish_problems() and again when the
        browser fetches the preview image, which used to arrive as a separate
        request with a fresh Build and an empty document cache.
        """
        if year is None:
            # Resolved before the lookup so the default year and its own number
            # are one cache entry. The publish page asks for both -- once as
            # None, once as an int -- and used to lay the same page out twice.
            try:
                year, _ = school_year_mod.resolve_start_year(store.years_dir)
            except (FileNotFoundError, ValueError):
                year = None
        sha = store.head()
        cache = app.state.build_cache
        if cache and next(iter(cache))[0] != sha:
            cache.clear()          # the draft moved; every year is stale
        if (sha, year) in cache:
            built, error = cache[(sha, year)]
            return built, error, sha
        try:
            built = pipeline.build(store.csv_path, store.years_dir, year)
            error = None
        except pipeline.Blocked as exc:
            built, error = None, str(exc)
        cache[(sha, year)] = (built, error)
        return built, error, sha

    def start_year_of(label: str | None) -> int | None:
        """"2027-28" -> 2027, and anything unrecognisable -> the default year."""
        try:
            return int((label or "").split("-")[0])
        except ValueError:
            return None

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, year: str = "", sess: dict = Depends(session)):
        store: Store = app.state.store
        store.sync()
        wanted = start_year_of(year)
        build, error, _ = build_current(store, wanted)
        return render(
            request, "index.html",
            rows=sorted(store.rows(), key=csvio.Row.sort_key),
            years=store.year_labels(),
            viewing=build.label if build else year,
            types=event_types.choices(),
            build=build, error=error,
            base=store.head(),
            pending=store.has_unpublished_changes(),
            changes=_pending_changes(store),
            name=sess.get("name", ""),
        )

    def _organization(store: Store) -> str | None:
        """The organization name from the existing config, or None.

        Read rather than asked, so next year cannot end up with a second
        spelling of "Horace Mann PTSA" heading its page. None when there is no
        readable config: it used to fall back to the literal string "PTSA",
        which printed a wrong name on the sheet families receive and named the
        file after it -- a guess quietly becoming data, in the one flow whose
        whole design is that guesses cannot.
        """
        try:
            year, _ = pipeline.load_year(store.years_dir)
            return year.organization
        except pipeline.Blocked:
            return None

    def _pending_changes(store: Store) -> list:
        try:
            return changes_mod.summarise(
                store.rows_at(store.published_head()), store.rows())
        except StoreError:
            return []

    @app.post("/save")
    async def save(request: Request, sess: dict = Depends(session)):
        store: Store = app.state.store
        form = await request.form()
        rows = _rows_from_form(form)
        author = (form.get("name") or sess.get("name") or "").strip()
        base = form.get("base") or None

        summary = changes_mod.describe(
            changes_mod.summarise(store.rows(), rows))
        try:
            store.save(rows, author, summary, base=base)
        except Conflict as exc:
            return render(request, "conflict.html", message=str(exc),
                          status_code=409)
        except StoreError as exc:
            return render(request, "error.html", message=str(exc),
                          status_code=500)

        # Back to the year they were editing. Landing on the published year
        # after every save meant re-picking it each time, and the warnings
        # panel they then read would be about a different year than the rows
        # they had just changed.
        year = (form.get("year") or "").strip()
        response = RedirectResponse(f"/?year={year}" if year else "/",
                                    status_code=303)
        if author:
            response.set_cookie(
                COOKIE_NAME, app.state.auth.issue(author),
                max_age=SESSION_MAX_AGE, httponly=True,
                secure=app.state.secure_cookies, samesite="lax",
            )
        return response

    @app.get("/preview.png")
    def preview_image(year: str = "", sess: dict = Depends(session)):
        """The preview as a picture.

        The obvious way to show a PDF in a page is an iframe, and on a desktop
        browser it works. On phones it usually shows nothing at all, and in
        some embedded viewers it shows a black rectangle -- which is what it
        did here. A person checking whether they typed the date right should
        not have to know which browser renders PDFs inline. An image works
        everywhere; the PDF is still one click away for anyone who wants to
        print or send it.
        """
        build, error, _ = build_current(app.state.store, start_year_of(year))
        if build is None:
            raise HTTPException(status_code=422, detail=error)
        return Response(_page_png(build), media_type="image/png",
                        headers={"Cache-Control": "no-store"})

    @app.get("/preview.pdf")
    def preview(year: str = "", sess: dict = Depends(session)):
        build, error, _ = build_current(app.state.store, start_year_of(year))
        if build is None:
            raise HTTPException(status_code=422, detail=error)
        return Response(
            build.pdf_bytes(), media_type="application/pdf",
            headers={"Content-Disposition":
                     f'inline; filename="DRAFT-{build.filename}"'},
        )

    def _blockers(store: Store):
        """Everything wrong with a year that is, or will become, the live one.

        Publishing pushes the whole CSV, and on 1 August the scheduled build
        switches which year `calendar.pdf` means. A staged year that does not
        build would sail past a gate that only looked at today's year, sit on
        main with CI green, and take the published calendar down on the day it
        became current -- the eight-month staleness this pipeline is written
        against, just delayed.

        Years that have already ended are deliberately not gated. Last year's
        config is normally still on disk after a roll while its rows are not,
        so it does not build -- and it never will again, because
        resolve_start_year only ever moves forward. Gating it blocked
        publishing on this very repository, permanently, with no way for
        anybody to clear it: the fix would have been deleting a file the editor
        has no page for.
        """
        from calendar_gen import school_year

        current = school_year.current_start_year()
        problems = []

        # The year the build actually resolves to is always gated, even when
        # it is in the past. With no config for the year we are in,
        # resolve_start_year falls back to the newest there is -- and that is
        # the year CI's `--check --strict` will build. Skipping it because it
        # has ended meant an empty gate, a green publish page, "the new PDF is
        # being built now", and a workflow that rejected the same data.
        try:
            resolved, _why = school_year.resolve_start_year(store.years_dir)
        except (FileNotFoundError, ValueError):
            resolved = None

        for label in store.year_labels():
            year = start_year_of(label)
            # Ended years are otherwise left alone: last year's config normally
            # outlives its rows, and gating it blocked publishing on the real
            # repository with no way for anyone to clear it.
            if year is None or (year < current and year != resolved):
                continue
            build, error, _ = build_current(store, year)
            if error:
                problems.append(f"{label}: {error}")
            else:
                problems += [f"{label}: {p}" for p in build.publish_problems()]
        return problems

    @app.get("/publish", response_class=HTMLResponse)
    def publish_form(request: Request, sess: dict = Depends(session)):
        store: Store = app.state.store
        store.sync()
        build, error, sha = build_current(store)
        blockers = _blockers(store)
        return render(
            request, "publish.html",
            changes=_pending_changes(store),
            pending=store.has_unpublished_changes(),
            blockers=blockers, build=build, sha=sha,
        )

    @app.post("/publish")
    def do_publish(request: Request, reviewed: str = Form(""),
                   sess: dict = Depends(session)):
        store: Store = app.state.store
        # Sync before validating, not after. publish() syncs on its way to the
        # push, so validating first and syncing second would check one draft
        # and send another.
        store.sync()
        build, error, checked = build_current(store)

        # `reviewed` is the draft the publish page showed. If the draft has
        # moved since -- somebody else saved while this page sat open -- then
        # publishing now would send a change this person never saw, and it
        # would pass every gate, because the gate would have re-run on the new
        # content. Validated and reviewed have to be the same thing.
        if reviewed and reviewed != checked:
            return render(request, "conflict.html", status_code=409,
                          message="Someone else saved while this page was open, "
                                  "so nothing has been published. Look at the "
                                  "changes again -- there are more of them now.")
        blockers = _blockers(store)
        if blockers:
            # The last line of defence, not the first: the button is already
            # disabled. Someone with a stale page open must still not be able
            # to publish a calendar that does not fit on a page.
            return render(request, "publish.html", blockers=blockers,
                          changes=_pending_changes(store), build=build,
                          pending=store.has_unpublished_changes(),
                          sha=checked, status_code=422)
        try:
            store.publish(expected=checked)
        except Conflict as exc:
            return render(request, "conflict.html", message=str(exc),
                          status_code=409)
        except StoreError as exc:
            return render(request, "error.html", message=str(exc),
                          status_code=500)
        return RedirectResponse("/published", status_code=303)

    @app.get("/published", response_class=HTMLResponse)
    def published(request: Request, sess: dict = Depends(session)):
        return render(request, "published.html",
                      pdf_url=os.environ.get("PUBLISHED_PDF_URL", ""))

    # --- history ---------------------------------------------------------

    @app.get("/history", response_class=HTMLResponse)
    def history(request: Request, sess: dict = Depends(session)):
        store: Store = app.state.store
        store.sync()
        return render(request, "history.html", versions=store.history(),
                      current=store.head())

    @app.get("/history/{sha}", response_class=HTMLResponse)
    def version(request: Request, sha: str, sess: dict = Depends(session)):
        store: Store = app.state.store
        try:
            old = store.rows_at(sha)
        except StoreError as exc:
            return render(request, "error.html", message=str(exc), status_code=404)
        return render(request, "version.html", sha=sha,
                      changes=changes_mod.summarise(old, store.rows()),
                      rows=sorted(old, key=csvio.Row.sort_key))

    @app.post("/history/{sha}/restore")
    def restore(request: Request, sha: str, sess: dict = Depends(session)):
        store: Store = app.state.store
        try:
            store.restore(sha, sess.get("name", ""))
        except StoreError as exc:
            return render(request, "error.html", message=str(exc), status_code=404)
        return RedirectResponse("/", status_code=303)

    # --- starting a new school year --------------------------------------

    @app.get("/new-year", response_class=HTMLResponse)
    def new_year_form(request: Request, sess: dict = Depends(session)):
        store: Store = app.state.store
        store.sync()
        start = newyear.next_year_after(store.years_dir)
        return render(request, "new-year.html",
                      label=newyear.label_for(start), start_year=start,
                      existing=store.year_labels(),
                      suggested=newyear.suggest_dates(start), error=None)

    @app.post("/new-year", response_class=HTMLResponse)
    def new_year_review(request: Request, start_year: int = Form(...),
                        first_day: str = Form(""), last_day: str = Form(""),
                        early_release_start: str = Form(""),
                        kindergarten_first_day: str = Form(""),
                        sess: dict = Depends(session)):
        """Second screen: which of last year's dates carry over.

        Nothing is written yet. Every suggestion here is a guess at where an
        event lands a year on, and a guess must not become data without a
        person looking at it -- so this is the looking, and the next step only
        writes what was ticked.
        """
        store: Store = app.state.store
        store.sync()
        label = newyear.label_for(start_year)

        missing = [name for name, value in
                   (("the first day", first_day), ("the last day", last_day),
                    ("the first early-release Wednesday", early_release_start))
                   if not value]
        if missing:
            return render(
                request, "new-year.html", status_code=400,
                label=label, start_year=start_year,
                existing=store.year_labels(),
                # Everything they typed, including the optional kindergarten
                # date -- which used to be dropped here, and being optional is
                # easy not to notice missing.
                suggested={"first_day": first_day, "last_day": last_day,
                           "early_release_start": early_release_start,
                           "kindergarten_first_day": kindergarten_first_day},
                error=f"Please fill in {', and '.join(missing)}.")

        previous = start_year - 1
        return render(
            request, "new-year-dates.html",
            label=label, start_year=start_year,
            previous_label=newyear.label_for(previous),
            proposals=newyear.propose(store.rows(), previous),
            types=event_types.choices(),
            first_day=first_day, last_day=last_day,
            early_release_start=early_release_start,
            kindergarten_first_day=kindergarten_first_day,
        )

    @app.post("/new-year/create")
    async def new_year_create(request: Request, sess: dict = Depends(session)):
        store: Store = app.state.store
        form = await request.form()

        def fail(message: str, status: int = 400):
            return render(request, "error.html", message=message,
                          status_code=status)

        # These arrive in hidden fields, and every one of them is interpolated
        # into a TOML file that is then committed and pushed. An empty or
        # malformed value used to produce `last_day = ` -- not parseable TOML
        # at all -- in a year nothing could later fix.
        try:
            start_year = int(form.get("start_year") or "")
        except (TypeError, ValueError):
            return fail("That form was missing which school year to create. "
                        "Start again from New year.")

        dates = {}
        for field in ("first_day", "last_day", "early_release_start",
                      "kindergarten_first_day"):
            raw = (form.get(field) or "").strip()
            if not raw and field == "kindergarten_first_day":
                dates[field] = ""
                continue
            try:
                dates[field] = dt.date.fromisoformat(raw).isoformat()
            except ValueError:
                return fail(f"{raw or 'A date'} is not a date the calendar can "
                            f"use. Go back and pick it from the date box.")

        organization = _organization(store)
        if organization is None:
            return fail(
                "There is no readable school-year config to take the "
                "organization's name from, so the new year would be headed "
                "with a guess. Fix the existing year first.", 409)

        label = newyear.label_for(start_year)
        first_day = dates["first_day"]
        last_day = dates["last_day"]
        kinder = dates["kindergarten_first_day"]

        config = newyear.config_toml(
            organization=organization, label=label,
            early_release_start=dates["early_release_start"],
            last_day=last_day,
            boxed_days=[d for d in (first_day, kinder, last_day) if d],
            source_label=newyear.label_for(start_year - 1),
        )

        carried = _rows_from_form(form)
        # The two dates the config names still have to be listed, or the page
        # draws a box on a day with nothing beside it. Skipped when the same
        # event was already carried over: build_important_dates groups by label
        # and unions the dates, so a duplicate prints as one event on two days
        # ("8/30, 9/1  First Day") and earns a stray asterisk. Nothing in the
        # validator catches that, so it has to not happen.
        already = {(r.first_day, r.type) for r in carried}
        for when, kind, name in ((first_day, "first_day", "First Day (Grades 1-12)"),
                                 (kinder, "first_day", "First Day (Kindergarten)"),
                                 (last_day, "last_day", "Last Day of School")):
            if when and (when, kind) not in already:
                carried.append(csvio.Row(date=when, type=kind, label=name))
                # Added as we go, or entering the same date for the first day
                # and kindergarten's first day -- which the form invites, since
                # "leave empty if it is the same day" is a hint, not a rule --
                # writes both rows and spends two lines of the dates list on
                # one day, on a page the rest of this repo fights to keep to
                # one sheet.
                already.add((when, kind))

        def validate(csv_path, years_dir):
            pipeline.build(csv_path, years_dir, start_year)

        try:
            store.add_year(label, config, carried, sess.get("name", ""),
                           f"started {label} with {len(carried)} dates",
                           validate=validate)
        except pipeline.Blocked as exc:
            # Nothing was committed. Say what is wrong with the dates rather
            # than leaving a year behind that cannot be built or deleted.
            return fail(f"Those dates do not make a calendar that can be "
                        f"built, so {label} has not been created:\n\n{exc}")
        except StoreError as exc:
            return fail(str(exc), 409)
        return RedirectResponse(f"/?year={label}", status_code=303)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    return app


def _page_png(build, width: int = 1100) -> bytes:
    """The first page of the built calendar, rasterised.

    Rendered at more than display width so the date numbers stay readable when
    the browser scales it down -- the whole point of the preview is checking
    small print.
    """
    import io

    import pypdfium2

    document = pypdfium2.PdfDocument(io.BytesIO(build.pdf_bytes()))
    try:
        page = document[0]
        image = page.render(scale=width / page.get_size()[0]).to_pil()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        document.close()


def _rows_from_form(form) -> list[csvio.Row]:
    """Rebuild the row list from the posted form.

    The form carries every row on every save, indexed by position, and rows the
    person deleted simply are not there. Rebuilding the whole list is what makes
    the CSV writer's job simple enough to trust -- there is no partial update to
    get wrong.

    The CSV has three date columns (date, start_date, end_date) and the form has
    two: From and To, with To left blank for a single day. Three boxes would
    make every ordinary one-day event a question about which box to use, and the
    answer would be wrong often enough to matter. The mapping is here, in one
    place, rather than being explained on the page.
    """
    indices = sorted({
        int(key.split("-", 1)[1].split("-", 1)[0])
        for key in form
        if key.startswith("row-") and key.split("-", 1)[1].split("-", 1)[0].isdigit()
    })
    rows = []
    for i in indices:
        def field(name: str) -> str:
            return (form.get(f"row-{i}-{name}") or "").strip()

        if field("deleted") == "1":
            continue
        start, end = field("from"), field("to")
        # A "range" of one day is a warning from the validator and means the
        # same thing as a single date, so treat it as one rather than making
        # somebody read the warning and fix it by hand.
        if end and end != start:
            row = csvio.Row(start_date=start, end_date=end)
        else:
            row = csvio.Row(date=start)
        row.type = field("type")
        row.label = field("label")
        row.notes = field("notes")

        # A row with nothing in it is someone who clicked Add and changed their
        # mind, not an event. Dropping it saves them a validation error about a
        # blank line they cannot see.
        if not any([row.date, row.start_date, row.label]):
            continue
        rows.append(row)
    return rows


def _store_from_env() -> Store:
    remote = os.environ.get("REPO_REMOTE", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    workdir = Path(os.environ.get("WORKDIR", "/data/repo"))

    if not remote:
        # No remote configured: work against this checkout. Useful for running
        # the editor locally against a clone you already have, and wrong in a
        # container, where only python/ and web/ are copied in and there is no
        # data/ to edit. Say which it is rather than failing later on a missing
        # file with no hint that a variable was never set.
        if not (REPO / "data" / "all_events.csv").exists():
            raise RuntimeError(
                f"REPO_REMOTE is not set and there is no calendar data at "
                f"{REPO / 'data'}. Set REPO_REMOTE to the repository's clone "
                f"URL (and GITHUB_TOKEN to a token that may push to it)."
            )
        # owns_checkout=False: this is the developer's own clone, not a
        # disposable one the editor may reset.
        return Store(REPO, owns_checkout=False)

    if token and remote.startswith("https://") and "@" not in remote:
        remote = remote.replace("https://", f"https://x-access-token:{token}@", 1)
    return Store.clone(remote, workdir)


app = None  # created by uvicorn's factory below


def factory() -> FastAPI:
    return create_app()
