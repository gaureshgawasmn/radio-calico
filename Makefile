.PHONY: dev dev-down prod prod-down test test-backend test-frontend logs-dev logs-prod security

# ── Dev (SQLite, hot-reload via volume mounts, port 8088) ──────────────────────
dev:
	docker compose up --build -d

dev-down:
	docker compose down

# ── Prod (PostgreSQL, baked images, port 80) ───────────────────────────────────
prod:
	docker compose -f docker-compose.prod.yml up --build -d

prod-down:
	docker compose -f docker-compose.prod.yml down -v

# ── Tests ──────────────────────────────────────────────────────────────────────
test: test-backend test-frontend

test-backend:
	python3 -m unittest discover -s tests -p "test_api.py" -v

test-frontend:
	@echo "Frontend tests: open http://localhost:8088/tests/test_utils.html"
	@echo "(dev stack must be running — use: make dev)"

# ── Logs ───────────────────────────────────────────────────────────────────────
logs-dev:
	docker compose logs -f

logs-prod:
	docker compose -f docker-compose.prod.yml logs -f

# ── Security ───────────────────────────────────────────────────────────────────
# Runs npm audit inside a Docker container — no local Node.js install needed.
# Exits non-zero if any vulnerability at the configured level is found.
security:
	docker run --rm \
	  -v $(CURDIR):/app \
	  -w /app \
	  node:18-alpine \
	  npm audit --audit-level=moderate
