# AI usage

This project was built with **Claude Code** (Anthropic's Claude models) as a pair-programming assistant, working
in the terminal of the candidate's machine against the real stack (Docker, PostgreSQL, Flutter, Bun).

## What the assistant did
- Wrote most of the code from `FixFlow_Requirements_RU.pdf`: FastAPI backend, Alembic migrations, Next.js web app,
  Flutter Android app, tests, seeds, scripts and the documentation in this folder.
- Ran the tools itself (tests in Docker, linters, type checkers, builds, the APK build) and fixed what failed.
- Kept `docs/PROGRESS.md` current so the work could continue after context resets.

## What the candidate did
- Chose the scope and priorities (real Flutter - FastAPI - PostgreSQL integration first), set the constraints
  (no destructive database resets, no early submission), reviewed results and ran the steps the assistant could not
  (installing Docker/Android tooling, accepting licenses, restarting the PC).
- Owns the submission: understands the architecture (`docs/ARCHITECTURE.md`) and the original feature
  (Smart Assign, `docs/PRODUCT_DECISIONS.md`) and can explain and change them.

## How the output was checked
Nothing is claimed as working unless it was run: backend integration tests on PostgreSQL, `scripts/smoke.py`
(real lifecycle + 409 conflict + tenant isolation), web lint/type/unit tests/build, Flutter analyze/tests and a live
integration run. Results and honest gaps: `docs/VERIFICATION.md`, `docs/KNOWN_LIMITATIONS.md`.

## Prompts and review
The work was driven by short Russian/English instructions per module (scheduling, work reports, offline queue,
estimates, inventory, SLA, maintenance, UI). AI output was reviewed by reading diffs, running the test suites and
exercising the screens in a browser; defects found that way (e.g. a vacuous test, an idempotent-replay bug,
a wrong error classification for missing photos) were fixed and covered by tests.
