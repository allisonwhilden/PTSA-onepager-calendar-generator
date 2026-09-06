# The calendar editor.
#
# Not the calendar itself: the PDF families see is built by
# .github/workflows/build-and-deploy.yml and served from gh-pages, and that is
# deliberate. If this container is down, or its host has gone out of business,
# the calendar on the school website is unaffected and the dates are still a
# CSV in the repo. This image only has to be up when somebody wants to change
# a date.
#
#   docker build -t ptsa-calendar-editor .
#   docker run -p 8000:8000 \
#     -e REPO_REMOTE=https://github.com/<owner>/<repo>.git \
#     -e GITHUB_TOKEN=<a token that may push to the repo> \
#     -e EDITOR_PASSWORD_HASH="$(python -c 'from web.auth import hash_password; print(hash_password("..."))')" \
#     ptsa-calendar-editor

FROM python:3.11-slim

# WeasyPrint draws the page with pango and cairo, so they have to be here --
# the same libraries the deploy workflow installs. git is not incidental
# either: it is the database.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies before source, so editing a template does not reinstall them.
# Copied one per line: `COPY a/req.txt b/req.txt ./dir/` flattens both to the
# same name and silently keeps only the second.
COPY python/requirements.txt ./deps/renderer.txt
COPY web/requirements.txt ./deps/editor.txt
RUN pip install --no-cache-dir -r deps/renderer.txt -r deps/editor.txt

COPY python/ ./python/
COPY web/ ./web/

# The editor imports calendar_gen rather than reimplementing any of it.
ENV PYTHONPATH=/app:/app/python \
    PYTHONUNBUFFERED=1 \
    WORKDIR=/data/repo

# The clone lives here. Nothing in it is precious -- every save is pushed as it
# happens -- so this can be ephemeral storage and a redeploy re-clones.
RUN mkdir -p /data/repo

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status == 200 else 1)"

# One worker on purpose. The store serialises writes with an in-process lock,
# which is only a lock if there is one process; two workers sharing one clone
# would interleave commits. This is a form a handful of people use a few times
# a year -- one worker is not the bottleneck.
CMD ["uvicorn", "web.app:factory", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
