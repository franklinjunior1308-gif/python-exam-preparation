# Demo video script (about 5 minutes)

Requirement README-03..06: public or unlisted YouTube video, real working system (not mock-ups), shows a web request,
dispatcher assignment, technician actions in Android, a backend update reaching the phone, one conflict **or**
offline scenario, the original feature (Smart Assign), a test run and one engineering decision. No real passwords,
tokens or customer data. The seeded password `Demo-2345!` is demo-only and may be on screen.

## Before recording (15 min)
1. `docker compose up -d --build` then `docker compose run --rm backend python -m app.seed` and
   `docker compose run --rm backend python -m app.seed_extra`. Open http://localhost:3000 (EN language).
2. Android emulator (or phone on the same Wi-Fi) with `mobile/build/app/outputs/flutter-apk/app-debug.apk` installed
   (`adb install -r app-debug.apk`). Server address at sign-in: `http://10.0.2.2:8000` (emulator) or
   `http://<computer IP>:8000` (phone).
3. Two browser windows: customer `customer1.a@fixflow.test`, dispatcher `dispatcher.a@fixflow.test`
   (organization "AIT Facility"). Technician on the phone: `tech2.a@fixflow.test`. All passwords: `Demo-2345!`.
4. Close chat apps and notification popups. Increase the font to 125 %. Screen recorder at 1080p with voice.
5. Dry-run once; keep the timer visible.

## Timeline
| Time | What to show | What to say (one sentence) |
|---|---|---|
| 0:00-0:20 | Title, `README`, one architecture picture (`docs/ARCHITECTURE.md`) | "FixFlow: FastAPI + PostgreSQL, Next.js web, Flutter Android; all three use one database." |
| 0:20-1:10 | Customer creates a request with a photo (`/app/requests/new`) | "The customer files a request; it is stored and visible only inside its organization." |
| 1:10-2:10 | Dispatcher: triage, **Smart Assign** panel, "Best match", schedule week view | "Smart Assign ranks technicians by skills, availability and load and explains why." (original feature, WEB-09) |
| 2:10-2:40 | Dispatcher tries to book the same technician and slot again: **409 conflict** message | "The database exclusion constraint rejects double booking even under concurrent requests." |
| 2:40-3:40 | Phone: sign in as technician, task appears, accept, start, add a note + photo, complete | "The task comes from the real API and is stored locally." |
| 3:40-4:10 | Airplane mode on the phone: add a note, see it in the offline queue; turn network on: it syncs once | "Each action has a stable command id, so a retry never duplicates it." (offline scenario) |
| 4:10-4:30 | Web refreshes: status COMPLETED, history, SLA badge, estimate state | "The web shows what the technician did." |
| 4:30-5:00 | Terminal: `docker compose --profile test run --rm backend-tests` result (245 passed), `bun run test:ci`, `flutter test` | "Tests run on real PostgreSQL. One decision: compare-and-set status changes + idempotency keys instead of locks in the app." |

## Do not show
Real e-mails or phone numbers, `.env` with real secrets (the file here has demo values only), your personal GitHub
tokens, browser profile avatars.

## After recording
Upload to YouTube as **Unlisted** (or Public), wait until processing finishes, open the link in a private window
to confirm it plays without a sign-in, then paste the URL at the top of `README.md` (replace the TODO line).
