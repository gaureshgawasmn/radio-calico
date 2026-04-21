#!/usr/bin/env python3
"""
Unit and integration tests for api.py.

Unit layer  — in-memory SQLite, no network.
Integration — real HTTP server on a random OS-assigned port, temp DB file
              wiped between every test for full isolation.
"""
import hashlib
import http.client
import json
import os
import socketserver
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.parse
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api

SCHEMA = """
CREATE TABLE ratings (
    song       TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    vote       TEXT NOT NULL CHECK(vote IN ("up","down")),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (song, user_id)
)
"""


# ── Unit: tally() ──────────────────────────────────────────────────────────

class TestTally(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(SCHEMA)

    def _ins(self, song, uid, vote):
        self.conn.execute(
            "INSERT INTO ratings (song, user_id, vote) VALUES (?,?,?)",
            (song, uid, vote)
        )

    def test_empty_table_returns_zeros(self):
        ups, downs = api.tally(self.conn, 'No Such Song')
        self.assertEqual(ups, 0)
        self.assertEqual(downs, 0)

    def test_always_returns_ints_not_none(self):
        ups, downs = api.tally(self.conn, 'Ghost Song')
        self.assertIsInstance(ups, int)
        self.assertIsInstance(downs, int)

    def test_single_upvote(self):
        self._ins('Song A', 'u1', 'up')
        ups, downs = api.tally(self.conn, 'Song A')
        self.assertEqual(ups, 1)
        self.assertEqual(downs, 0)

    def test_single_downvote(self):
        self._ins('Song A', 'u1', 'down')
        ups, downs = api.tally(self.conn, 'Song A')
        self.assertEqual(ups, 0)
        self.assertEqual(downs, 1)

    def test_multiple_upvotes(self):
        for i in range(5):
            self._ins('Song A', f'u{i}', 'up')
        ups, downs = api.tally(self.conn, 'Song A')
        self.assertEqual(ups, 5)
        self.assertEqual(downs, 0)

    def test_mixed_votes(self):
        self._ins('Song A', 'u1', 'up')
        self._ins('Song A', 'u2', 'up')
        self._ins('Song A', 'u3', 'down')
        ups, downs = api.tally(self.conn, 'Song A')
        self.assertEqual(ups, 2)
        self.assertEqual(downs, 1)

    def test_votes_for_other_songs_not_counted(self):
        self._ins('Song A', 'u1', 'up')
        self._ins('Song B', 'u1', 'down')
        ups_a, downs_a = api.tally(self.conn, 'Song A')
        ups_b, downs_b = api.tally(self.conn, 'Song B')
        self.assertEqual((ups_a, downs_a), (1, 0))
        self.assertEqual((ups_b, downs_b), (0, 1))

    def test_song_with_no_votes_among_others(self):
        self._ins('Song B', 'u1', 'up')
        ups, downs = api.tally(self.conn, 'Song A')
        self.assertEqual(ups, 0)
        self.assertEqual(downs, 0)


# ── Unit: user_id_from_request() ──────────────────────────────────────────

class _FakeHeaders:
    """Minimal stand-in for http.server BaseHTTPRequestHandler.headers."""
    def __init__(self, data):
        self._d = {k.lower(): v for k, v in data.items()}

    def get(self, key, default=None):
        return self._d.get(key.lower(), default)


def _mock_handler(headers, client_ip='127.0.0.1'):
    h = MagicMock()
    h.headers = _FakeHeaders(headers)
    h.client_address = (client_ip, 9999)
    return h


def _sha(ip):
    return hashlib.sha256(ip.encode()).hexdigest()


class TestUserIdFromRequest(unittest.TestCase):
    def test_x_real_ip_takes_priority_over_forwarded_for(self):
        h = _mock_handler({'X-Real-IP': '10.0.0.1', 'X-Forwarded-For': '192.168.1.1'})
        self.assertEqual(api.user_id_from_request(h), _sha('10.0.0.1'))

    def test_x_forwarded_for_used_when_no_real_ip(self):
        h = _mock_handler({'X-Forwarded-For': '203.0.113.5, 10.0.0.1'}, client_ip='127.0.0.1')
        self.assertEqual(api.user_id_from_request(h), _sha('203.0.113.5'))

    def test_x_forwarded_for_first_ip_only(self):
        h = _mock_handler({'X-Forwarded-For': '1.2.3.4, 5.6.7.8, 9.10.11.12'})
        self.assertEqual(api.user_id_from_request(h), _sha('1.2.3.4'))

    def test_client_address_fallback(self):
        h = _mock_handler({}, client_ip='172.16.0.1')
        self.assertEqual(api.user_id_from_request(h), _sha('172.16.0.1'))

    def test_empty_forwarded_for_falls_through_to_client_address(self):
        h = _mock_handler({'X-Forwarded-For': ''}, client_ip='10.10.10.10')
        self.assertEqual(api.user_id_from_request(h), _sha('10.10.10.10'))

    def test_hash_is_deterministic(self):
        h1 = _mock_handler({'X-Real-IP': '1.2.3.4'})
        h2 = _mock_handler({'X-Real-IP': '1.2.3.4'})
        self.assertEqual(api.user_id_from_request(h1), api.user_id_from_request(h2))

    def test_different_ips_yield_different_hashes(self):
        h1 = _mock_handler({'X-Real-IP': '1.2.3.4'})
        h2 = _mock_handler({'X-Real-IP': '1.2.3.5'})
        self.assertNotEqual(api.user_id_from_request(h1), api.user_id_from_request(h2))

    def test_hash_is_64_char_lowercase_hex(self):
        h = _mock_handler({'X-Real-IP': '1.2.3.4'})
        uid = api.user_id_from_request(h)
        self.assertEqual(len(uid), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in uid))


