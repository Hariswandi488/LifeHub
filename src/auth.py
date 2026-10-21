"""Akun user: register, login, dan pengaman sederhana (username + password)."""
import os
import re
import secrets
import sqlite3
import time

from werkzeug.security import check_password_hash, generate_password_hash

from .common import now
from .db import BASE_DIR, get_db

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
MIN_PASSWORD = 8
HASH_METHOD = "pbkdf2:sha256"

# Batasi tebak password: 5x salah per username dalam 5 menit -> ditahan sementara.
# (Disimpan di memori; PythonAnywhere gratis cuma 1 worker, jadi cukup.)
MAX_FAILS = 5
WINDOW = 300
_failures = {}

_DUMMY_HASH = generate_password_hash("dummy-password", method=HASH_METHOD)


def load_secret_key():
    """Kunci penanda cookie sesi. Dari env LIFEHUB_SECRET_KEY, kalau tidak ada dibuat sekali
    lalu disimpan di file .secret_key (tidak ikut git) supaya login tidak hilang saat reload."""
    key = os.environ.get("LIFEHUB_SECRET_KEY")
    if key:
        return key
    path = os.path.join(BASE_DIR, ".secret_key")
    try:
        with open(path) as f:
            key = f.read().strip()
        if key:
            return key
    except OSError:
        pass
    key = secrets.token_hex(32)
    try:
        with open(path, "w") as f:
            f.write(key)
    except OSError:
        pass
    return key


def get_user(user_id):
    return get_db().execute(
        "SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()


def validate_register(username, password, confirm):
    errors = []
    if not USERNAME_RE.match(username):
        errors.append("Username 3-30 karakter: huruf, angka, titik, strip, atau underscore.")
    elif get_db().execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        errors.append("Username sudah dipakai.")
    if len(password) < MIN_PASSWORD:
        errors.append("Password minimal %d karakter." % MIN_PASSWORD)
    elif password != confirm:
        errors.append("Konfirmasi password tidak sama.")
    return errors


def create_user(username, password):
    """Buat akun. User pertama otomatis memegang data lama (dari sebelum ada akun)."""
    db = get_db()
    first = db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    cur = db.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, generate_password_hash(password, method=HASH_METHOD),
         now().isoformat(timespec="seconds")),
    )
    uid = cur.lastrowid
    if first:
        db.execute("UPDATE todos SET user_id = ? WHERE user_id IS NULL", (uid,))
        db.execute("UPDATE transactions SET user_id = ? WHERE user_id IS NULL", (uid,))
    db.commit()
    return uid


def _recent_failures(key):
    cutoff = time.time() - WINDOW
    recent = [t for t in _failures.get(key, []) if t > cutoff]
    _failures[key] = recent
    return recent


def authenticate(username, password):
    """Return (user_row, error). Selalu cek hash walau username tidak ada (anti-timing)."""
    key = username.lower()
    if len(_recent_failures(key)) >= MAX_FAILS:
        return None, "Terlalu banyak percobaan salah. Coba lagi beberapa menit lagi."
    row = get_db().execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?", (username,)).fetchone()
    ok = check_password_hash(row["password_hash"] if row else _DUMMY_HASH, password)
    if row and ok:
        _failures.pop(key, None)
        return row, None
    _failures.setdefault(key, []).append(time.time())
    return None, "Username atau password salah."
