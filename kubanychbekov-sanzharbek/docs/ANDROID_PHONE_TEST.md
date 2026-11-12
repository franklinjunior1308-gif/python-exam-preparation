# Installing the APK on a phone and the main end-to-end scenario

APK (build output, not committed): `mobile/build/app/outputs/flutter-apk/app-debug.apk`
(190 268 742 bytes, SHA-256 `e0bd783215647002b4a6e7e5fddf3c81a1eaad5bb12f118b40bd95da04f42085`). A copy for easy
transfer: `C:\Users\<user>\Downloads\FixFlow-debug.apk`. Rebuild: `cd mobile && flutter build apk --debug`.

## 1. Connect the phone to the local backend
- The computer and the phone must be on the **same Wi-Fi** (not a guest network with client isolation).
- Find the computer's IPv4 address: `ipconfig` -> Wi-Fi adapter (on the author's PC: `192.168.0.242`).
- Check from the computer that the API answers on that address:
  `curl http://<IP>:8000/api/v1/health/ready` -> `{"status":"ok","database":"up"}`.
- Check from the **phone's browser**: open `http://<IP>:8000/api/v1/health/live` -> `{"status":"ok"}`. If it does not
  open, the Windows firewall blocks port 8000 for the Wi-Fi network profile: allow it once in an **administrator**
  PowerShell: `New-NetFirewallRule -DisplayName "FixFlow API" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private,Public`
  (and remove it after the demo: `Remove-NetFirewallRule -DisplayName "FixFlow API"`).
- **The API URL is typed in the app at sign-in** (nothing is baked into the APK): `http://<IP>:8000`.
  Android emulator instead: `http://10.0.2.2:8000`. The debug app allows plain HTTP for this local use.

## 2. Install
Option A, USB: enable *Developer options* and *USB debugging* on the phone, connect the cable, accept the prompt on
the phone, then `adb devices` (it must list the phone) and
`adb install -r mobile\build\app\outputs\flutter-apk\app-debug.apk`.
Option B, file: copy `FixFlow-debug.apk` to the phone (USB file transfer, cloud drive, messenger), open it, allow
"install unknown apps" for that one app when asked, install. Play Protect may warn about an unknown debug app:
choose *Install anyway*.

## 3. Main scenario (customer -> dispatcher -> technician -> web)
All demo passwords are `Demo-2345!` (demo-only). Organization "AIT Facility". Technician in the app:
`tech2.a@fixflow.test` (Azamat Kenzhebaev, skills hvac + plumbing).

| # | Where | Action | Expected |
|---|---|---|---|
| 1 | Web, customer `customer1.a@fixflow.test` | New request: category **HVAC** or **Plumbing**, a property, a photo; Submit | Request appears with status *Submitted* |
| 2 | Web, dispatcher `dispatcher.a@fixflow.test` | Open the request, *Mark as triaged*, Smart Assign, choose **Azamat Kenzhebaev**, Assign | Status *Scheduled*; the visit shows in the schedule |
| 3 | Phone | Sign in: server `http://<IP>:8000`, `tech2.a@fixflow.test`; pull to refresh | The new task is in the list |
| 4 | Phone | Open the task, *Accept*, *Start* (if an estimate is required, approve it first as the customer in the web) | Status becomes *In progress* |
| 5 | Phone | Add a note and a photo (camera or gallery) | They appear in the queue and then on the request in the web |
| 6 | Phone | **Airplane mode on**, add another note | Shown as *Pending* in the offline queue |
| 7 | Phone | Airplane mode off, wait or pull to refresh | Queue empties; the web shows exactly one copy of the note |
| 8 | Phone | *Complete* with a summary of at least 20 characters and at least one photo | Status *Completed* |
| 9 | Web, dispatcher | Refresh the request | Status *Completed*, history entries, notes and photo visible, SLA final |
| 10 | Web, customer | Open the completed request, rate 1-5 | Feedback saved once |
| 11 | Web, dispatcher | Book the same technician at the same time as another visit | Refused with a conflict (409) message |

## 4. Result of this check
Fill in after running the scenario (do not mark a line done unless you saw it):

| Item | Result | Date |
|---|---|---|
| APK installed on a real phone | not yet confirmed | |
| Phone reaches `http://<IP>:8000` | not yet confirmed | |
| Steps 1-11 above | not yet confirmed | |

Already verified without a phone: the same app code (sign-in, task list into the local database, offline queue,
retry with the same command id, photo upload, refused state change) passed `flutter test test/live` against the real
API through the computer's LAN address `http://192.168.0.242:8000` (2 passed), and `GET /health/ready` answers on that
address (Docker Desktop's inbound rule for the Public network profile is present).
