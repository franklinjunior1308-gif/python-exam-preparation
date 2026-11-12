# Submission checklist: Sunday 2026-11-15 (Asia/Bishkek, UTC+06:00)

Hard times: shared repository opens **16:00**, deadline **18:00** (HEAD of the PR at 18:00 counts; later commits and a
late upload do not count). Nothing is pushed anywhere before 16:00. Do not merge the PR. Folder name and branch:
`kubanychbekov-sanzharbek` and `submission/kubanychbekov-sanzharbek`.

## A. Before 16:00 (everything local)
- [ ] `git status` is clean in the local repository; last verification run recorded in `docs/VERIFICATION.md`.
- [ ] Final full check passed: `BACKEND_TESTS_IN_DOCKER=1 ./scripts/verify-all.sh` (see `VERIFICATION.md`).
- [ ] Clean-start rehearsal passed (`docker compose -p rehearsal up -d --build`, seed, `scripts/smoke.sh`).
- [ ] Video recorded following `docs/VIDEO_SCRIPT.md`, uploaded to YouTube (Unlisted or Public), **processing finished**,
      opens in a private window without signing in.
- [ ] YouTube URL pasted in the first lines of `README.md` (replace the `TODO` line); committed locally.
- [ ] `README.md`: statuses match `docs/KNOWN_LIMITATIONS.md`; no claim of anything unfinished.
- [ ] No secrets or personal data in the tree: `.env` absent (only `.env.example`), no tokens, no real customer data.
- [ ] The APK is **not** committed (it is a build output); sources to rebuild it are (`mobile/android`, `pubspec.lock`).
- [ ] Prepared the clean copy folder (step B2) once as a dry run to check its size (< 50 MB expected).

## B. 16:00-16:20 get access and copy
1. Accept the GitHub invitation to the shared repository (e-mail or the repository page). Clone it to a **new** place:
   ```powershell
   cd C:\work
   git clone https://github.com/<ORG>/<SHARED-REPO>.git shared
   cd shared
   git switch -c submission/kubanychbekov-sanzharbek
   ```
2. Copy the project (no `.git`, no build output, no caches, no secrets):
   ```powershell
   $src = "C:\Users\ASUS ROG STRIX\fixflow\kubanychbekov-sanzharbek"
   robocopy $src .\kubanychbekov-sanzharbek /E /XD .git node_modules .next build .dart_tool .gradle .kotlin .venv __pycache__ .pytest_cache .ruff_cache uploads .idea /XF .env *.apk local.properties
   ```
3. Verify the copy:
   ```powershell
   Get-ChildItem -Recurse -Force kubanychbekov-sanzharbek -Directory -Filter .git   # must print nothing
   Get-ChildItem -Recurse kubanychbekov-sanzharbek -File | Where-Object Length -gt 5MB   # review each, expect none
   Test-Path kubanychbekov-sanzharbek\.env                                           # must be False
   git status --short | Select-String -NotMatch "kubanychbekov-sanzharbek/"           # must print nothing (root untouched)
   ```
4. Required layout exists inside the folder: `README.md`, `compose.yaml`, `.env.example`, `backend/{pyproject.toml,uv.lock,alembic,app,tests}`,
   `web/{package.json,bun.lock}`, `mobile/{pubspec.yaml,pubspec.lock,lib,test,android}`, `scripts/{verify-all.sh,smoke.sh}`,
   `docs/{ARCHITECTURE,API,PRODUCT_DECISIONS,KNOWN_LIMITATIONS,VERIFICATION,AI_USAGE}.md`.
5. Do **not** edit the organizers' root files: `README.md`, `docs/`, `.github/` in the repository root.

## C. 16:20-16:45 verify the copy as a reviewer would
- [ ] `cd kubanychbekov-sanzharbek; cp .env.example .env; docker compose up -d --build`
- [ ] `docker compose run --rm backend python -m app.seed` (and `app.seed_extra`), open http://localhost:3000, sign in
      as each role (customer, dispatcher, admin; technician on the phone).
- [ ] `./scripts/smoke.sh` prints `smoke: all checks passed`.
- [ ] Delete the `.env` you created (it is ignored by git, but do not leave it in the tree you commit).

## D. 16:45-17:15 commit and push
```powershell
git add kubanychbekov-sanzharbek
git status                                   # only paths under kubanychbekov-sanzharbek/
git commit -m "FixFlow: add Kubanychbekov Sanzharbek submission"
git push -u origin submission/kubanychbekov-sanzharbek
```
Meaningful history is welcome: if time allows, commit in 3-5 logical commits (backend, web, mobile, docs/scripts)
instead of one.

## E. 17:15-17:30 open the pull request (not a draft)
- Base: `main`; compare: `submission/kubanychbekov-sanzharbek`; **not a draft**.
- Title exactly: `FixFlow: Kubanychbekov Sanzharbek`
- Description must contain: link to the personal README, the YouTube link, how to run and verify
  (`docker compose up -d --build`, seed, `./scripts/smoke.sh`, `./scripts/verify-all.sh`), and an honest list of what is
  done and what is not (copy from `docs/KNOWN_LIMITATIONS.md`).
- Do not merge, do not close, do not force-push after 17:45 unless something is broken.

## F. 17:30-18:00 final checks
- [ ] PR shows as open and not draft, base `main`, title correct, one top-level folder changed.
- [ ] The video link in the PR and in `README.md` works while signed out.
- [ ] CI of the organizers (if any) has run; if it fails for a reason in your folder, fix and push **before 18:00**.
- [ ] Take a screenshot of the PR page for your own records. Stop pushing at 17:55.

## G. If something goes wrong
- No access at 16:00: wait, refresh, ask the organizers; keep the local repository as the source of truth.
- Push rejected: `git pull --rebase origin main` is not needed for a new branch; check that you pushed the branch you
  created and that the remote is the shared repository (`git remote -v`).
- Video still processing at 17:30: use the link anyway (YouTube accepts links during processing) and re-check later.
