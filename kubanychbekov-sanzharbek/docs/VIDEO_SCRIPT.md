# Demo video plan (about 5 minutes)

Requirements README-03..06: a public or unlisted YouTube video of the **real working system** (not mock-ups) that shows
a web request, the dispatcher's assignment, the technician's actions in Android, a backend update reaching the phone,
at least one conflict **or** offline scenario, the original feature (Smart Assign), a short test run and one
engineering decision. No real passwords, tokens or customer data on screen; the seeded password `Demo-2345!` is
demo-only and may be shown.

## Before recording (about 15 minutes)
1. Start the stack: `docker compose up -d --build`, then (both are safe to repeat)
   `docker compose run --rm backend python -m app.seed` and `docker compose run --rm backend python -m app.seed_extra`.
   Open http://localhost:3000 and choose **English** (the PDF requires a complete English UI).
2. Phone: install the APK (`adb install -r mobile/build/app/outputs/flutter-apk/app-debug.apk`, or open
   `Downloads\\FixFlow-debug.apk` on the phone). With the phone on USB and USB debugging on, run
   `adb reverse tcp:8000 tcp:8000` and use the server address `http://localhost:8000` in the app. Over Wi-Fi use
   `http://<computer IP>:8000` (re-check with `ipconfig`; school networks may isolate devices).
3. Accounts (password `Demo-2345!` for all, organization "AIT Facility"): customer `customer1.a@fixflow.test`,
   dispatcher `dispatcher.a@fixflow.test`, administrator `admin.a@fixflow.test`, technician in the app
   `tech2.a@fixflow.test` (Azamat, skills HVAC + plumbing). Sign the phone in as `tech2.a` before recording and
   switch the app language to English.
4. Browser: two windows or profiles (customer and dispatcher) so you do not have to sign out on camera.
5. Hide chat apps and notifications, set the browser zoom to 110-125 %, record at 1080p with your voice. Keep the
   timer visible. Do one dry run.
6. Ready terminal tabs: (a) `docker compose --profile test run --rm backend-tests`, (b) `cd web && bun run test:ci`,
   (c) `cd mobile && flutter test`. Run them once before so the images and caches are warm.

## Step by step
| # | Time | Where | What to do | What to say (one sentence) |
|---|---|---|---|---|
| 1 | 0:00-0:25 | Screen: `README.md` and `docs/ARCHITECTURE.md` | Show the title, the YouTube link at the top and the architecture picture. | "FixFlow is a field-service platform: FastAPI and PostgreSQL, a Next.js web app and a Flutter Android app that all use one database." |
| 2 | 0:25-1:10 | Web, **customer** | `New request`: title, description (20+ characters), category **HVAC**, a property, priority **High**, attach a photo, submit. Show it in the list as *Submitted*. | "The customer files a request; it is stored in PostgreSQL and visible only inside its own organization." |
| 3 | 1:10-2:10 | Web, **dispatcher** | Open the request, *Mark as triaged*. In **Smart Assign** show the ranked technicians and the reason text, pick Azamat, *Assign*. Open the schedule week view. | "Smart Assign ranks technicians by skills, availability and load and explains every choice. This is the original feature." |
| 4 | 2:10-2:35 | Web, **dispatcher** | Open a second request, try to book the same technician for the same time: show the **409 conflict** message. | "A PostgreSQL exclusion constraint rejects double booking, even when two dispatchers click at the same moment." |
| 5 | 2:35-3:35 | **Phone** | Pull to refresh: the new HIGH task appears with its SLA card. Open it, *Accept task*, *Start work*, *Add note*, *Add photo* from the gallery, then *Used materials* (optional, writes off one item). | "The task arrives from the real API and is also stored on the phone, so it can be read without a network." |
| 6 | 3:35-4:10 | **Phone** | Offline scenario: switch on airplane mode (or `docker compose stop backend`), add a note: it shows *Waiting to sync* in the queue. Switch the network back on: it disappears and the note shows once. | "Every action has a stable command id, so a retry after a lost connection never creates a duplicate." |
| 7 | 4:10-4:25 | **Phone** | *Complete work*: summary of 20+ characters, photo already attached, confirm. | "Completion needs a summary and at least one photo, checked on the server." |
| 8 | 4:25-4:45 | Web, **dispatcher** then **customer** | Refresh the request: status *Completed*, timeline with notes and the photo, final SLA. As the customer rate it 5 stars. | "The web shows what the technician did, and the SLA result is fixed at completion." |
| 9 | 4:45-5:15 | Terminal | Show the three test runs finishing green: backend **284 passed**, web **23 pass**, Flutter **38 passed**. | "Tests run against a real PostgreSQL." |
| 10 | 5:15-5:30 | Spoken, with `docs/PRODUCT_DECISIONS.md` on screen | Name one engineering decision. | "I changed request status with compare-and-set updates and idempotency keys in the database instead of locks in the application, so concurrent requests stay correct with several workers." |

If you need to stay under five minutes, cut step 7 into step 5 (complete right after the note) and shorten step 9 to the
summary line of each run.

## Optional extras (only if time allows, 10-15 seconds each)
- **Administrator:** dashboard with technician load and report filters, *Properties and equipment* with an asset's
  history, *Staff and roles*, the audit feed.
- **Estimate:** a request with an estimate blocks *Start* on the phone until the customer approves it.
- **Language:** switch the web or the phone to Russian to show the translations (the PDF only requires English).

## Do not show
Real e-mails or phone numbers, personal GitHub tokens or browser profiles with your avatar, the Windows notification
area, the `.env` file if it ever contains anything but the demo values, your own gallery photos (pick only a neutral
test image for the attachment).

## If something goes wrong on camera
- The phone shows *Offline*: the server address is wrong or the network changed; fix it in the sign-in or profile screen
  (the saved address is shown there) and pull to refresh.
- A task does not appear: pull to refresh; the dispatcher must have assigned **Azamat (tech2.a)**.
- *Assign* says conflict: pick another time or technician (the schedule view shows busy slots).
- Do not delete the Docker volumes to "start over": run the seed commands again instead (they never duplicate).

## After recording
Upload to YouTube as **Unlisted** (or Public). Wait until processing is finished, open the link in a private window to
confirm it plays without signing in, then put the URL on the first lines of `README.md` (replace the TODO line) and tell
the assistant so the final check and the submission can follow (Sunday 15 November after 16:00, Asia/Bishkek).
