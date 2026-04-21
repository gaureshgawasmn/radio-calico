#!/usr/bin/env python3
"""
Ratings API for Radio Calico.
User identity is derived from the client IP address (hashed with SHA-256).
nginx must set X-Real-IP $remote_addr when proxying to this server.

Endpoints:
  GET  /api/ratings?song=<title>          → {ups, downs, user_vote}
  POST /api/rate  body: {song, vote}      → {ups, downs, user_vote}

Set DATABASE_URL (e.g. postgresql://user:pass@host/db) for PostgreSQL.
Leave it unset to use SQLite via DB_PATH (default: dev.db beside this script).
"""
import http.server
import socketserver
import json
import hashlib
import urllib.parse
import os

DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = 8089

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras

    def get_db():
        return psycopg2.connect(DATABASE_URL)

    def _execute(conn, sql, params=()):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql.replace("?", "%s"), params)
        return cur

else:
    import sqlite3

    DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "dev.db"))

    def get_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _execute(conn, sql, params=()):
        return conn.execute(sql, params)


def user_id_from_request(handler):
    """SHA-256 hash of the client IP so raw IPs never touch the DB."""
    ip = (
        handler.headers.get("X-Real-IP")
        or handler.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or handler.client_address[0]
    )
    return hashlib.sha256(ip.encode()).hexdigest()


def tally(conn, song):
    row = _execute(conn,
        """SELECT
             SUM(CASE WHEN vote='up'   THEN 1 ELSE 0 END) AS ups,
             SUM(CASE WHEN vote='down' THEN 1 ELSE 0 END) AS downs
           FROM ratings WHERE song = ?""",
        (song,),
    ).fetchone()
    return int(row["ups"] or 0), int(row["downs"] or 0)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/ratings":
            self.send_response(404); self.end_headers(); return

        params  = urllib.parse.parse_qs(parsed.query)
        song    = params.get("song", [""])[0]
        user_id = user_id_from_request(self)

        with get_db() as conn:
            ups, downs = tally(conn, song)
            r = _execute(conn,
                "SELECT vote FROM ratings WHERE song=? AND user_id=?",
                (song, user_id),
            ).fetchone()
            user_vote = r["vote"] if r else None

        self._json({"ups": ups, "downs": downs, "user_vote": user_vote})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/rate":
            self.send_response(404); self.end_headers(); return

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._json({"error": "bad json"}, 400); return

        song    = str(body.get("song", "")).strip()
        vote    = str(body.get("vote", ""))
        user_id = user_id_from_request(self)

        if not song or vote not in ("up", "down"):
            self._json({"error": "invalid input"}, 400); return

        with get_db() as conn:
            existing = _execute(conn,
                "SELECT vote FROM ratings WHERE song=? AND user_id=?",
                (song, user_id),
            ).fetchone()

            if existing:
                if existing["vote"] == vote:
                    # Same button again → toggle off
                    _execute(conn,
                        "DELETE FROM ratings WHERE song=? AND user_id=?",
                        (song, user_id),
                    )
                    user_vote = None
                else:
                    # Switch vote
                    _execute(conn,
                        "UPDATE ratings SET vote=? WHERE song=? AND user_id=?",
                        (vote, song, user_id),
                    )
                    user_vote = vote
            else:
                _execute(conn,
                    "INSERT INTO ratings (song, user_id, vote) VALUES (?,?,?)",
                    (song, user_id, vote),
                )
                user_vote = vote

            conn.commit()
            ups, downs = tally(conn, song)

        self._json({"ups": ups, "downs": downs, "user_vote": user_vote})


def init_db():
    with get_db() as conn:
        _execute(conn, """CREATE TABLE IF NOT EXISTS ratings (
            song       TEXT NOT NULL,
            user_id    TEXT NOT NULL,
            vote       TEXT NOT NULL CHECK(vote IN ('up','down')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (song, user_id)
        )""")
        conn.commit()


if __name__ == "__main__":
    init_db()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", PORT), Handler) as srv:
        print(f"Ratings API on :{PORT}")
        srv.serve_forever()
