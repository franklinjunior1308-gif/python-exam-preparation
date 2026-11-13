# FixFlow: one-command helpers around Docker Compose and the check scripts.
#   make up      build and start PostgreSQL + API + web, wait until the API is ready, load the demo data
#   make help    list every target
# Needs Docker with the Compose plugin, `make` and `curl`. Windows: run it from Git Bash and install make first
# (for example `winget install ezwinports.make`). Nothing here deletes your data except `make reset CONFIRM=yes`.

SHELL := /bin/sh
COMPOSE ?= docker compose

.DEFAULT_GOAL := help
.PHONY: help up start stop restart down ps status logs seed sla-scan pm-generate smoke \
        test-backend test-web test-mobile verify apk adb-reverse reset

help: ## Show this list
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  make %-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Build and start db + backend + web, wait for readiness, load demo data (safe to repeat)
	$(COMPOSE) up -d --build
	@echo "Waiting for the API to become ready..."
	@api=$$($(COMPOSE) port backend 8000 | sed 's/.*://'); ok=0; \
	for i in $$(seq 1 90); do \
	  if curl -fs "http://localhost:$$api/api/v1/health/ready" >/dev/null 2>&1; then ok=1; break; fi; \
	  sleep 2; \
	done; \
	if [ "$$ok" -ne 1 ]; then echo "The API did not become ready in 3 minutes."; $(COMPOSE) logs --tail 40 backend; exit 1; fi
	$(MAKE) seed
	@api=$$($(COMPOSE) port backend 8000 | sed 's/.*://'); web=$$($(COMPOSE) port web 3000 | sed 's/.*://'); \
	echo ""; \
	echo "FixFlow is running:"; \
	echo "  Web  http://localhost:$$web"; \
	echo "  API  http://localhost:$$api   (docs: /docs, health: /api/v1/health/ready)"; \
	echo "Demo accounts: see README.md (password Demo-2345!, demo only)."

start: ## Start the containers that already exist (no rebuild)
	$(COMPOSE) up -d

stop: ## Stop the containers, keep them and all data
	$(COMPOSE) stop

restart: ## Restart the containers (data is kept)
	$(COMPOSE) restart

down: ## Remove the containers and the network; the data volumes are KEPT
	$(COMPOSE) down

ps: ## Show the containers and their health
	$(COMPOSE) ps

status: ## Check that the API and the web answer
	@api=$$($(COMPOSE) port backend 8000 | sed 's/.*://'); web=$$($(COMPOSE) port web 3000 | sed 's/.*://'); \
	echo "API  ready : $$(curl -s http://localhost:$$api/api/v1/health/ready || echo not reachable)"; \
	echo "Web  /login: HTTP $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:$$web/login || echo 000)"

logs: ## Follow the logs of all services (Ctrl+C to leave)
	$(COMPOSE) logs -f --tail 100

seed: ## Demo data: organizations, users, requests, plans, estimates (safe to repeat, never duplicates)
	$(COMPOSE) run --rm backend python -m app.seed
	$(COMPOSE) run --rm backend python -m app.seed_extra

sla-scan: ## Find overdue requests and create the escalations (SLA-07, safe to repeat)
	$(COMPOSE) run --rm backend python -m app.sla_scan

pm-generate: ## Create the requests of preventive-maintenance events that are due (PM-05, safe to repeat)
	$(COMPOSE) run --rm backend python -m app.pm_generate

smoke: ## Real HTTP smoke test of the running, seeded system
	./scripts/smoke.sh

test-backend: ## Backend: ruff, format, ty and pytest on PostgreSQL inside Docker (do not run two at once)
	$(COMPOSE) --profile test run --rm backend-tests

test-web: ## Web: install, lint, typecheck, tests, build (needs Bun)
	cd web && bun install --frozen-lockfile && bun run lint && bun run typecheck && bun run test:ci && bun run build

test-mobile: ## Android app: format check, analyze, tests (needs Flutter)
	cd mobile && flutter pub get && dart format --output=none --set-exit-if-changed lib test && flutter analyze && flutter test

verify: ## Everything: backend (in Docker), web and mobile, ends with ALL CHECKS PASSED
	BACKEND_TESTS_IN_DOCKER=1 ./scripts/verify-all.sh

apk: ## Build the debug APK -> mobile/build/app/outputs/flutter-apk/app-debug.apk
	cd mobile && flutter build apk --debug

adb-reverse: ## Phone on USB: let it reach the API as http://localhost:8000 (needs adb and USB debugging)
	adb reverse tcp:8000 tcp:8000

reset: ## DESTRUCTIVE: delete this project's database and uploads. Needs CONFIRM=yes
	@if [ "$(CONFIRM)" != "yes" ]; then \
	  echo "This DELETES the local FixFlow database and uploaded files (Docker volumes of this project only)."; \
	  echo "Run  make reset CONFIRM=yes  if you really want that."; \
	  exit 1; \
	fi
	$(COMPOSE) down -v
