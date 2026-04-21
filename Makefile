.PHONY: security

# ── Security ───────────────────────────────────────────────────────────────────
# Runs npm audit inside a Docker container — no local Node.js install needed.
# Exits non-zero if any vulnerability at the configured level is found.
security:
	docker run --rm \
	  -v $(CURDIR):/app \
	  -w /app \
	  node:18-alpine \
	  npm audit --audit-level=moderate
