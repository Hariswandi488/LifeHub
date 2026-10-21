"""Koneksi SQLite + skema tabel. Semua data disimpan di satu file: lifehub.db"""
import os
import sqlite3

from flask import g

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Path absolut supaya aman di PythonAnywhere (working directory-nya bukan folder project).
DB_PATH = os.environ.get("LIFEHUB_DB", os.path.join(BASE_DIR, "lifehub.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS todos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    subject     TEXT NOT NULL DEFAULT 'random',
    description TEXT NOT NULL DEFAULT '',
    -- once = tunggal | daily = tiap hari | weekly = hari tertentu
    repeat_type TEXT NOT NULL DEFAULT 'once'
                CHECK (repeat_type IN ('once', 'daily', 'weekly')),
    deadline    TEXT,                        -- YYYY-MM-DD (untuk 'once', boleh kosong)
    weekdays    TEXT NOT NULL DEFAULT '',    -- '0,2,4' (Senin=0 ... Minggu=6) untuk 'weekly'
    due_time    TEXT,                        -- HH:MM, opsional
    start_date  TEXT NOT NULL,               -- todo berulang mulai berlaku dari tanggal ini
    creator     TEXT NOT NULL DEFAULT 'Haris',
    created_at  TEXT NOT NULL
);

-- Riwayat centang. 'once': ada 1 baris = selesai. Berulang: 1 baris per tanggal selesai.
CREATE TABLE IF NOT EXISTS todo_completions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    todo_id   INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
    done_date TEXT NOT NULL,
    done_at   TEXT NOT NULL,
    UNIQUE (todo_id, done_date)
);

CREATE TABLE IF NOT EXISTS transactions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    type       TEXT NOT NULL CHECK (type IN ('income', 'expense')),
    name       TEXT NOT NULL,
    amount     INTEGER NOT NULL CHECK (amount > 0),   -- rupiah, bilangan bulat
    note       TEXT NOT NULL DEFAULT '',
    date       TEXT NOT NULL,                         -- YYYY-MM-DD
    created_at TEXT NOT NULL
);
"""


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def _migrate(conn):
    """DB lama (sebelum ada akun) -> tambah kolom user_id. Baris lama dipegang user pertama
    yang mendaftar (lihat auth.create_user)."""
    for table in ("todos", "transactions"):
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(%s)" % table)]
        if "user_id" not in cols:
            conn.execute("ALTER TABLE %s ADD COLUMN user_id INTEGER REFERENCES users(id)" % table)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_todos_user ON todos (user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_user_date ON transactions (user_id, date)")


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
