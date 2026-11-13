# AI usage

Two AI assistants were used. Personal prompts and full chat logs are not included (DOC-06); this file describes what
each assistant did and how its output was checked.

## Claude (Anthropic) - main development assistant
Claude Code (Claude models) worked in the terminal of the candidate's machine against the real stack (Docker,
PostgreSQL, Flutter, Bun). It was used widely for:
- **Backend:** FastAPI application, SQLAlchemy models, Alembic migrations, services (requests lifecycle, scheduling and
  Smart Assign, work reports and photos, estimates, inventory, SLA, maintenance plans, feedback, audit feed, staff and
  roles, categories, equipment and its history, live updates over SSE, SLA report), login lockout and request IDs.
- **Web:** the Next.js application (screens per role, the backend-for-frontend proxy, EN/RU dictionary).
- **Flutter Android app:** offline queue, sync, conflicts, materials write-off, EN/RU texts.
- **Tests:** backend integration tests on PostgreSQL (including concurrency and tenant isolation), web unit tests,
  Flutter unit, widget and live-API tests.
- **Documentation and scripts:** everything in `docs/`, `README.md`, `scripts/` and the seed commands.
- It ran the tools itself (tests in Docker, linters, type checkers, builds, the APK build) and fixed what failed.
- It kept `docs/PROGRESS.md` current so that work could continue after context resets. Several Claude sessions
  worked in parallel on separate paths (backend and mobile, web); ownership rules are in `docs/WORKSTREAMS.md`.

## ChatGPT (OpenAI) - references, analysis and consultation
ChatGPT was used outside the repository for:
- **Visual references:** generating the design mockups (landing page and screens) that were used as a visual guide only.
- **Requirements analysis:** reading and structuring `FixFlow_Requirements_RU.pdf`.
- **Planning:** splitting the work into stages and ordering priorities.
- **Testing consultations:** discussing what to test (offline behaviour, concurrency, idempotency).
It did not write code that was committed without going through the checks below.

## What the candidate did
- Chose the scope and priorities (real Flutter - FastAPI - PostgreSQL integration first) and set the constraints (no
  destructive database resets, no early submission, no changes to system settings without permission).
- Ran the steps the assistant could not: installing Docker and the Android tooling, accepting licenses, restarting the
  PC, installing the APK on a phone, recording the video.
- Owns the submission and is responsible for being able to explain and change the architecture
  (`docs/ARCHITECTURE.md`) and the original feature, Smart Assign (`docs/PRODUCT_DECISIONS.md`).

## How AI output was checked
- **Automated:** backend `ruff`, `ruff format`, `ty` and `pytest` on PostgreSQL 17 in Docker (integration tests for the
  lifecycle, scheduling conflicts, stock races, idempotent commands, SLA escalation, roles and tenant isolation);
  web lint, type check, unit tests and production build; Flutter `format`, `analyze`, unit/widget tests, and a live test
  against the real API (`mobile/test/live`); the Android debug APK build.
- **Scripts:** `scripts/smoke.sh` and `scripts/e2e_scenario.py` run the main scenario through the real HTTP API as each role.
- **Reading and running:** diffs were read, screens were opened in a browser, and the app was started on a physical phone.
- **Defects found this way** and fixed with tests: a vacuous test, an idempotent-replay bug, a wrong error class for a
  missing photo, a header overflow on narrow phones, English-only notification titles in the Russian UI, a deadlock when
  two test runs shared one database.
- **Not claimed:** nothing is marked as passing unless it was run. The final status of each requirement, including
  what is NOT VERIFIED (for example anything that needs the candidate's phone), is in `docs/VERIFICATION.md` and
  `docs/KNOWN_LIMITATIONS.md`.
