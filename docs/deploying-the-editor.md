# Putting the editor online

Once, by one person. After that the PTSA edits dates in a browser and nobody
touches this again.

The editor is only the editor. The calendar families see is built by GitHub
Actions and served from gh-pages, and that does not change here — so if you
never finish this page, or the host you pick shuts down in two years, the
calendar keeps working and the dates are still editable on GitHub.

## 1. A token the editor can push with

The editor saves by pushing to this repository, so it needs a token that may.

Use a **fine-grained personal access token** limited to this one repository,
with **Contents: Read and write**. Nothing else. Set an expiry you will
actually notice — a year is reasonable; put a reminder in the PTSA calendar,
which is a pleasing sort of recursion.

If the token expires the editor stops being able to save, and says so. The
published calendar is unaffected.

## 2. A password for the people who edit

One shared password, handed over with the rest of the role. Store its hash, not
the password:

```bash
python -c 'import sys; sys.path.insert(0, "."); from web.auth import hash_password; \
           print(hash_password("the password you chose"))'
```

Keep the password itself in whatever the PTSA already uses to pass along logins.
Changing it later is one environment variable, and it signs everybody out.

## 3. Somewhere to run it

Any host that runs a container. [Fly.io](https://fly.io) is the suggestion:
cheapest always-on option, and it does not sleep.

```bash
fly launch --no-deploy            # answers: no database, no redis

fly secrets set \
  EDITOR_PASSWORD_HASH='<the hash from step 2>' \
  GITHUB_TOKEN='<the token from step 1>' \
  REPO_REMOTE='https://github.com/<owner>/<repo>.git' \
  PUBLISHED_PDF_URL='https://<owner>.github.io/<repo>/calendar.pdf'

fly deploy
```

On a free tier the machine sleeps and the first page load takes ten to thirty
seconds. For something used a few times a year that may be fine; a few dollars
a month keeps it warm.

**One process.** The store serialises writes with an in-process lock, which is
only a lock if there is one process. Two workers sharing one clone would
interleave commits. This is a form a handful of people use a few times a year —
one process is not the bottleneck.

## 4. Point the school website at the PDF, once

```
https://<owner>.github.io/<repo>/calendar.pdf
```

That link always means *the current school year*, and it keeps meaning that on
its own: a scheduled build rolls it over on 1 August. Link it once and never
touch the school site again.

Next year's calendar gets its own permanent link as soon as it is published —
`calendar-2027-28.pdf` — so it can be shared for review in the spring while
`calendar.pdf` still shows the year everyone is actually in.

## What happens when

| | |
|---|---|
| Someone saves | Committed and pushed to the `draft` branch. Not published. |
| Someone publishes | `draft` is pushed to `main`; the workflow builds and uploads the PDF. About a minute. |
| Someone restores an old version | It becomes a draft. Still has to be published. |
| 1 August | The scheduled build rolls `calendar.pdf` to the new school year. |
| No config for the new school year | The build publishes nothing and says so in the Actions job summary, rather than serving an ended calendar as the current one. |
| The editor is down | The published calendar is unaffected. Dates can be edited on GitHub directly. |
| The token expires | Saving fails with a clear message. The published calendar is unaffected. |

## If something looks wrong

Everything is versioned and nothing is destructive. **History → Restore** puts
any previous set of dates back as a draft; you review it and publish it like
any other change. What was restored over stays in the history.
