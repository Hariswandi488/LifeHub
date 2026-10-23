"""Logika todo. Data di SQLite (tabel todos + todo_completions).

Tipe todo (mirip alarm):
  once   -> tunggal, boleh punya deadline tanggal tertentu
  daily  -> muncul setiap hari
  weekly -> muncul di hari-hari tertentu (Senin=0 ... Minggu=6)
Semua tipe boleh punya jam (due_time).
"""
import calendar
import re
from datetime import timedelta

from .common import DAYS_SHORT, fmt_date, now, parse_date, today
from .db import get_db

SUBJECTS = ["tugas", "project", "random"]

REPEAT_TYPES = {
    "once": "Sekali (tunggal)",
    "daily": "Setiap hari",
    "weekly": "Hari tertentu",
}

TYPE_LABELS = {
    "all": "All",
    "once": "Sekali",
    "daily": "Harian",
    "weekly": "Hari tertentu",
}

FILTER_LIST = {
    "status": ["all", "active", "completed"],
    "subject": ["all"] + SUBJECTS,
    "type": ["all", "once", "daily", "weekly"],
    "deadline": [
        "all", "overdue", "today", "tomorrow",
        "this_week", "next_week", "this_month", "next_month",
    ],
}

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# ---------------------------------------------------------------- helper jadwal

def occurs_on(todo, day):
    """Apakah todo ini 'jatuh' di tanggal `day`?"""
    if todo["repeat_type"] == "once":
        return todo["deadline"] == day.isoformat()
    if day.isoformat() < todo["start_date"]:
        return False
    if todo["repeat_type"] == "daily":
        return True
    return day.weekday() in todo["weekdays_list"]


def occurs_in_range(todo, start, end):
    if todo["repeat_type"] == "once":
        d = parse_date(todo["deadline"])
        return d is not None and start <= d <= end
    day = max(start, parse_date(todo["start_date"]) or start)
    while day <= end:
        if occurs_on(todo, day):
            return True
        day += timedelta(days=1)
    return False


def deadline_range(key, ref):
    """Nama filter -> (tanggal_awal, tanggal_akhir). None kalau bukan filter rentang."""
    if key == "today":
        return ref, ref
    if key == "tomorrow":
        d = ref + timedelta(days=1)
        return d, d
    monday = ref - timedelta(days=ref.weekday())
    if key == "this_week":
        return monday, monday + timedelta(days=6)
    if key == "next_week":
        nxt = monday + timedelta(days=7)
        return nxt, nxt + timedelta(days=6)
    if key == "this_month":
        first = ref.replace(day=1)
        return first, first.replace(day=calendar.monthrange(first.year, first.month)[1])
    if key == "next_month":
        first = (ref.replace(day=1) + timedelta(days=32)).replace(day=1)
        return first, first.replace(day=calendar.monthrange(first.year, first.month)[1])
    return None


def match_deadline(todo, key, ref):
    if key == "all":
        return True
    if key == "overdue":
        return todo["is_overdue"]
    rng = deadline_range(key, ref)
    return True if rng is None else occurs_in_range(todo, *rng)


def schedule_label(todo):
    if todo["repeat_type"] == "once":
        label = fmt_date(todo["deadline"]) if todo["deadline"] else "Tanpa deadline"
    elif todo["repeat_type"] == "daily":
        label = "Setiap hari"
    else:
        label = ", ".join(DAYS_SHORT[i] for i in todo["weekdays_list"])
    if todo["due_time"]:
        label += " • " + todo["due_time"]
    return label


# ---------------------------------------------------------------- baca data

def _hydrate(row, done_today, done_any, ref):
    todo = dict(row)
    todo["weekdays_list"] = [int(x) for x in todo["weekdays"].split(",") if x != ""]
    if todo["repeat_type"] == "once":
        todo["done"] = todo["id"] in done_any
    else:
        todo["done"] = todo["id"] in done_today  # berulang: selesai = sudah dicentang HARI INI
    todo["is_overdue"] = bool(
        todo["repeat_type"] == "once"
        and todo["deadline"]
        and todo["deadline"] < ref.isoformat()
        and not todo["done"]
    )
    todo["schedule_label"] = schedule_label(todo)
    return todo


def _load(uid, where="", params=()):
    """Ambil todo milik user `uid` saja."""
    db = get_db()
    ref = today()
    rows = db.execute("SELECT * FROM todos WHERE user_id = ? " + where,
                      (uid,) + tuple(params)).fetchall()
    done_today = {r[0] for r in db.execute(
        "SELECT c.todo_id FROM todo_completions c JOIN todos t ON t.id = c.todo_id "
        "WHERE t.user_id = ? AND c.done_date = ?", (uid, ref.isoformat()))}
    done_any = {r[0] for r in db.execute(
        "SELECT DISTINCT c.todo_id FROM todo_completions c JOIN todos t ON t.id = c.todo_id "
        "WHERE t.user_id = ?", (uid,))}
    return [_hydrate(r, done_today, done_any, ref) for r in rows]


def _sort_key(todo):
    if todo["repeat_type"] == "once":
        day = todo["deadline"] or "9999-12-31"
    else:
        day = today().isoformat()
    return (todo["done"], day, todo["due_time"] or "99:99", todo["id"])


def get_todo(uid, todo_id):
    found = _load(uid, "AND id = ?", (todo_id,))
    return found[0] if found else None


