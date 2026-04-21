#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Backend tests (Python unittest) ==="
python3 -m unittest discover -s "$ROOT/tests" -p "test_api.py" -v

echo ""
echo "=== Frontend tests ==="
echo "Open in browser (nginx must be running):"
echo "  http://localhost:8088/tests/test_utils.html"
echo ""
echo "Start nginx: nginx -c $ROOT/nginx/nginx.conf"
