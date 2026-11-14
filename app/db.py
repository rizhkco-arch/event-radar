import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from .geo import bounding_box, haversine_km
from .normalize import CST, now_cst, to_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT, first_name TEXT,
    city TEXT DEFAULT 'suzhou',
    lat REAL, lon REAL,
    radius_km REAL DEFAULT 30,
    foreign_only INTEGER DEFAULT 0,
    cats TEXT DEFAULT '[]',
    notify INTEGER DEFAULT 1,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedupe_key TEXT UNIQUE,
    title TEXT, description TEXT,
    start_time TEXT, end_time TEXT,
    venue TEXT, address TEXT, city TEXT,
    lat REAL, lon REAL,
    category TEXT, source TEXT, source_url TEXT,
    price TEXT, language TEXT,
    foreign_score REAL, is_foreign INTEGER,
    created_at TEXT, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_time);
CREATE INDEX IF NOT EXISTS idx_events_latlon ON events(lat, lon);
CREATE TABLE IF NOT EXISTS saved_events (
    user_id INTEGER, event_id INTEGER, PRIMARY KEY (user_id, event_id)
);
CREATE TABLE IF NOT EXISTS notified (
    user_id INTEGER, event_id INTEGER, PRIMARY KEY (user_id, event_id)
);
CREATE TABLE IF NOT EXISTS ingest_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT, city TEXT, started TEXT, finished TEXT,
    fetched INTEGER, inserted INTEGER, error TEXT
);
"""

EVENT_COLUMNS = [
    "dedupe_key", "title", "description", "start_time", "end_time", "venue",
    "address", "city", "lat", "lon", "category", "source", "source_url",
    "price", "language", "foreign_score", "is_foreign",
]


class Database:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        import os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with self._conn() as con:
            con.executescript(SCHEMA)

    def _conn(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def upsert_user(self, telegram_id: int, username: str = None, first_name: str = None, lat=None, lon=None, city=None, radius_km=None):
        from .cities import CITIES
        with self._lock, self._conn() as con:
            row = con.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
            if row is None:
                c = CITIES.get(city or "suzhou") or CITIES["suzhou"]
                con.execute(
                    "INSERT INTO users (telegram_id, username, first_name, city, lat, lon, radius_km, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (telegram_id, username, first_name, city or "suzhou", lat if lat is not None else c["lat"], lon if lon is not None else c["lon"], radius_km or 30, to_iso(now_cst())),
                )
            else:
                if username is not None:
                    con.execute("UPDATE users SET username=? WHERE telegram_id=?", (username, telegram_id))
                if first_name is not None:
                    con.execute("UPDATE users SET first_name=? WHERE telegram_id=?", (first_name, telegram_id))
                if lat is not None and lon is not None:
                    con.execute("UPDATE users SET lat=?, lon=? WHERE telegram_id=?", (lat, lon, telegram_id))
                if city:
                    con.execute("UPDATE users SET city=? WHERE telegram_id=?", (city, telegram_id))
                if radius_km is not None:
                    con.execute("UPDATE users SET radius_km=? WHERE telegram_id=?", (radius_km, telegram_id))

    def get_user(self, telegram_id: int):
        with self._conn() as con:
            row = con.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
            return dict(row) if row else None

    def update_user(self, telegram_id: int, **fields):
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._lock, self._conn() as con:
            con.execute(f"UPDATE users SET {cols} WHERE telegram_id=?", (*fields.values(), telegram_id))

    def get_cats(self, user) -> list:
        try:
            return json.loads(user.get("cats") or "[]")
        except Exception:
            return []

    def set_cats(self, telegram_id: int, cats: list):
        self.update_user(telegram_id, cats=json.dumps(cats, ensure_ascii=False))

    def insert_event(self, ev: dict):
        now = to_iso(now_cst())
        with self._lock, self._conn() as con:
            existing = con.execute("SELECT id FROM events WHERE dedupe_key=?", (ev["dedupe_key"],)).fetchone()
            if existing:
                con.execute(
                    f"UPDATE events SET {', '.join(c + '=?' for c in EVENT_COLUMNS)}, updated_at=? WHERE dedupe_key=?",
                    (*[ev[c] for c in EVENT_COLUMNS], now, ev["dedupe_key"]),
                )
                return existing["id"], False
            cur = con.execute(
                f"INSERT INTO events ({', '.join(EVENT_COLUMNS)}, created_at, updated_at) VALUES ({', '.join('?' for _ in EVENT_COLUMNS)}, ?, ?)",
                (*[ev[c] for c in EVENT_COLUMNS], now, now),
            )
            return cur.lastrowid, True

    def _row_to_event(self, row) -> dict:
        return dict(row)

    def events_in_radius(self, lat: float, lon: float, radius_km: float, after: datetime = None, limit: int = 50, categories=None, foreign_only: bool = False, city: str = None):
        after = after or now_cst()
        min_lat, max_lat, min_lon, max_lon = bounding_box(lat, lon, radius_km)
        sql = "SELECT * FROM events WHERE start_time >= ? AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?"
        args = [to_iso(after), min_lat, max_lat, min_lon, max_lon]
        if categories:
            sql += f" AND category IN ({', '.join('?' for _ in categories)})"
            args.extend(categories)
        if foreign_only:
            sql += " AND is_foreign = 1"
        if city:
            sql += " AND city = ?"
            args.append(city)
        sql += " ORDER BY start_time ASC LIMIT 500"
        with self._conn() as con:
            rows = con.execute(sql, args).fetchall()
        out = []
        for r in rows:
            e = self._row_to_event(r)
            e["distance_km"] = haversine_km(lat, lon, e["lat"], e["lon"])
            if e["distance_km"] <= radius_km:
                out.append(e)
        out.sort(key=lambda e: (e["start_time"], e["distance_km"]))
        return out[:limit]

    def users_matching_event(self, lat: float, lon: float):
        with self._conn() as con:
            rows = con.execute("SELECT * FROM users WHERE notify=1 AND lat IS NOT NULL AND lon IS NOT NULL").fetchall()
        out = []
        for r in rows:
            u = dict(r)
            u["distance_km"] = haversine_km(u["lat"], u["lon"], lat, lon)
            if u["distance_km"] <= u["radius_km"]:
                out.append(u)
        return out

    def all_users(self):
        with self._conn() as con:
            return [dict(r) for r in con.execute("SELECT * FROM users").fetchall()]

    def is_notified(self, user_id: int, event_id: int) -> bool:
        with self._conn() as con:
            return con.execute("SELECT 1 FROM notified WHERE user_id=? AND event_id=?", (user_id, event_id)).fetchone() is not None

    def mark_notified(self, user_id: int, event_id: int):
        with self._lock, self._conn() as con:
            con.execute("INSERT OR IGNORE INTO notified (user_id, event_id) VALUES (?, ?)", (user_id, event_id))

    def save_event(self, user_id: int, event_id: int):
        with self._lock, self._conn() as con:
            con.execute("INSERT OR IGNORE INTO saved_events (user_id, event_id) VALUES (?, ?)", (user_id, event_id))

    def unsave_event(self, user_id: int, event_id: int):
        with self._lock, self._conn() as con:
            con.execute("DELETE FROM saved_events WHERE user_id=? AND event_id=?", (user_id, event_id))

    def saved_events(self, user_id: int):
        with self._conn() as con:
            rows = con.execute(
                "SELECT e.* FROM events e JOIN saved_events s ON s.event_id=e.id WHERE s.user_id=? ORDER BY e.start_time ASC",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def log_ingest(self, source: str, city: str, started: str, finished: str, fetched: int, inserted: int, error: str = None):
        with self._lock, self._conn() as con:
            con.execute(
                "INSERT INTO ingest_log (source, city, started, finished, fetched, inserted, error) VALUES (?,?,?,?,?,?,?)",
                (source, city, started, finished, fetched, inserted, error),
            )

    def recent_logs(self, limit: int = 15):
        with self._conn() as con:
            return [dict(r) for r in con.execute("SELECT * FROM ingest_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

    def stats(self):
        with self._conn() as con:
            users = con.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            events = con.execute("SELECT COUNT(*) c FROM events").fetchone()["c"]
            future = con.execute("SELECT COUNT(*) c FROM events WHERE start_time >= ?", (to_iso(now_cst()),)).fetchone()["c"]
            foreign = con.execute("SELECT COUNT(*) c FROM events WHERE is_foreign=1").fetchone()["c"]
            return {"users": users, "events": events, "future_events": future, "foreign_events": foreign}

    def get_event(self, event_id: int):
        with self._conn() as con:
            r = con.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
            return dict(r) if r else None