# ── Integration: real HTTP server, temp DB ─────────────────────────────────

class TestRatingsHTTP(unittest.TestCase):
    """
    Spins up a real ThreadingTCPServer on a random port with a temp SQLite
    file.  setUp() wipes all rows before each test, giving full isolation
    without the overhead of tearing down and recreating the server.
    """

    @classmethod
    def setUpClass(cls):
        cls._db_fd, cls._db_path = tempfile.mkstemp(suffix='.db')
        api.DB_PATH = cls._db_path

        conn = sqlite3.connect(cls._db_path)
        conn.execute(SCHEMA)
        conn.commit()
        conn.close()

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        cls._server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), api.Handler)
        cls._port = cls._server.server_address[1]
        t = threading.Thread(target=cls._server.serve_forever, daemon=True)
        t.start()

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        os.close(cls._db_fd)
        os.unlink(cls._db_path)

    def setUp(self):
        conn = sqlite3.connect(self.__class__._db_path)
        conn.execute('DELETE FROM ratings')
        conn.commit()
        conn.close()

    # ── low-level helpers ──────────────────────────────────────────────────

    def _hconn(self):
        return http.client.HTTPConnection('127.0.0.1', self.__class__._port, timeout=5)

    def _get(self, path, ip='1.1.1.1'):
        c = self._hconn()
        c.request('GET', path, headers={'X-Real-IP': ip})
        r = c.getresponse()
        return r.status, json.loads(r.read())

    def _post(self, path, payload, ip='1.1.1.1'):
        data = json.dumps(payload).encode()
        c = self._hconn()
        c.request('POST', path, body=data,
                  headers={'Content-Type': 'application/json', 'X-Real-IP': ip})
        r = c.getresponse()
        return r.status, json.loads(r.read())

    def _vote(self, song, vote, ip='1.1.1.1'):
        return self._post('/api/rate', {'song': song, 'vote': vote}, ip=ip)

    def _ratings(self, song, ip='1.1.1.1'):
        return self._get(f'/api/ratings?song={urllib.parse.quote(song)}', ip=ip)

    # ── GET /api/ratings ───────────────────────────────────────────────────

    def test_get_unknown_song_returns_zeros_and_null_vote(self):
        status, data = self._ratings('Ghost Song')
        self.assertEqual(status, 200)
        self.assertEqual(data['ups'], 0)
        self.assertEqual(data['downs'], 0)
        self.assertIsNone(data['user_vote'])

    def test_get_reflects_pre_seeded_votes(self):
        conn = sqlite3.connect(self.__class__._db_path)
        uid_a = _sha('10.0.0.1')
        uid_b = _sha('10.0.0.2')
        conn.execute("INSERT INTO ratings (song,user_id,vote) VALUES (?,?,?)", ('Song X', uid_a, 'up'))
        conn.execute("INSERT INTO ratings (song,user_id,vote) VALUES (?,?,?)", ('Song X', uid_b, 'down'))
        conn.commit()
        conn.close()

        status, data = self._ratings('Song X', ip='10.0.0.1')
        self.assertEqual(status, 200)
        self.assertEqual(data['ups'], 1)
        self.assertEqual(data['downs'], 1)
        self.assertEqual(data['user_vote'], 'up')

    def test_get_user_vote_null_when_others_voted_but_not_me(self):
        conn = sqlite3.connect(self.__class__._db_path)
        conn.execute("INSERT INTO ratings (song,user_id,vote) VALUES (?,?,?)",
                     ('Song Y', _sha('10.0.0.1'), 'up'))
        conn.commit()
        conn.close()

        _, data = self._ratings('Song Y', ip='10.0.0.99')
        self.assertEqual(data['ups'], 1)
        self.assertIsNone(data['user_vote'])

    def test_get_wrong_path_returns_404(self):
        c = self._hconn()
        c.request('GET', '/api/nope', headers={'X-Real-IP': '1.1.1.1'})
        r = c.getresponse()
        r.read()
        self.assertEqual(r.status, 404)

    # ── POST /api/rate ─────────────────────────────────────────────────────

    def test_new_upvote(self):
        status, data = self._vote('Song A', 'up')
        self.assertEqual(status, 200)
        self.assertEqual(data['ups'], 1)
        self.assertEqual(data['downs'], 0)
        self.assertEqual(data['user_vote'], 'up')

    def test_new_downvote(self):
        status, data = self._vote('Song A', 'down')
        self.assertEqual(status, 200)
        self.assertEqual(data['ups'], 0)
        self.assertEqual(data['downs'], 1)
        self.assertEqual(data['user_vote'], 'down')

    def test_toggle_off_upvote(self):
        self._vote('Song A', 'up')
        status, data = self._vote('Song A', 'up')
        self.assertEqual(status, 200)
        self.assertEqual(data['ups'], 0)
        self.assertIsNone(data['user_vote'])

    def test_toggle_off_downvote(self):
        self._vote('Song A', 'down')
        status, data = self._vote('Song A', 'down')
        self.assertEqual(status, 200)
        self.assertEqual(data['downs'], 0)
        self.assertIsNone(data['user_vote'])

    def test_switch_up_to_down(self):
        self._vote('Song A', 'up')
        status, data = self._vote('Song A', 'down')
        self.assertEqual(status, 200)
        self.assertEqual(data['ups'], 0)
        self.assertEqual(data['downs'], 1)
        self.assertEqual(data['user_vote'], 'down')

    def test_switch_down_to_up(self):
        self._vote('Song A', 'down')
        status, data = self._vote('Song A', 'up')
        self.assertEqual(status, 200)
        self.assertEqual(data['ups'], 1)
        self.assertEqual(data['downs'], 0)
        self.assertEqual(data['user_vote'], 'up')

    def test_vote_visible_in_subsequent_get(self):
        self._vote('Song A', 'up', ip='5.5.5.5')
        _, data = self._ratings('Song A', ip='5.5.5.5')
        self.assertEqual(data['user_vote'], 'up')
        self.assertEqual(data['ups'], 1)

    def test_toggle_off_visible_in_subsequent_get(self):
        self._vote('Song A', 'up', ip='5.5.5.5')
        self._vote('Song A', 'up', ip='5.5.5.5')
        _, data = self._ratings('Song A', ip='5.5.5.5')
        self.assertIsNone(data['user_vote'])
        self.assertEqual(data['ups'], 0)

    def test_multiple_users_independent(self):
        self._vote('Song A', 'up',   ip='2.0.0.1')
        self._vote('Song A', 'up',   ip='2.0.0.2')
        self._vote('Song A', 'down', ip='2.0.0.3')
        _, data = self._ratings('Song A', ip='2.0.0.99')
        self.assertEqual(data['ups'], 2)
        self.assertEqual(data['downs'], 1)
        self.assertIsNone(data['user_vote'])

    def test_votes_isolated_across_songs(self):
        self._vote('Song A', 'up',   ip='3.0.0.1')
        self._vote('Song B', 'down', ip='3.0.0.1')
        _, data_a = self._ratings('Song A', ip='3.0.0.1')
        _, data_b = self._ratings('Song B', ip='3.0.0.1')
        self.assertEqual(data_a['ups'], 1)
        self.assertEqual(data_a['downs'], 0)
        self.assertEqual(data_b['ups'], 0)
        self.assertEqual(data_b['downs'], 1)

    def test_empty_song_returns_400(self):
        status, data = self._vote('', 'up')
        self.assertEqual(status, 400)
        self.assertIn('error', data)

    def test_whitespace_only_song_returns_400(self):
        status, data = self._vote('   ', 'up')
        self.assertEqual(status, 400)

    def test_missing_song_key_returns_400(self):
        status, data = self._post('/api/rate', {'vote': 'up'})
        self.assertEqual(status, 400)

    def test_invalid_vote_value_returns_400(self):
        status, data = self._vote('Song A', 'meh')
        self.assertEqual(status, 400)
        self.assertIn('error', data)

    def test_missing_vote_key_returns_400(self):
        status, data = self._post('/api/rate', {'song': 'Song A'})
        self.assertEqual(status, 400)

    def test_malformed_json_returns_400(self):
        c = self._hconn()
        body = b'not valid json'
        c.request('POST', '/api/rate', body=body,
                  headers={'Content-Type': 'application/json',
                           'X-Real-IP': '1.1.1.1'})
        r = c.getresponse()
        data = json.loads(r.read())
        self.assertEqual(r.status, 400)
        self.assertIn('error', data)

    def test_post_wrong_path_returns_404(self):
        c = self._hconn()
        c.request('POST', '/api/wrong', body=b'{}',
                  headers={'Content-Type': 'application/json', 'X-Real-IP': '1.1.1.1'})
        r = c.getresponse()
        r.read()
        self.assertEqual(r.status, 404)

    def test_song_with_special_characters(self):
        song = "It's Alive (feat. Ü & Ö)"
        self._vote(song, 'up')
        _, data = self._ratings(song)
        self.assertEqual(data['ups'], 1)

    # ── OPTIONS ───────────────────────────────────────────────────────────

    def test_options_returns_204_with_cors_headers(self):
        c = self._hconn()
        c.request('OPTIONS', '/api/rate')
        r = c.getresponse()
        r.read()
        self.assertEqual(r.status, 204)
        headers = {k.lower(): v for k, v in r.getheaders()}
        self.assertIn('access-control-allow-origin', headers)
        self.assertEqual(headers['access-control-allow-origin'], '*')
        self.assertIn('access-control-allow-methods', headers)


if __name__ == '__main__':
    unittest.main(verbosity=2)
