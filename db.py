import json
import os
import sqlite3
from threading import Lock

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "rumor_game.db")

_lock = Lock()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS game_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            data TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


def load_state():
    conn = get_conn()
    row = conn.execute("SELECT data FROM game_state WHERE id = 1").fetchone()
    conn.close()
    if row:
        return json.loads(row["data"])
    return None


def save_state(state: dict):
    with _lock:
        conn = get_conn()
        conn.execute(
            """
            INSERT INTO game_state (id, data) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET data = excluded.data
            """,
            (json.dumps(state),),
        )
        conn.commit()
        conn.close()


def wipe_state():
    with _lock:
        conn = get_conn()
        conn.execute("DELETE FROM game_state WHERE id = 1")
        conn.commit()
        conn.close()
