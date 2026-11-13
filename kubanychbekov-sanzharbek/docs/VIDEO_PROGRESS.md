# VIDEO_PROGRESS (read this first if the context was reset)

Goal: a ~5 minute MP4 (1920x1080, 16:9, no voice, English captions) of the REAL FixFlow flow on ONE request:
Customer (web) -> Dispatcher + Smart Assign (web) -> Technician (Android: accept, start, note, photo) -> Offline
note + sync -> Complete (Android) -> Customer closes + rates (web) -> tests + architecture. The author adds the
Russian voice-over later. Rules: demo accounts only, never reset the database or delete Docker volumes, do not change
source code without a critical need, do not upload to YouTube, no official GitHub PR before Sunday 2026-11-15 16:00.
Do not fake screens: everything is recorded from the running system; only waits are sped up.

## Tools (all installed with the author's permission)
- FFmpeg 9.0.2 (winget `Gyan.FFmpeg`): `C:\Users\ASUS ROG STRIX\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe` (has drawtext, subtitles, xfade, zoompan).
- scrcpy 5.0.1 (phone; `--record=file.mp4 --no-playback --no-audio` for clips), OBS 33 (not used for the final video), adb in `C:\dev\android\platform-tools`, make 4.4.1.
- Bun 1.4.4 drives Chrome over the DevTools protocol: `C:\dev\demo\lib\cdp.ts` (real mouse/keyboard events, visible pointer + click ripple,
  frames from `Page.startScreencast`, timestamps in `frames.json`, `frameVideoList()` writes an ffmpeg concat list with the true frame durations).
  Chrome starts with a clean profile under `C:\dev\demo\profiles\<name>` (customer port 9341, dispatcher port 9342). Do NOT kill other Chrome processes (the author's browser).
- Probe done: a 8 s clip of the real login page was recorded and encoded to 1920x1080 30 fps MP4 (quality good, pointer visible).
- Workspace: `C:\dev\demo` (`raw\<scene>\` frames, `assets\demo_photo.png` neutral test image, `state.json` request id). Output goes to `C:\Users\ASUS ROG STRIX\Videos\FixFlow-demo\`.

## Environment state (checked 2026-11-13 ~22:20)
Docker stack up (backend, db, web), API ready, web 200, phone connected over USB (`adb reverse tcp:8000 tcp:8000`, server URL in the app
`http://localhost:8000`), the Android app is signed OUT (sign in as `tech1.a@fixflow.test`, password `Demo-2345!`; phone UI language can be switched to EN with the toggle).
Smart Assign must pick **Erlan Moldobekov (tech1.a)** because the phone uses that account. Web accounts: `customer1.a@fixflow.test`,
`dispatcher.a@fixflow.test` (two organizations: choose "AIT Facility"), password `Demo-2345!`. Sessions last 60 minutes.
The author's own scrcpy window `FixFlow-Phone` may be open; for clips use a second headless scrcpy with `--no-window`/`-N`.

## Scene plan (target length after editing)
0:00-0:30 intro: title card + stack bullets, real landing page, architecture card. 0:30-1:15 customer (login, new HIGH HVAC request
"Air conditioner is not cooling", photo, request number + status). 1:15-2:15 dispatcher (triage, Smart Assign, assign Erlan, schedule).
2:15-3:15 Android (SLA card, accept, start, note, photo). 3:15-3:55 offline (`docker compose stop backend`, note -> Pending sync,
`docker compose start backend`, synced once). 3:55-4:25 completion (Android complete; web: Completed, customer closes + 5 stars, history).
4:25-5:00 tests (real runs: bun test, flutter test, backend in Docker sped up) + clean-clone/make-up PASS from `docs/VERIFICATION.md` + engineering decision caption + end card
"FixFlow - From Request to Resolution". Captions in English, lower third, short. Cross-fades 0.4 s, no music.

## DECISIONS CHANGED BY THE AUTHOR (latest wins)
- The WHOLE video must be in **Russian**: web UI in RU, Android UI in RU, Russian request title/description, Russian captions
  («Создание заявки», «Назначение техника», «Работа в Android», «Офлайн-режим», «Завершение работы», «Результаты тестирования»).
  An English take (request #94) was recorded first and then **CANCELED** (cleanup, via API); it is not used.
- The author asked for REAL photos instead of the grey test image: two CC0 photos from Wikimedia Commons (author Alf van Beem; downloaded with the
  author's permission): `C:\dev\demo\assets\photo_problem.jpg` (customer) and `photo_after.jpg` (technician). They show an air handling unit, no people.
- I (Claude) perform the demonstration actions myself (browser via CDP, phone via adb); the author records nothing.

## Done (2026-11-13 ~23:10)
- FFmpeg 9.0.2 installed; DevTools-protocol driver `C:\dev\demo\lib\cdp.ts` works (probe OK). Chrome profiles: `profiles\customer` (port 9341, already switched to RU
  with the in-app RU button), `profiles\dispatcher` (port 9342, RU). A Chrome with `--lang=ru-RU` on a new profile did not open its debug port: do not use that flag.
- Scripts must be created with the Write tool (bash heredocs lose backslashes in Windows paths). Every script must end with `process.exit(0)`.
- **Stage 1 DONE** (`s1_ru.ts`, raw `raw\s1_customer_ru`, ~1134 frames): customer signs in, creates request **#95 "Кондиционер не охлаждает"**, HVAC, Высокий, Building A, adds `photo_problem.jpg`.
- **Stage 2 DONE** (`s2_dispatcher.ts`, raw `raw\s2_dispatcher`, 442 frames, 30 s; marks in `frames.json`): dispatcher opens #95, "Отметить обработанной" + confirm, Умное назначение, assigns **Erlan Moldobekov**
  (verified in PostgreSQL: #95 SCHEDULED, Erlan, 2026-11-16 09:00 Bishkek), opens Расписание.
- Phone: UI Automator works (`adb shell uiautomator dump`, bounds + text/content-desc), so buttons can be found by text and tapped. The app is signed OUT now.

## Phone plan and traps (stages 3-6, same request #95, account tech1.a@fixflow.test)
- Stop the author's window scrcpy (only one client per device), record with `scrcpy -N --no-audio --record=C:\dev\demo\raw\phone.mp4 --video-bit-rate 4M` (or `--no-playback`), log wall-clock
  timestamps for every action (JSON), cut and speed up in the edit. **Crop the status bar** (top ~80 px) in the edit: it shows personal notification icons.
- `adb shell input text` cannot type Cyrillic. Plan: type Russian notes by tapping Gboard keys (switch to the Russian layout with the globe key, read key bounds from a uiautomator dump, tap each letter);
  if Russian is not enabled in Gboard, use Latin notes and tell the author (do not install an IME or change phone settings without asking).
- **Photo picker shows the author's PERSONAL photos**: push `photo_after.jpg` to `/sdcard/Pictures/` with `MSYS_NO_PATHCONV=1`, and in the edit **blur the whole picker region** for those seconds (caption
  «личные фото скрыты»); never show the picker unblurred.
- Offline step: `docker compose stop backend` -> add note -> status «Ожидает синхронизации» -> `docker compose start backend` (data is kept) -> synced once.
- Web finish: customer profile (port 9341, session may need a new login), open #95, «Закрыть заявку», 5 stars + «Отправить отзыв», show history/timeline.
- Tests scene: record a real terminal (ffmpeg gdigrab of a region or a window) running `bun test`, `flutter test`, and the backend tests (sped up), plus the clean-clone/make-up table from `docs/VERIFICATION.md`.

## Remaining steps
3. Phone clips (login, task, SLA, accept, start, note, photo, offline, complete). 4. Web closing clip. 5. Tests clip. 6. Title/architecture cards (Russian) and captions.
7. Edit with ffmpeg (per-scene filter graphs, `setpts`, `drawtext` with `C:/Windows/Fonts/segoeui.ttf`, `xfade`), encode `libx264 -crf 18 -an +faststart` to
   `C:\Users\ASUS ROG STRIX\Videos\FixFlow-demo\FixFlow_demo_ru_no_voice.mp4`. 8. Deliver the MP4 path, Russian narration text by scene with timestamps, the scene list, and an honest statement of what is real
   (and what was blurred/cropped). Anything that fails must be reported, not hidden.
