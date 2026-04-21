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

There are no build steps, package managers, or external dependencies — the backend uses only Python stdlib and the frontend loads HLS.js from CDN.

## Architecture

**Radio Calico** is a web-based HLS audio streaming player with a crowdsourced song-rating system.

### Components

- **`index.html`** — Frontend markup (~88 lines). Polls CloudFront every 10 seconds for track metadata, streams audio via HLS.js, displays album art, and sends ratings to the local API.
- **`style.css`** — All styles for the widget (CSS custom properties, layout, animations).
- **`app.js`** — All frontend JavaScript (HLS player, metadata polling, ratings, equalizer bars).
- **`api.py`** — Python `http.server`-based ratings backend. Two endpoints:
  - `GET /api/ratings?song=<title>` → `{ups, downs, user_vote}`
  - `POST /api/rate` body `{song, vote}` (vote: `"up"` or `"down"`)
- **`dev.db`** — SQLite database. The `ratings` table is the only active one; the `test` table is unused.
- **`nginx/nginx.conf`** — Serves static files from the repo root and reverse-proxies `/api/` to the Python server. Also forwards `X-Real-IP` so the API can hash the client IP for anonymous user identification.

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

## Branding (from `RadioCalico_Style_Guide.txt`)

- **Colors**: Mint `#D8F2D5`, Forest Green `#1F4E23`, Teal `#38A29D`, Orange `#EFA63C`, Charcoal `#231F20`
- **Fonts**: Montserrat (headings), Open Sans (body)
- **Voice**: Friendly, trustworthy, no-nonsense — ad-free, data-free, subscription-free

## No Test Suite

There are no automated tests. Manual testing requires running both servers and opening `http://localhost:8088` in a browser.
