"""Helper umum: zona waktu, parsing tanggal, dan format tampilan."""
import os
from datetime import date, datetime, timedelta, timezone

# PythonAnywhere jalan di UTC. Tanpa ini "hari ini" bisa meleset (WIB = UTC+7).
# Ganti lewat environment variable LIFEHUB_TZ kalau bukan WIB (mis. Asia/Makassar).
try:
    from zoneinfo import ZoneInfo

    TZ = ZoneInfo(os.environ.get("LIFEHUB_TZ", "Asia/Jakarta"))
except Exception:  # tzdata belum ke-install -> fallback tetap WIB
    TZ = timezone(timedelta(hours=7))

MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
          "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
MONTHS_LONG = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
               "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
DAYS_SHORT = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
DAYS_LONG = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def now():
    return datetime.now(TZ)


def today():
    return now().date()


def parse_date(value):
    """'2026-10-21' -> date, atau None kalau kosong/tidak valid."""
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def fmt_date(value, weekday=False):
    """date atau string ISO -> '21 Okt 2026' (opsional diawali nama hari)."""
    if isinstance(value, str):
        value = parse_date(value)
    if not value:
        return ""
    text = "{} {} {}".format(value.day, MONTHS[value.month - 1], value.year)
    if weekday:
        text = "{}, {}".format(DAYS_LONG[value.weekday()], text)
    return text


def rupiah(value):
    """15000 -> 'Rp 15.000', -5000 -> '-Rp 5.000'."""
    value = int(value or 0)
    sign = "-" if value < 0 else ""
    return "{}Rp {:,}".format(sign, abs(value)).replace(",", ".")
