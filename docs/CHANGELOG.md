# Changelog LifeHub

Log setiap update, yang terbaru di paling atas. Tidak berisi secret.

---

## Fase 1: Saku dan Simpanan (2026-10-23)

**Yang berubah**
- "Uang saat ini" dipisah jadi dua kantong: **Saku** (bisa dipakai langsung) dan **Simpanan** (tidak dipakai langsung), plus baris total.
- Tiap pemasukan/pengeluaran punya pilihan kantong ("Masuk ke" / "Diambil dari"). Default: Saku.
- Fitur **Pindahkan dana** (Saku ke Simpanan atau sebaliknya): tambah, edit, hapus. Perpindahan **bukan** pemasukan/pengeluaran, jadi total periode dan total uang tidak berubah.
- Halaman finance: dua kartu saldo, filter kantong (Semua / Saku / Simpanan), badge kantong di tiap transaksi, bagian "Perpindahan dana" mengikuti filter hari/minggu/bulan.
- Dashboard: kartu "Uang saat ini" menampilkan total, Saku, dan Simpanan.

**Aturan**
- Pindahkan dana lebih dari saldo kantong asal ditolak (saat edit, perpindahan itu sendiri tidak dihitung).
- Pengeluaran boleh membuat saldo minus (tampil merah).
- Transaksi lama otomatis masuk Saku, jadi angka uang saat ini tidak berubah.

**File**
- Diubah: `app.py`, `src/db.py`, `src/finance_logic.py`, `templates/finance/finance.html`, `templates/finance/form.html`, `templates/index.html`, `static/css/finance/finance.css`, `static/css/form.css`, `static/css/index.css`, `static/js/finance_form.js`.
- Baru: `templates/finance/transfer.html`, `docs/CHANGELOG.md`.

**Migrasi database (jalan otomatis saat Reload, hanya menambah, data lama tidak diubah)**
- `ALTER TABLE transactions ADD COLUMN bucket` (default `'saku'`, hanya boleh `saku`/`simpanan`).
- `CREATE TABLE transfers` + index `idx_transfers_user_date`.
- Versi database: belum bernomor (sistem versi masuk di Fase 0). Struktur setelah fase ini adalah baseline v1 untuk Fase 0.

**Langkah deploy**
1. Backup manual dulu (Fase 0 belum ada): `cp ~/LifeHub/lifehub.db ~/backup-lifehub-$(date +%Y%m%d).db`
2. Push ke GitHub, lalu `git pull` di Bash console PythonAnywhere.
3. Klik **Reload** di tab Web.
4. Cek halaman Finance: Saku harus sama dengan angka "uang saat ini" sebelumnya, Simpanan Rp 0.
5. Pindahkan uang simpanan lu yang sebenarnya lewat tombol **Pindahkan**.

**Rollback**
- `git checkout` ke commit sebelumnya, lalu salin backup: `cp ~/backup-lifehub-TANGGAL.db ~/LifeHub/lifehub.db`, lalu Reload. Jangan pakai kode lama dengan database baru: kode lama mengabaikan tabel `transfers`, jadi saldo salah.

**Tes**
- 205 pengecekan otomatis lolos (144 sebelumnya + 61 baru): hitungan saldo, aturan perpindahan, validasi, isolasi antar user, payload SQL injection/XSS, invarian acak (saku + simpanan = total = pemasukan - pengeluaran), migrasi dari database lama.
- Tampilan belum dicek langsung di browser.

---

## Baseline: kondisi sebelum Fase 1

- Todo tiga tipe (sekali, harian, hari tertentu) dengan jam opsional, filter status/subject/tipe/deadline, dan pencarian.
- Finance: pemasukan/pengeluaran (rupiah), filter hari/minggu/bulan/semua, grup per nama, total per filter, uang saat ini.
- Akun per user (username + password, register sendiri), data dipisah per akun, kode undangan opsional (`LIFEHUB_INVITE_CODE`), pembatas percobaan login.
- Data di SQLite (`lifehub.db`), zona waktu lewat `LIFEHUB_TZ`.
