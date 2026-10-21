# LifeHub

Todo list + Finance tracker. Flask + SQLite (semua data di satu file: `lifehub.db`, dibuat otomatis).

## Fitur

**Todo** — tiga tipe, mirip alarm:
- **Sekali (tunggal)**: opsional ada deadline tanggal.
- **Setiap hari**: muncul tiap hari, centangnya reset otomatis besok.
- **Hari tertentu**: pilih hari (mis. Sen, Rab, Jum).
- Semua tipe boleh punya jam. Filter: status, subject, tipe, deadline + pencarian.

**Finance** — pemasukan & pengeluaran (rupiah):
- Filter per **hari / minggu (Senin-Minggu) / bulan / semua**, bisa geser maju-mundur.
- Data dipisah pemasukan vs pengeluaran, lalu dikelompokkan **per nama** (klik untuk lihat rinciannya).
- Total pemasukan, pengeluaran, selisih untuk filter yang dipilih, dan **uang saat ini** (seluruh waktu).

**Akun** — username + password, daftar sendiri di `/register`:
- Todo dan finance dipisah per akun; satu akun tidak bisa lihat/ubah data akun lain.
- Password disimpan ter-hash. 5x salah password dalam 5 menit -> ditahan sementara.
- Data lama (kalau sebelumnya sudah ada `lifehub.db`) otomatis jadi milik akun pertama yang daftar.

## Jalanin di lokal

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python app.py                   # buka http://127.0.0.1:5000, lalu klik Daftar
```

## Deploy ke PythonAnywhere (akun gratis)

1. **Ambil kodenya.** Di tab *Consoles* buka Bash, lalu:
   `git clone https://github.com/Hariswandi488/LifeHub.git`
   (atau upload zip lewat tab *Files* dan `unzip`).
2. **Buat virtualenv** (sesuaikan versi Python dengan yang tersedia, minimal 3.10):
   ```bash
   mkvirtualenv lifehub --python=python3.13
   cd ~/LifeHub && pip install -r requirements.txt
   ```
3. Tab **Web** -> *Add a new web app* -> **Manual configuration** -> pilih versi Python yang sama.
4. Di tab Web isi:
   - *Source code*: `/home/USERNAME/LifeHub`
   - *Virtualenv*: `/home/USERNAME/.virtualenvs/lifehub`
5. Klik link **WSGI configuration file**, hapus isinya, ganti dengan ini (ganti `USERNAME` dan password):
   ```python
   import os
   import sys

   path = "/home/USERNAME/LifeHub"
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ["LIFEHUB_INVITE_CODE"] = "ganti-kode-undangan"  # opsional tapi disarankan
   os.environ["LIFEHUB_TZ"] = "Asia/Jakarta"   # WIB; WITA = Asia/Makassar, WIT = Asia/Jayapura

   from app import app as application  # noqa
   ```
6. Klik **Reload**. Web jalan di `https://USERNAME.pythonanywhere.com`.

### Penting
- **Isi `LIFEHUB_INVITE_CODE`.** Web di PythonAnywhere itu publik; tanpa kode undangan, siapa pun yang menemukan URL-nya bisa membuat akun. Kasih kodenya hanya ke orang yang kamu izinkan. Kalau kosong, pendaftaran terbuka untuk semua.
- **Zona waktu.** Server PythonAnywhere memakai UTC. `LIFEHUB_TZ` memastikan "hari ini" di todo dan finance sesuai waktumu.
- **Akun gratis kedaluwarsa 1 bulan.** Buka tab Web lalu klik tombol perpanjang sebelum habis.
- **Update kode:** `git pull` di Bash console, lalu Reload. File `lifehub.db` tidak ikut git (sengaja, isinya data pribadi).
- **Backup:** sesekali download `lifehub.db` dari tab *Files*.

## Struktur

```
app.py                 route (home, task, finance, login)
src/db.py              koneksi SQLite + skema tabel (users, todos, transactions)
src/auth.py            register, login, hash password
src/todo_logic.py      logika todo (tipe, filter, centang)
src/finance_logic.py   logika finance (periode, grup per nama, saldo)
src/common.py          zona waktu + format tanggal/rupiah
templates/ static/     tampilan
```
