"""Logika finance. Data di SQLite (tabel transactions). Nominal = rupiah bulat."""
import calendar
import re
from datetime import date, timedelta

from .common import MONTHS, MONTHS_LONG, fmt_date, now, parse_date, today
from .db import get_db

TYPES = {"income": "Pemasukan", "expense": "Pengeluaran"}

PERIODS = [
    ("day", "Hari"),
    ("week", "Minggu"),
    ("month", "Bulan"),
    ("all", "Semua"),
]

_AMOUNT_RE = re.compile(r"^\d+$|^\d{1,3}([.,]\d{3})+$")


# ---------------------------------------------------------------- input

def parse_amount(raw):
    """'15000', '15.000', 'Rp 15,000' -> 15000. None kalau tidak valid / bukan > 0."""
    text = re.sub(r"(?i)rp", "", raw or "").replace(" ", "")
    if not _AMOUNT_RE.match(text):
        return None
    value = int(re.sub(r"[.,]", "", text))
    return value if 0 < value <= 999_999_999_999 else None


def blank_transaction(kind="expense"):
    return {
        "type": kind if kind in TYPES else "expense",
        "name": "", "amount": "", "note": "", "date": today().isoformat(),
    }


def parse_form(form):
    """Return (data, errors); data berisi nilai input supaya form bisa ditampilkan ulang."""
    errors = []
    kind = form.get("type") or ""
    name = " ".join((form.get("name") or "").split())
    amount_raw = (form.get("amount") or "").strip()
    note = (form.get("note") or "").strip()
    date_raw = (form.get("date") or "").strip() or today().isoformat()

    if kind not in TYPES:
        errors.append("Pilih pemasukan atau pengeluaran.")
        kind = "expense"
    if not name:
        errors.append("Nama wajib diisi (contoh: Gaji, Makan, Bensin).")
    elif len(name) > 60:
        errors.append("Nama maksimal 60 karakter.")
    amount = parse_amount(amount_raw)
    if amount is None:
        errors.append("Nominal harus angka bulat lebih dari 0, contoh 25000 atau 25.000.")
    if parse_date(date_raw) is None:
        errors.append("Format tanggal tidak valid.")
    if len(note) > 200:
        errors.append("Catatan maksimal 200 karakter.")

    data = {
        "type": kind, "name": name, "amount": amount if amount is not None else amount_raw,
        "note": note, "date": date_raw,
    }
    return data, errors


# ---------------------------------------------------------------- CRUD

def canonical_name(uid, name):
    """Kalau nama ini sudah pernah dipakai (beda huruf besar/kecil), pakai ejaan yang lama."""
    row = get_db().execute(
        "SELECT name FROM transactions WHERE user_id = ? AND LOWER(name) = LOWER(?) ORDER BY id LIMIT 1",
        (uid, name),
    ).fetchone()
    return row["name"] if row else name


def create_transaction(uid, data):
    db = get_db()
    data = dict(data, name=canonical_name(uid, data["name"]))
    cur = db.execute(
        "INSERT INTO transactions (user_id, type, name, amount, note, date, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uid, data["type"], data["name"], data["amount"], data["note"], data["date"],
         now().isoformat(timespec="seconds")),
    )
    db.commit()
    return cur.lastrowid


def get_transaction(uid, tx_id):
    return get_db().execute(
        "SELECT * FROM transactions WHERE id = ? AND user_id = ?", (tx_id, uid)).fetchone()


def update_transaction(uid, tx_id, data):
    db = get_db()
    cur = db.execute(
        "UPDATE transactions SET type=?, name=?, amount=?, note=?, date=? WHERE id=? AND user_id=?",
        (data["type"], data["name"], data["amount"], data["note"], data["date"], tx_id, uid),
    )
    db.commit()
    return cur.rowcount > 0


def delete_transaction(uid, tx_id):
    db = get_db()
    db.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (tx_id, uid))
    db.commit()


# ---------------------------------------------------------------- periode

def period_bounds(period, anchor):
    """(awal, akhir) tanggal untuk periode day/week/month di sekitar `anchor`.
    'all' -> (None, None). Minggu dihitung Senin-Minggu."""
    if period == "day":
        return anchor, anchor
    if period == "week":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    if period == "month":
        start = anchor.replace(day=1)
        return start, start.replace(day=calendar.monthrange(start.year, start.month)[1])
    return None, None


