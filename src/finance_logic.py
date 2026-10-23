"""Logika finance. Data di SQLite (tabel transactions). Nominal = rupiah bulat."""
import calendar
import re
from datetime import date, timedelta

from .common import MONTHS, MONTHS_LONG, fmt_date, now, parse_date, rupiah, today
from .db import get_db

TYPES = {"income": "Pemasukan", "expense": "Pengeluaran"}

# Dua kantong uang: saku = bisa dipakai langsung, simpanan = tidak dipakai langsung.
BUCKETS = {"saku": "Saku", "simpanan": "Simpanan"}

TRANSFER_DIRECTIONS = {
    "to_savings": "Saku → Simpanan",
    "to_pocket": "Simpanan → Saku",
}

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


def blank_transaction(kind="expense", bucket="saku"):
    return {
        "type": kind if kind in TYPES else "expense",
        "bucket": bucket if bucket in BUCKETS else "saku",
        "name": "", "amount": "", "note": "", "date": today().isoformat(),
    }


def parse_form(form):
    """Return (data, errors); data berisi nilai input supaya form bisa ditampilkan ulang."""
    errors = []
    kind = form.get("type") or ""
    bucket = form.get("bucket") or "saku"
    name = " ".join((form.get("name") or "").split())
    amount_raw = (form.get("amount") or "").strip()
    note = (form.get("note") or "").strip()
    date_raw = (form.get("date") or "").strip() or today().isoformat()

    if kind not in TYPES:
        errors.append("Pilih pemasukan atau pengeluaran.")
        kind = "expense"
    if bucket not in BUCKETS:
        errors.append("Pilih Saku atau Simpanan.")
        bucket = "saku"
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
        "type": kind, "bucket": bucket, "name": name,
        "amount": amount if amount is not None else amount_raw,
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
        "INSERT INTO transactions (user_id, type, bucket, name, amount, note, date, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (uid, data["type"], data["bucket"], data["name"], data["amount"], data["note"], data["date"],
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
        "UPDATE transactions SET type=?, bucket=?, name=?, amount=?, note=?, date=? WHERE id=? AND user_id=?",
        (data["type"], data["bucket"], data["name"], data["amount"], data["note"], data["date"], tx_id, uid),
    )
    db.commit()
    return cur.rowcount > 0


def delete_transaction(uid, tx_id):
    db = get_db()
    db.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (tx_id, uid))
    db.commit()


# ---------------------------------------------------------------- perpindahan dana

def blank_transfer(direction="to_savings"):
    return {
        "direction": direction if direction in TRANSFER_DIRECTIONS else "to_savings",
        "amount": "", "note": "", "date": today().isoformat(),
    }


def parse_transfer_form(uid, form, exclude_id=None):
    """Return (data, errors). Dana yang dipindah tidak boleh melebihi saldo kantong asal."""
    errors = []
    direction = form.get("direction") or ""
    amount_raw = (form.get("amount") or "").strip()
    note = (form.get("note") or "").strip()
    date_raw = (form.get("date") or "").strip() or today().isoformat()

    if direction not in TRANSFER_DIRECTIONS:
        errors.append("Pilih arah perpindahan dana.")
        direction = "to_savings"
    amount = parse_amount(amount_raw)
    if amount is None:
        errors.append("Nominal harus angka bulat lebih dari 0, contoh 100000 atau 100.000.")
    if parse_date(date_raw) is None:
        errors.append("Format tanggal tidak valid.")
    if len(note) > 200:
        errors.append("Catatan maksimal 200 karakter.")
    if amount is not None and not errors:
        source = "saku" if direction == "to_savings" else "simpanan"
        available = balances(uid, exclude_transfer=exclude_id)[source]
        if amount > available:
            errors.append("Saldo {} tidak cukup (tersisa {}).".format(
                BUCKETS[source], rupiah(max(available, 0))))

    data = {
        "direction": direction, "amount": amount if amount is not None else amount_raw,
        "note": note, "date": date_raw,
    }
    return data, errors


def create_transfer(uid, data):
    db = get_db()
    cur = db.execute(
        "INSERT INTO transfers (user_id, direction, amount, note, date, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (uid, data["direction"], data["amount"], data["note"], data["date"],
         now().isoformat(timespec="seconds")),
    )
    db.commit()
    return cur.lastrowid


def get_transfer(uid, transfer_id):
    return get_db().execute(
        "SELECT * FROM transfers WHERE id = ? AND user_id = ?", (transfer_id, uid)).fetchone()


def update_transfer(uid, transfer_id, data):
    db = get_db()
    cur = db.execute(
        "UPDATE transfers SET direction=?, amount=?, note=?, date=? WHERE id=? AND user_id=?",
        (data["direction"], data["amount"], data["note"], data["date"], transfer_id, uid),
    )
    db.commit()
    return cur.rowcount > 0


def delete_transfer(uid, transfer_id):
    db = get_db()
    db.execute("DELETE FROM transfers WHERE id = ? AND user_id = ?", (transfer_id, uid))
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

def balances(uid, exclude_transfer=None):
    """Saldo per kantong + total (seluruh waktu).
    Saku = pemasukan - pengeluaran (kantong saku) - pindah ke simpanan + tarik dari simpanan.
    Simpanan = kebalikannya. Total tidak terpengaruh perpindahan dana."""
    db = get_db()
    pocket = savings = 0
    for bucket, kind, total in db.execute(
        "SELECT bucket, type, COALESCE(SUM(amount), 0) FROM transactions "
        "WHERE user_id = ? GROUP BY bucket, type", (uid,)
    ):
        signed = total if kind == "income" else -total
        if bucket == "saku":
            pocket += signed
        else:
            savings += signed
    sql = "SELECT direction, COALESCE(SUM(amount), 0) FROM transfers WHERE user_id = ?"
    params = [uid]
    if exclude_transfer is not None:
        sql += " AND id != ?"
        params.append(exclude_transfer)
    for direction, total in db.execute(sql + " GROUP BY direction", params):
        if direction == "to_savings":
            pocket -= total
            savings += total
        else:
            pocket += total
            savings -= total
    return {"saku": pocket, "simpanan": savings, "total": pocket + savings}


def balance(uid):
    """Uang saat ini (total semua kantong)."""
    return balances(uid)["total"]


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


def summary(uid, period, anchor, bucket="all"):
    """Semua data buat halaman finance: total filter, grup per nama, perpindahan dana, saldo.
    bucket = 'all' | 'saku' | 'simpanan' -> menyaring daftar transaksi (saldo tidak ikut disaring)."""
    start, end = period_bounds(period, anchor)
    sql = "SELECT * FROM transactions WHERE user_id = ?"
    params = [uid]
    if bucket in BUCKETS:
        sql += " AND bucket = ?"
        params.append(bucket)
    if start is not None:
        sql += " AND date BETWEEN ? AND ?"
        params += [start.isoformat(), end.isoformat()]
    rows = get_db().execute(sql + " ORDER BY date DESC, id DESC", params).fetchall()

    t_sql = "SELECT * FROM transfers WHERE user_id = ?"
    t_params = [uid]
    if start is not None:
        t_sql += " AND date BETWEEN ? AND ?"
        t_params += [start.isoformat(), end.isoformat()]
    transfers = get_db().execute(t_sql + " ORDER BY date DESC, id DESC", t_params).fetchall()
    moved = {"to_savings": 0, "to_pocket": 0}
    for t in transfers:
        moved[t["direction"]] += t["amount"]

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
        "balances": balances(uid),
        "transfers": transfers,
        "moved": moved,
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
