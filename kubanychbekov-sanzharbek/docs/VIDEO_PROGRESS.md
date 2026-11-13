# VIDEO_PROGRESS (read this first after a context reset) - last update 2026-11-13 ~23:20

## 0. Goal and rules (latest author decisions win)
A ~5 minute MP4, 1920x1080, 16:9, NO voice and NO music, **fully in Russian**: web UI in RU, Android UI in RU, Russian request, Russian captions
(«Создание заявки», «Назначение техника», «Работа в Android», «Офлайн-режим», «Завершение работы», «Результаты тестирования») plus intro/architecture/end cards.
ONE request for the whole scenario. Everything is recorded from the real running system; only waits are sped up. I (Claude) perform the demo actions myself
(browser through the DevTools protocol, phone through adb); the author records nothing and will add the Russian voice later.
Never reset the database, never delete Docker volumes or any recorded file, do not change source code without a critical need, no YouTube upload,
no official GitHub PR before Sunday 2026-11-15 16:00 (Asia/Bishkek). Use demo accounts only; never show passwords (typed as dots), tokens, the author's personal photos or phone status-bar icons.

## 1. Demo request (already created, do NOT create another)
- **#95 "Кондиционер не охлаждает"**, HVAC, priority Высокий, property Building A, organization AIT Facility, created by `customer1.a@fixflow.test`.
- Current state in PostgreSQL: **SCHEDULED**, assigned to **Erlan Moldobekov (tech1.a@fixflow.test)**, visit Monday 2026-11-16 09:00 Bishkek. Customer photo `photo_problem.jpg` attached.
- Next real transitions still to be done on THIS request: ACCEPTED -> IN_PROGRESS (phone), notes + technician photo + offline note (phone), COMPLETED (phone), CLOSED + rating (web, customer).
- Request **#94** (English take, English UI) was CANCELED as an unused test (via API cleanup). #91 (earlier phone check) is COMPLETED and rated. Leave them.
- State file: `C:\dev\demo\state.json` ({"requestId":95,...}). Accounts (password `Demo-2345!`, demo-only): customer1.a, dispatcher.a (two organizations: choose "AIT Facility"), tech1.a (phone). Sessions last 60 minutes.

## 2. Recorded scenes and where the files are (all under `C:\dev\demo\`, nothing has been deleted)
| Scene | Folder | Content |
|---|---|---|
| Probe (test only, English login page) | `raw\probe\` (+ `probe.mp4`) | not used in the video |
| Stage 1 English take (unused, request #94) | `raw\s1_customer\` | not used |
| **Stage 1 customer, RU (USE)** | `raw\s1_customer_ru\` | 1134 JPEG frames `000000.jpg...`, `frames.json` (true paint timestamps + marks: login, new-request, submit, created, photo, done), `list.txt` (ffmpeg concat list) |
| **Stage 2 dispatcher, RU (USE)** | `raw\s2_dispatcher\` | 442 frames, ~30 s, marks: requests, open, triage, smart, assign, assigned, schedule, done |
Frames are not MP4 yet. Encode one scene with
`ffmpeg -y -f concat -safe 0 -i raw\<scene>\list.txt -vf "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p" -c:v libx264 -crf 18 -preset veryfast -an out.mp4`.
Not recorded yet: phone stages (login, task + SLA, accept, start, note, photo, offline, complete), web closing + rating, tests/terminal, title/architecture/end cards.

## 3. Installed programs (all with the author's permission) and paths
- FFmpeg 9.0.2: `C:\Users\ASUS ROG STRIX\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe` (also `ffprobe.exe`; filters drawtext, subtitles, xfade, zoompan, boxblur available). Fonts with Cyrillic: `C:/Windows/Fonts/segoeui.ttf`.
- Bun 1.4.4: `C:\Users\ASUS ROG STRIX\AppData\Local\Microsoft\WinGet\Packages\Oven-sh.Bun_Microsoft.Winget.Source_8wekyb3d8bbwe\bun-windows-x64` (add to PATH in bash).
- scrcpy 5.0.1: `...\WinGet\Packages\Genymobile.scrcpy_Microsoft.Winget.Source_8wekyb3d8bbwe\scrcpy-win64-v5.0.1\scrcpy.exe` (set `$env:ADB="C:\dev\android\platform-tools\adb.exe"`); OBS 33 (`C:\Program Files\obs-studio`, not needed for the final video); make 4.4.1; Chrome and Edge (pre-installed).
- Phone: Xiaomi POCO 25078PC3EG, Android 15, 720x1600, USB debugging on, `adb reverse tcp:8000 tcp:8000` (re-run it after any reconnect), app server URL `http://localhost:8000`. The app is currently **signed out**.
- Docker stack (project `kubanychbekov-sanzharbek`: db, backend, web) running and healthy; volumes intact. Rehearsal volumes `rehearsal_*`, `cleanclone_*` and folders `C:\dev\cleanclone-*` are harmless leftovers.