def list_todos(uid, status="all", subject="all", kind="all", deadline="all", q=""):
    ref = today()
    q = (q or "").strip().lower()
    result = []
    for todo in _load(uid):
        if status == "active" and todo["done"]:
            continue
        if status == "completed" and not todo["done"]:
            continue
        if subject != "all" and todo["subject"] != subject:
            continue
        if kind != "all" and todo["repeat_type"] != kind:
            continue
        if q and q not in (todo["title"] + " " + todo["description"]).lower():
            continue
        if not match_deadline(todo, deadline, ref):
            continue
        result.append(todo)
    return sorted(result, key=_sort_key)


def todos_today(uid):
    """Untuk dashboard: yang jatuh hari ini + yang terlambat."""
    ref = today()
    items = [t for t in _load(uid) if occurs_on(t, ref) or t["is_overdue"]]
    items.sort(key=lambda t: (t["done"], not t["is_overdue"], t["due_time"] or "99:99", t["id"]))
    return items


# ---------------------------------------------------------------- form

def blank_todo():
    return {
        "title": "", "subject": "random", "repeat_type": "once",
        "deadline": "", "weekdays_list": [], "due_time": "", "description": "",
    }


def parse_form(form):
    """Validasi input form. Return (data, errors); data selalu berisi nilai input
    supaya form bisa ditampilkan ulang kalau ada error."""
    errors = []
    title = (form.get("title") or "").strip()
    subject = (form.get("subject") or "random").strip().lower()
    repeat_type = form.get("repeat_type") or "once"
    description = (form.get("description") or "").strip()
    deadline = (form.get("deadline") or "").strip()
    due_time = (form.get("due_time") or "").strip()
    days = sorted({int(x) for x in form.getlist("weekdays") if x in {"0", "1", "2", "3", "4", "5", "6"}})

    if not title:
        errors.append("Judul wajib diisi.")
    elif len(title) > 120:
        errors.append("Judul maksimal 120 karakter.")
    if subject not in SUBJECTS:
        subject = "random"
    if repeat_type not in REPEAT_TYPES:
        errors.append("Tipe todo tidak valid.")
        repeat_type = "once"
    if len(description) > 1000:
        errors.append("Deskripsi maksimal 1000 karakter.")
    if due_time and not TIME_RE.match(due_time):
        errors.append("Format jam harus HH:MM, contoh 07:30.")
    if repeat_type == "once" and deadline and parse_date(deadline) is None:
        errors.append("Format deadline tidak valid.")
    if repeat_type == "weekly" and not days:
        errors.append("Pilih minimal satu hari untuk todo hari tertentu.")

    data = {
        "title": title, "subject": subject, "repeat_type": repeat_type,
        "deadline": deadline if repeat_type == "once" else "",
        "weekdays_list": days if repeat_type == "weekly" else [],
        "due_time": due_time, "description": description,
    }
    return data, errors


# ---------------------------------------------------------------- tulis data

def create_todo(uid, data, creator=""):
    db = get_db()
    cur = db.execute(
        """INSERT INTO todos
           (user_id, title, subject, description, repeat_type, deadline, weekdays,
            due_time, start_date, creator, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            uid, data["title"], data["subject"], data["description"], data["repeat_type"],
            data["deadline"] or None,
            ",".join(str(d) for d in data["weekdays_list"]),
            data["due_time"] or None,
            today().isoformat(), creator, now().isoformat(timespec="seconds"),
        ),
    )
    db.commit()
    return cur.lastrowid


def update_todo(uid, todo_id, data):
    db = get_db()
    old = db.execute("SELECT repeat_type FROM todos WHERE id = ? AND user_id = ?", (todo_id, uid)).fetchone()
    if old is None:
        return False
    db.execute(
        """UPDATE todos SET title=?, subject=?, description=?, repeat_type=?,
           deadline=?, weekdays=?, due_time=? WHERE id=? AND user_id=?""",
        (
            data["title"], data["subject"], data["description"], data["repeat_type"],
            data["deadline"] or None,
            ",".join(str(d) for d in data["weekdays_list"]),
            data["due_time"] or None, todo_id, uid,
        ),
    )
    if old["repeat_type"] != data["repeat_type"]:
        # arti "selesai" beda antar tipe, jadi riwayat centang lama dibuang
        db.execute("DELETE FROM todo_completions WHERE todo_id = ?", (todo_id,))
    db.commit()
    return True


def delete_todo(uid, todo_id):
    db = get_db()
    db.execute("DELETE FROM todos WHERE id = ? AND user_id = ?", (todo_id, uid))
    db.commit()


def toggle_complete(uid, todo_id):
    """Centang / batal centang. Return False kalau todo tidak ada (atau bukan milik user)."""
    todo = get_todo(uid, todo_id)
    if todo is None:
        return False
    db = get_db()
    ref = today().isoformat()
    if todo["done"]:
        if todo["repeat_type"] == "once":
            db.execute("DELETE FROM todo_completions WHERE todo_id = ?", (todo_id,))
        else:
            db.execute("DELETE FROM todo_completions WHERE todo_id = ? AND done_date = ?",
                       (todo_id, ref))
    else:
        db.execute(
            "INSERT OR IGNORE INTO todo_completions (todo_id, done_date, done_at) VALUES (?, ?, ?)",
            (todo_id, ref, now().isoformat(timespec="seconds")),
        )
    db.commit()
    return True
