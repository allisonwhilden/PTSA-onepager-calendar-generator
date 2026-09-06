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

from . import changes as changes_mod
from . import csvio
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
    #: (sha, Build | None, error | None) for the last commit built. One entry:
    #: everyone is looking at the same draft.
    app.state.build_cache = None
    # Cookies go out Secure unless told otherwise, so a misconfigured proxy
    # cannot quietly downgrade the session to plain HTTP. Tests and local
    # development set it to false explicitly.
    app.state.secure_cookies = _bool_env("SECURE_COOKIES", True)

    templates = Jinja2Templates(directory=str(HERE / "templates"))
    templates.env.globals["now"] = lambda: dt.datetime.now()

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

    def build_current(store: Store):
        """The draft as `build.py` would build it, or the reason it cannot.

        Returns (Build, error, sha). A calendar too broken to render still has
        to be editable -- that is the state someone needs the editor for most --
        so a failure here is something to show at the top of the page, never
        something to refuse to load.

        Cached against the commit it was built from. Laying the page out costs
        about 0.75s and a single view of the dates page needs it twice: once
        for publish_problems() and again when the browser fetches the preview
        image, which used to arrive as a separate request with a fresh Build
        and an empty document cache.
        """
        sha = store.head()
        cached = app.state.build_cache
        if cached and cached[0] == sha:
            return cached[1], cached[2], sha
        try:
            built, error = pipeline.build(store.csv_path, store.years_dir), None
        except pipeline.Blocked as exc:
            built, error = None, str(exc)
        app.state.build_cache = (sha, built, error)
        return built, error, sha

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, sess: dict = Depends(session)):
        store: Store = app.state.store
        store.sync()
        build, error, _ = build_current(store)
        return render(
            request, "index.html",
            rows=sorted(store.rows(), key=csvio.Row.sort_key),
            types=event_types.choices(),
            build=build, error=error,
            base=store.head(),
            pending=store.has_unpublished_changes(),
            changes=_pending_changes(store),
            name=sess.get("name", ""),
        )

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

        response = RedirectResponse("/", status_code=303)
        if author:
            response.set_cookie(
                COOKIE_NAME, app.state.auth.issue(author),
                max_age=SESSION_MAX_AGE, httponly=True,
                secure=app.state.secure_cookies, samesite="lax",
            )
        return response

    @app.get("/preview.png")
    def preview_image(sess: dict = Depends(session)):
        """The preview as a picture.

        The obvious way to show a PDF in a page is an iframe, and on a desktop
        browser it works. On phones it usually shows nothing at all, and in
        some embedded viewers it shows a black rectangle -- which is what it
        did here. A person checking whether they typed the date right should
        not have to know which browser renders PDFs inline. An image works
        everywhere; the PDF is still one click away for anyone who wants to
        print or send it.
        """
        build, error, _ = build_current(app.state.store)
        if build is None:
            raise HTTPException(status_code=422, detail=error)
        return Response(_page_png(build), media_type="image/png",
                        headers={"Cache-Control": "no-store"})

    @app.get("/preview.pdf")
    def preview(sess: dict = Depends(session)):
        build, error, _ = build_current(app.state.store)
        if build is None:
            raise HTTPException(status_code=422, detail=error)
        return Response(
            build.pdf_bytes(), media_type="application/pdf",
            headers={"Content-Disposition":
                     f'inline; filename="DRAFT-{build.filename}"'},
        )

    @app.get("/publish", response_class=HTMLResponse)
    def publish_form(request: Request, sess: dict = Depends(session)):
        store: Store = app.state.store
        store.sync()
        build, error, sha = build_current(store)
        blockers = list(filter(None, [error]))
        if build is not None:
            blockers += build.publish_problems()
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
        blockers = list(filter(None, [error]))
        if build is not None:
            blockers += build.publish_problems()
        if blockers:
            # The last line of defence, not the first: the button is already
            # disabled. Someone with a stale page open must still not be able
            # to publish a calendar that does not fit on a page.
            return render(request, "publish.html", blockers=blockers,
                          changes=_pending_changes(store), build=build,
                          pending=store.has_unpublished_changes(),
                          status_code=422)
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