## 4. Automation scripts (ready) in `C:\dev\demo\`
- `lib\cdp.ts`: Chrome DevTools driver (real mouse/keyboard events, visible pointer + click ripple, screencast frames, `type`, `choose` for selects, `click("text=...")`, `clickRow(row, button)`, `pretendClick`, `upload`, `scrollTo`, `waitText`, `mark`, `frameVideoList`).
- `s1_ru.ts` (stage 1, done), `s2_dispatcher.ts` (stage 2, done), `prep_ru.ts` (switches the customer profile to RU and signs out), `probe.ts`, `s1_customer.ts` (English, unused).
- Chrome profiles: `profiles\customer` (port 9341, RU, currently signed out) and `profiles\dispatcher` (port 9342, RU, signed in as dispatcher); both Chrome windows are still open (do NOT kill other Chrome processes: the author's own browser is running).
- Helpers outside the repo: `C:\dev\tmp\*.py` (photo search/download, cancel94, slots, record notes). Assets: `assets\photo_problem.jpg`, `assets\photo_after.jpg` (CC0, Wikimedia Commons, author Alf van Beem, downloaded with permission), `assets\demo_photo.png` (grey test image, unused).

## 5. Known problems / traps (not all fixed)
1. A new Chrome profile started with `--lang=ru-RU` does not open its debug port: use the default language and the in-app RU button (cookie per profile).
2. Scripts must be created with the Write tool; bash heredocs lose backslashes in Windows paths. Every script must end with `process.exit(0)` or Bun never exits.
3. `adb shell input text` cannot type Cyrillic. Plan: switch Gboard to the Russian layout with the globe key and tap the letters (key bounds from `uiautomator dump`). If Russian is not enabled in Gboard, ask the author to enable it (Settings > Languages > Gboard); do not install an IME or change phone settings without asking. **Not tested yet.**
4. The photo picker on the phone shows the author's PERSONAL photos: push `photo_after.jpg` to `/sdcard/Pictures/` with `MSYS_NO_PATHCONV=1`, record it, and in the edit **blur the whole picker region** for those seconds with the caption «личные фото скрыты». Crop the phone status bar (top ~80 px).
5. Only one scrcpy client per device: close the author's window `FixFlow-Phone` before recording with `scrcpy -N --no-audio --record=C:\dev\demo\raw\phone.mp4 --video-bit-rate 4M` (log wall-clock timestamps of every action to align the cuts).
6. The USB cable/adb connection dropped several times (statuses unauthorized/offline): if `adb devices` is empty, ask the author to re-plug and accept the debugging prompt, then `adb reverse tcp:8000 tcp:8000`.
7. The stage 2 clip has not been viewed frame by frame yet: extract a few frames with ffmpeg (`-ss`) and check it before using it; re-record the scene with a NEW request only if it is bad (never edit the database).
8. Nothing is pushed: the docs commit `26c0d4c` is local; `git push personal main:fixflow` updates the backup branch (never push to the shared lab repository before the allowed time).

## 6. Next actions (in order)
1. Re-run `adb devices`, `adb reverse`, stop the author's scrcpy window, start the headless recording. 2. Phone: sign in as tech1.a (server `http://localhost:8000`), open #95 (pull to refresh), show the SLA card, «Принять задание», «Начать выполнение», note (Russian via Gboard), «Добавить фото» from the gallery (blur later).
3. Offline: `docker compose stop backend` -> add a note -> «Ожидает синхронизации» -> `docker compose start backend` (data kept) -> check exactly one copy in PostgreSQL (`work_notes`).
4. Complete on the phone (summary >= 20 characters, photo attached). 5. Web (profile `customer`, log in again): open #95 -> «Закрыть заявку», 5 stars + «Отправить отзыв», show the history; script it like `s1_ru.ts`.
6. Tests scene: record a terminal region with ffmpeg `gdigrab` while running `bun test` (web), `flutter test` (mobile) and the backend tests (`docker compose --profile test run --rm backend-tests`, sped up), then show the "make up / clean clone" table from `docs/VERIFICATION.md`.
7. Edit: normalise every clip to 1920x1080 30 fps yuv420p; per-scene trims from the `frames.json` marks / phone log; `setpts` for waits (label "x4"); `drawtext` captions (Segoe UI, lower third, fade in/out); `xfade` 0.4 s between scenes; intro card (title + stack bullets), architecture card, final card «FixFlow — от заявки до решения»;
   encode `libx264 -crf 18 -an -movflags +faststart` to `C:\Users\ASUS ROG STRIX\Videos\FixFlow-demo\FixFlow_demo_ru_no_voice.mp4`.
8. Deliver: MP4 path, Russian narration text by scene with timestamps, the scene list with exact times, and an honest statement of what is real, what was sped up, what was blurred/cropped.

## 7. How to resume editing without losing anything
All raw frames and logs stay in `C:\dev\demo\raw\` (do not delete). To continue: read this file, re-check the environment (Docker stack, `adb devices`, `curl localhost:3000/login`), then do step 1 of section 6. The request #95 already exists and is SCHEDULED to Erlan,
so DO NOT run `s1_ru.ts` again (it would create another request); continue with the phone. If a scene must be re-recorded, record it as a new clip next to the old one and keep both.

## UPDATE 2026-11-13 ~23:20 - take 2 (new request)
- Phone take 1 on #95 went through the whole flow (accept, start, RU note via Gboard coordinate taps, photo, offline note synced exactly once, COMPLETED) but `raw\phone.mp4` is unusable
  (scrcpy was killed -> "moov atom not found"; file kept). #95 is now COMPLETED, so the whole chain is redone on a NEW request (#96+), with the phone recorded to **MKV** and scrcpy stopped gracefully.
- Take-1 files stay in `raw\` (s1_customer_ru, s2_dispatcher, phone.mp4, phone_log.json). Take-2 files use the `v2_` prefix. Phone helpers: `C:\dev\demo\ph.py`, `kbru.py` (Russian Gboard key coordinates for 720x1600, rows y=1100/1208/1316, space 395,1425).
- Lesson: wait for the text field to be focused before typing; to clear a field use ctrl+a then DEL.

## UPDATE 2026-11-13 ~23:55 - take 2 recorded (request #96 is CLOSED, rated 5)
- Raw take 2 in `C:\dev\demo\raw\`: `v2_s1` (customer creates #96), `v2_s2` (dispatcher + Smart Assign -> Erlan), `v2_phone.mkv` + `phone_log.json` (labels after `v2_phone_start`; video time ~ log time + 4 s), `v2_s3` (customer closes, rating form not yet accepted), `v2_s3b` (customer rates 5 stars + comment, history). Use these; the take-1 files are obsolete.
- Fix learned: Chrome needs `Emulation.setFocusEmulationEnabled` + `Page.bringToFront` (now in `lib/cdp.ts` attach), otherwise mouse events hang when the window is not focused. Star rating: `label.rating-star:nth-of-type(5)`.
- Remaining: tests terminal clip (`C:\dev\demo\run_tests.bat`, window title FixFlowTests, ffmpeg gdigrab), cards, edit, encode, report.
