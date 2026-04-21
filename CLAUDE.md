# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Project

```bash
# Start the ratings API (port 8089)
python3 /home/student/radiocalico/api.py

# Start Nginx web server (port 8088)
nginx -c /home/student/radiocalico/nginx/nginx.conf

# Stop Nginx
nginx -c /home/student/radiocalico/nginx/nginx.conf -s stop
```

The UI is served at `http://localhost:8088`. Nginx proxies `/api/*` requests to the Python backend at `127.0.0.1:8089`.

There are no build steps, package managers, or external dependencies for local dev — the backend uses only Python stdlib and the frontend loads HLS.js from CDN. Docker is available for containerised deployment (see below).

## Architecture

**Radio Calico** is a web-based HLS audio streaming player with a crowdsourced song-rating system.

### Components

- **`index.html`** — Frontend markup (~88 lines). Polls CloudFront every 10 seconds for track metadata, streams audio via HLS.js, displays album art, and sends ratings to the local API.
- **`style.css`** — All styles for the widget (CSS custom properties, layout, animations).
- **`app.js`** — All frontend JavaScript (HLS player, metadata polling, ratings, equalizer bars). Depends on `utils.js`.
- **`utils.js`** — Pure utility functions shared between `app.js` and the test suite: `truncate`, `fmtQuality`, `fmtStreamLevel`, `escHtml`, `applyRatingState`, `resetRatings`.
- **`api.py`** — Python `http.server`-based ratings backend. Two endpoints:
  - `GET /api/ratings?song=<title>` → `{ups, downs, user_vote}`
  - `POST /api/rate` body `{song, vote}` (vote: `"up"` or `"down"`)
  - `DB_PATH` is configurable via the `DB_PATH` environment variable (defaults to `dev.db` next to the script).
- **`dev.db`** — SQLite database. The `ratings` table is the only active one; the `test` table is unused.
- **`nginx/nginx.conf`** — Serves static files from the repo root and reverse-proxies `/api/` to the Python server. Also forwards `X-Real-IP` so the API can hash the client IP for anonymous user identification.
- **`nginx/nginx.docker.conf`** — Docker-specific Nginx config; proxies to the `api` service by container hostname instead of `127.0.0.1`.
- **`Dockerfile`** — Python 3.12-slim image for the API service.
- **`Dockerfile.nginx`** — Nginx Alpine image that bakes in static assets for production.
- **`docker-compose.yml`** — Dev compose setup: mounts source files as volumes, exposes port `8088`.
- **`docker-compose.prod.yml`** — Production compose setup: bakes assets into images, exposes port `80`, uses a named volume `db_data` for the SQLite file.

### Key Data Flows

1. **Metadata**: Frontend fetches `https://d3d4yli4hf5bmh.cloudfront.net/metadatav2.json` every 10 s for `title`, `artist`, `album`, `bit_depth`, `sample_rate`, and up to 5 previous tracks.
2. **Cover art**: Fetched from a separate CloudFront endpoint alongside the metadata.
3. **Audio**: HLS stream from CloudFront, managed by HLS.js attached to `<audio id="audio">`.
4. **Ratings**: User identity is a SHA-256 hash of the client IP (privacy-preserving, no accounts). Votes are togglable and switchable (up ↔ down). One row per `(song, user_id)` primary key.

### Database Schema

```sql
CREATE TABLE ratings (
    song       TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    vote       TEXT NOT NULL CHECK(vote IN ("up","down")),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (song, user_id)
);
```

## Docker

```bash
# Dev (hot-reload via volume mounts, port 8088)
docker compose up

# Production (baked images, port 80)
docker compose -f docker-compose.prod.yml up --build
```

The API container reads `DB_PATH=/app/data/dev.db` (dev) or `DB_PATH=/app/data/ratings.db` (prod). The named volume `db_data` persists across restarts.

## Testing

### Backend (Python unittest)

```bash
python3 -m unittest discover -s tests -p "test_api.py" -v
# or use the helper script:
bash tests/run_tests.sh
```

`tests/test_api.py` has two layers:
- **Unit tests** (`TestTally`, `TestUserIdFromRequest`) — in-memory SQLite, no network.
- **Integration tests** (`TestRatingsHTTP`) — real HTTP server on a random OS-assigned port, temp DB wiped between tests.

### Frontend (browser)

Open `http://localhost:8088/tests/test_utils.html` while nginx is running. The page runs all `utils.js` unit tests inline and shows a pass/fail summary.

## Branding (from `RadioCalico_Style_Guide.txt`)

- **Colors**: Mint `#D8F2D5`, Forest Green `#1F4E23`, Teal `#38A29D`, Orange `#EFA63C`, Charcoal `#231F20`
- **Fonts**: Montserrat (headings), Open Sans (body)
- **Voice**: Friendly, trustworthy, no-nonsense — ad-free, data-free, subscription-free