def period_label(period, anchor):
    start, end = period_bounds(period, anchor)
    if period == "all":
        return "Semua waktu"
    if period == "day":
        return fmt_date(start, weekday=True)
    if period == "month":
        return "{} {}".format(MONTHS_LONG[start.month - 1], start.year)
    # minggu: "19 - 25 Okt 2026", atau lintas bulan "28 Sep - 4 Okt 2026"
    if start.year != end.year:
        return "{} - {}".format(fmt_date(start), fmt_date(end))
    if start.month != end.month:
        return "{} {} - {} {} {}".format(start.day, MONTHS[start.month - 1],
                                         end.day, MONTHS[end.month - 1], end.year)
    return "{} - {} {} {}".format(start.day, end.day, MONTHS[end.month - 1], end.year)


def shift_anchor(period, anchor, step):
    """Geser periode maju (+1) / mundur (-1)."""
    if period == "day":
        return anchor + timedelta(days=step)
    if period == "week":
        return anchor + timedelta(days=7 * step)
    if period == "month":
        index = anchor.year * 12 + (anchor.month - 1) + step
        return date(index // 12, index % 12 + 1, 1)
    return anchor


# ---------------------------------------------------------------- ringkasan

def balance(uid):
    """Uang saat ini = semua pemasukan - semua pengeluaran (seluruh waktu)."""
    row = get_db().execute(
        "SELECT COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END), 0) "
        "FROM transactions WHERE user_id = ?", (uid,)
    ).fetchone()
    return row[0]


def totals(uid, start, end):
    """Total pemasukan & pengeluaran dalam rentang tanggal (None = semua)."""
    sql = "SELECT type, COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = ?"
    params = [uid]
    if start is not None:
        sql += " AND date BETWEEN ? AND ?"
        params += [start.isoformat(), end.isoformat()]
    sums = {"income": 0, "expense": 0}
    for kind, total in get_db().execute(sql + " GROUP BY type", params):
        sums[kind] = total
    return sums["income"], sums["expense"]


def names_by_type(uid):
    """Nama yang pernah dipakai (paling sering dulu) buat autocomplete di form."""
    result = {"income": [], "expense": []}
    rows = get_db().execute(
        "SELECT type, MIN(name) AS name, COUNT(*) AS c FROM transactions WHERE user_id = ? "
        "GROUP BY type, LOWER(name) ORDER BY c DESC, name", (uid,)
    )
    for row in rows:
        result[row["type"]].append(row["name"])
    return result


def summary(uid, period, anchor):
    """Semua data buat halaman finance: total filter, grup per nama, dan saldo."""
    start, end = period_bounds(period, anchor)
    sql = "SELECT * FROM transactions WHERE user_id = ?"
    params = [uid]
    if start is not None:
        sql += " AND date BETWEEN ? AND ?"
        params += [start.isoformat(), end.isoformat()]
    rows = get_db().execute(sql + " ORDER BY date DESC, id DESC", params).fetchall()

    grouped = {"income": {}, "expense": {}}
    for row in rows:
        key = row["name"].lower()  # "makan" dan "Makan" dianggap nama yang sama
        group = grouped[row["type"]].setdefault(
            key, {"name": row["name"], "count": 0, "total": 0, "rows": []})
        group["count"] += 1
        group["total"] += row["amount"]
        group["rows"].append(row)

    result = {}
    for kind in TYPES:
        groups = sorted(grouped[kind].values(), key=lambda g: (-g["total"], g["name"].lower()))
        kind_total = sum(g["total"] for g in groups)
        for g in groups:
            g["share"] = round(g["total"] * 100 / kind_total) if kind_total else 0
        result[kind] = {"total": kind_total, "groups": groups}

    income, expense = result["income"]["total"], result["expense"]["total"]
    return {
        "balance": balance(uid),
        "label": period_label(period, anchor),
        "start": start,
        "end": end,
        "count": len(rows),
        "income": result["income"],
        "expense": result["expense"],
        "net": income - expense,
        "is_current": start is None or start <= today() <= end,
        "prev_anchor": shift_anchor(period, anchor, -1),
        "next_anchor": shift_anchor(period, anchor, +1),
    }
