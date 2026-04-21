# Radio Calico

A web-based HLS audio streaming player with a crowdsourced song-rating system. Ad-free, data-free, subscription-free.

![Radio Calico Logo](RadioCalicoLogoTM.png)

## Features

- Live HLS audio stream via [HLS.js](https://github.com/video-dev/hls.js/)
- Real-time track metadata — title, artist, album, source quality (bit depth & sample rate)
- Album art display with release year badge
- Previous tracks list (up to 5)
- Thumbs up / thumbs down rating system — anonymous, IP-hash based (no accounts)
- Animated equalizer visualizer
- Volume control with mute toggle

## Stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla HTML / CSS / JS |
| Audio | HLS.js (CDN) |
| Backend | Python `http.server` (stdlib only) |
| Database | SQLite |
| Web server | Nginx (static files + reverse proxy) |
| Fonts | Montserrat, Open Sans (Google Fonts) |

No build steps. No package managers. No external runtime dependencies.

## Getting Started

### Prerequisites

- Python 3
- Nginx

### Run

```bash
# Start the ratings API on port 8089
python3 api.py

# Start Nginx on port 8088
nginx -c /path/to/radiocalico/nginx/nginx.conf
```

Open **http://localhost:8088** in your browser.

### Stop

```bash
nginx -c /path/to/radiocalico/nginx/nginx.conf -s stop
```

## Architecture

```
Browser
  │
  ├─ GET /              → Nginx serves index.html, style.css, app.js
  ├─ GET /api/ratings   → Nginx proxies → Python API (port 8089)
  ├─ POST /api/rate     → Nginx proxies → Python API (port 8089)
  │
  └─ CloudFront (external)
       ├─ metadatav2.json  (polled every 10 s)
       ├─ Cover art images
       └─ HLS audio stream
```

### API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/ratings?song=<title>` | Returns `{ ups, downs, user_vote }` |
| `POST` | `/api/rate` | Body: `{ song, vote }` — vote is `"up"` or `"down"` |

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

User identity is a SHA-256 hash of the client IP — no accounts, no tracking.

## Branding

| Token | Value |
|---|---|
| Mint | `#D8F2D5` |
| Forest Green | `#1F4E23` |
| Teal | `#38A29D` |
| Calico Orange | `#EFA63C` |
| Charcoal | `#231F20` |

Headings: **Montserrat** — Body: **Open Sans**
