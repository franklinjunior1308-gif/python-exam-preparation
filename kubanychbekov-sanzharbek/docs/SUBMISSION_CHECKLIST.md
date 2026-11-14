# Submission checklist: Sunday 2026-11-15 (Asia/Bishkek, UTC+06:00)

**These rules replace the old procedure (shared repository + pull request).** Site: https://lab.solutions.ait.kg (registered for the FixFlow event).

| Deadline | What |
|---|---|
| before **2026-11-15 16:00** | Accept the invitation to the GitHub organization **AITS-Lab** |
| **2026-11-15 16:00** | Your individual **private exam repository** opens |
| until **2026-11-15 18:00** | Push to branch **`main`**; the **last successful push before 18:00 is the official submission** |

Instructor's confirmation (quoted): "No pull request needed. Push your project to the main branch of your repo, in the repo root (not a subfolder). Your last push before 18:00 is what we grade." On the starter files: "you can replace everything in your repo" (replacing the initial README.md and other starter files is allowed; still do not delete anything needlessly, and look at `git status` first).
These instructions change only the **submission procedure**; all technical requirements of the official PDF stay mandatory.

Rules: the whole project goes **directly into the repository root** (not into `kubanychbekov-sanzharbek/`); branch `main`;
**no pull request**; nothing is pushed to the exam repository before 16:00. **Aim to finish by 17:45.** The personal backup repository
(`personal`, branch `fixflow`) is kept as it is and is never deleted; its `main` is not touched and no force push is used.

## A. Before 16:00 (everything local) - status 2026-11-14
- [x] Project verified: `BACKEND_TESTS_IN_DOCKER=1 ./scripts/verify-all.sh` -> `ALL CHECKS PASSED` (backend 284, web 23, Flutter 38; see `docs/VERIFICATION.md`). Tests were re-run on camera the night of 2026-11-13.
- [x] Clean-clone and `make up` rehearsals passed (`docs/VERIFICATION.md`).
- [x] `docs/AI_USAGE.md` present, describes Claude (main assistant) and ChatGPT (references/consultation).
- [x] Final demo video with the author's voice: `C:\Users\ASUS ROG STRIX\Videos\FixFlow-demo\FixFlow_EXAM_FINAL_POLISHED.mp4` (4:25, 1920x1080; web create/assign/Smart Assign, Android work, offline queue + restart + sync, completion, rating, tests); timing report in `FIXFLOW_EXAM_SYNC_TABLE_RU.md` next to it.
- [ ] **Author:** accept the AITS-Lab invitation (before 16:00!) and check that the exam repository appears at 16:00.
- [ ] **Author:** upload the video to YouTube (Unlisted/Public), wait until processing finishes, check that it opens in a private window; send the URL.
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
3. If the organizers placed starter files in the repository root (for example a README), the instructor allows replacing them:
   look at `git status` and `git diff` first, keep our `README.md` (it starts with the YouTube link), and do not delete other files without a reason.
4. Required root layout: `README.md` (first line = YouTube link), `compose.yaml`, `Makefile`, `.env.example`, `.gitignore`, `backend/`, `web/`, `mobile/`, `scripts/`, `docs/` (including `docs/AI_USAGE.md`).
5. Check the exact repository URL first: `git remote -v` must show the private AITS-Lab exam repository, not the personal backup.

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
- [ ] The push succeeded (`git status` says up to date with `origin/main`).
- [ ] On GitHub (repository page, branch `main`) the required files are in the **root**: `README.md`, `compose.yaml`, `Makefile`, `.env.example`, `backend/`, `web/`, `mobile/`, `scripts/`, `docs/` (open `docs/AI_USAGE.md` to be sure); no `kubanychbekov-sanzharbek/` subfolder.
- [ ] The latest commit on `main` shows a time before 18:00 Bishkek (UTC+06:00), ideally before 17:45; no PR was opened.
- [ ] The YouTube link in the first line of `README.md` works while signed out.
- [ ] Target: everything done by 17:45. Stop pushing at 17:55: only the last successful push before 18:00 counts. If something breaks, fix and push again **before 18:00**.

## F. If something goes wrong
- Invitation not accepted / repository not visible at 16:00: refresh, check e-mail and https://lab.solutions.ait.kg, ask the organizers; the local repository stays the source of truth.
- Push rejected: check `git remote -v` (must be the exam repository) and the branch (`main`); if the organizers' root commit exists, `git pull --rebase origin main`, resolve, push again.
- Video still processing at 17:30: use the link anyway and re-check later.
