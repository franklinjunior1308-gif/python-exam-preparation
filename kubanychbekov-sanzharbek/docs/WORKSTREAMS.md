# Parallel work: who owns what

Several Claude sessions work in this one checkout (branch `main`, no worktrees). To avoid overwriting each
other, each area has ONE owner. Nobody runs `git add -A`; everyone stages only their own paths.

| Area | Paths | Owner |
|---|---|---|
| Backend and API | `backend/**` (models, services, API, **all Alembic migrations**), `docs/API.md` | fork 1 |
| Web and UI | `web/**`, `backend/app/seed_extra.py` | fork 2 |
| Flutter and APK | `mobile/**`, `docs/VERIFICATION.md` | fork 1 (until a separate Flutter owner is named) |
| Shared docs | `docs/PROGRESS.md`, `README.md` | small edits only, re-read the file just before editing |

Rules
- **Migrations:** the chain is linear with one head (`alembic heads` must print one line). Only the backend owner
  creates a migration; others ask for the shape of the endpoint instead.
- **Needing a change in someone else's area:** send them the exact shape (path, JSON); do not edit their files.
- **Before integrating or committing:** `git status` (never stage another owner's uncommitted files), then the
  owner's tests: backend `docker compose --profile test run --rm backend-tests`; web `bun run lint && bun run
  typecheck && bun run test:ci && bun run build`; mobile `flutter analyze && flutter test`.
- **Never** push to the exam repository before it opens (Sunday 2026-11-15 16:00 Asia/Bishkek; pushes to the personal backup are fine), never reset
  the database or Docker volumes, never delete history.
