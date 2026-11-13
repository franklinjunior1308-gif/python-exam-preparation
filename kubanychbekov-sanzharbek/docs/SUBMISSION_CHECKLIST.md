# Submission checklist: Sunday 2026-11-15 (Asia/Bishkek, UTC+06:00)

**These rules replace the old procedure (shared repository + pull request).** Site: https://lab.solutions.ait.kg (registered for the FixFlow event).

| Deadline | What |
|---|---|
| before **2026-11-15 16:00** | Accept the invitation to the GitHub organization **AITS-Lab** |
| **2026-11-15 16:00** | Your individual **private exam repository** opens |
| until **2026-11-15 18:00** | Push to branch **`main`**; the **last successful push before 18:00 is the official submission** |

Rules: the whole project goes **directly into the repository root** (not into `kubanychbekov-sanzharbek/`); branch `main`;
**no pull request**; nothing is pushed to the exam repository before 16:00. The personal backup repository
(`personal`, branch `fixflow`) is kept as it is and is never deleted.

## A. Before 16:00 (everything local) - status 2026-11-14
- [x] Project verified: `BACKEND_TESTS_IN_DOCKER=1 ./scripts/verify-all.sh` -> `ALL CHECKS PASSED` (backend 284, web 23, Flutter 38; see `docs/VERIFICATION.md`). Tests were re-run on camera the night of 2026-11-13.
- [x] Clean-clone and `make up` rehearsals passed (`docs/VERIFICATION.md`).
- [x] `docs/AI_USAGE.md` present, describes Claude (main assistant) and ChatGPT (references/consultation).
- [x] Demo video built without voice: `C:\Users\ASUS ROG STRIX\Videos\FixFlow-demo\FixFlow_demo_ru_no_voice.mp4` (5:09, one request #96 through the whole flow); narration text in `docs/VIDEO_NARRATION_RU.md`.
- [ ] **Author:** accept the AITS-Lab invitation (before 16:00!) and check that the exam repository appears at 16:00.
- [ ] **Author:** record the Russian voice-over, upload to YouTube (Unlisted/Public), wait until processing finishes, check that it opens in a private window.
- [ ] YouTube URL in the first line of `README.md` (replace the `TODO` line), committed locally in the personal repository.
- [ ] No secrets in the tree: `.env` absent (only `.env.example`), no tokens; the APK is not committed.
- [ ] Dry run of the export (does not touch any repository):
  `powershell -File scripts\export-to-exam-repo.ps1 -Target C:\temp\exam-dry-run -DryRun` -> "required layout: OK", no nested folder, no `.env`, no large files.

## B. 16:00-16:20 get the repository and copy the project to its root
1. Clone the private exam repository (URL from the lab site / GitHub organization) to a new folder:
   ```powershell
   cd C:\work
   git clone https://github.com/AITS-Lab/<YOUR-EXAM-REPO>.git exam
   cd exam
   git branch --show-current        # expect: main (if not: git switch main)
   ```
2. Copy the project **contents** into the root (script excludes `.git`, caches, `.venv`, `.env`, APKs, uploads):
   ```powershell
   & "C:\Users\ASUS ROG STRIX\fixflow\kubanychbekov-sanzharbek\scripts\export-to-exam-repo.ps1" -Target C:\work\exam
   ```
   Read its output: `required layout: OK`, no ERROR lines, size well below 50 MB.
3. If the organizers placed their own files in the repository root (for example a README), do not silently overwrite them:
   look at `git status` and `git diff` first; keep our `README.md` (it contains the video link) unless the organizers require theirs.
4. Required root layout: `README.md`, `compose.yaml`, `Makefile`, `.env.example`, `.gitignore`, `backend/`, `web/`, `mobile/`, `scripts/`, `docs/`.

## C. 16:20-16:45 verify the copy as a reviewer would
- [ ] `cp .env.example .env; make up` (or `docker compose up -d --build`), open http://localhost:3000, sign in with the demo accounts.
- [ ] `./scripts/smoke.sh` prints `smoke: all checks passed`.
- [ ] Delete the `.env` you created (it is ignored by git, but do not leave it around).

## D. 16:45-17:30 commit and push to `main`
```powershell
git status                      # only project files, no .env, no *.apk, no .venv
git add -A
git commit -m "FixFlow: Kubanychbekov Sanzharbek"
git push origin main
```
Meaningful history is welcome: if time allows, commit in several logical commits (backend, web, mobile, docs/scripts) before the push.
No pull request, no extra branches.

## E. 17:30-18:00 final checks
- [ ] The push succeeded (`git status` says up to date with `origin/main`); the files are visible in the repository root on GitHub.
- [ ] The YouTube link in `README.md` works while signed out.
- [ ] Stop pushing at 17:55: only the last successful push before 18:00 counts. If something breaks, fix and push again **before 18:00**.

## F. If something goes wrong
- Invitation not accepted / repository not visible at 16:00: refresh, check e-mail and https://lab.solutions.ait.kg, ask the organizers; the local repository stays the source of truth.
- Push rejected: check `git remote -v` (must be the exam repository) and the branch (`main`); if the organizers' root commit exists, `git pull --rebase origin main`, resolve, push again.
- Video still processing at 17:30: use the link anyway and re-check later.
