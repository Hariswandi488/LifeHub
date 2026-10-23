import hmac
import os
import sqlite3
from datetime import timedelta

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)

from src import auth, db, finance_logic, todo_logic
from src.common import fmt_date, parse_date, rupiah, today

app = Flask(__name__)

# Kode undangan (opsional). Kalau LIFEHUB_INVITE_CODE diisi, hanya yang tahu kodenya
# yang bisa membuat akun. Disarankan diisi di hosting supaya tidak sembarang orang daftar.
INVITE_CODE = os.environ.get("LIFEHUB_INVITE_CODE", "")

app.secret_key = auth.load_secret_key()
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)

db.init_app(app)
app.jinja_env.filters["rupiah"] = rupiah
app.jinja_env.filters["fmt_date"] = fmt_date

PUBLIC_ENDPOINTS = ("login", "register", "static")


# ------------------------------------------------------------------ auth

@app.before_request
def load_user():
    g.user = None
    user_id = session.get("uid")
    if user_id:
        g.user = auth.get_user(user_id)
        if g.user is None:  # akun sudah tidak ada
            session.clear()
    if g.user is None and request.endpoint not in PUBLIC_ENDPOINTS:
        nxt = request.full_path if request.method == "GET" else None
        return redirect(url_for("login", next=nxt))
    return None


@app.context_processor
def inject_globals():
    return {"current_user": g.get("user")}


def uid():
    """ID user yang sedang login. Semua query data WAJIB pakai ini."""
    return g.user["id"]


def safe_next(default):
    """Alamat balik setelah aksi. Hanya path lokal (cegah open redirect)."""
    nxt = request.form.get("next") or request.args.get("next") or ""
    if nxt.startswith("/") and not nxt.startswith("//") and "\\" not in nxt:
        return nxt
    return default


def _start_session(user_id):
    session.clear()
    session["uid"] = user_id
    session.permanent = True


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("home"))
    error = None
    username = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        user, error = auth.authenticate(username, request.form.get("password") or "")
        if user:
            _start_session(user["id"])
            return redirect(safe_next(url_for("home")))
    return render_template("login.html", error=error, username=username,
                           next=request.args.get("next") or request.form.get("next") or "")


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("home"))
    errors = []
    username = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        errors = auth.validate_register(username, password, request.form.get("confirm") or "")
        if INVITE_CODE and not hmac.compare_digest(
                (request.form.get("invite") or "").encode(), INVITE_CODE.encode()):
            errors.append("Kode undangan salah.")
        if not errors:
            try:
                user_id = auth.create_user(username, password)
            except sqlite3.IntegrityError:
                errors.append("Username sudah dipakai.")
            else:
                _start_session(user_id)
                flash("Akun dibuat. Selamat datang, %s!" % username, "success")
                return redirect(url_for("home"))
    return render_template("register.html", errors=errors, username=username,
                           invite_required=bool(INVITE_CODE))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------------------ home

@app.route("/", methods=["GET"])
def home():
    ref = today()
    month_start, month_end = finance_logic.period_bounds("month", ref)
    income, expense = finance_logic.totals(uid(), month_start, month_end)
    todos = todo_logic.todos_today(uid())
    return render_template(
        "index.html",
        today_label=fmt_date(ref, weekday=True),
        balances=finance_logic.balances(uid()),
        month_income=income,
        month_expense=expense,
        todos=todos,
        done_count=sum(1 for t in todos if t["done"]),
        overdue_count=sum(1 for t in todos if t["is_overdue"]),
    )


# ------------------------------------------------------------------ todo

@app.route("/task", methods=["GET"])
def task():
    filters = {}
    for key in ("status", "subject", "type", "deadline"):
        value = request.args.get(key, "all")
        filters[key] = value if value in todo_logic.FILTER_LIST[key] else "all"
    q = request.args.get("q", "").strip()

    todos = todo_logic.list_todos(
        uid(), status=filters["status"], subject=filters["subject"], kind=filters["type"],
        deadline=filters["deadline"], q=q,
    )
    return render_template(
        "tasks/task.html",
        tasks=todos,
        filters=filters,
        q=q,
        has_filters=bool(q) or any(v != "all" for v in filters.values()),
        filter_list=todo_logic.FILTER_LIST,
        type_labels=todo_logic.TYPE_LABELS,
    )


def _task_form(mode, task_data, **extra):
    return render_template(
        "tasks/form.html", mode=mode, task=task_data,
        subjects=todo_logic.SUBJECTS, repeat_types=todo_logic.REPEAT_TYPES, **extra,
    )


@app.route("/task/add", methods=["GET", "POST"])
def add_task():
    if request.method == "POST":
        data, errors = todo_logic.parse_form(request.form)
        if not errors:
            todo_logic.create_todo(uid(), data, g.user["username"])
            flash("Task ditambahkan.", "success")
            return redirect(url_for("task"))
        for message in errors:
            flash(message, "error")
        return _task_form("add", data)
    return _task_form("add", todo_logic.blank_todo())


@app.route("/task/edit/id=<int:id>", methods=["GET", "POST"])
def edit_task(id):
    todo = todo_logic.get_todo(uid(), id)
    if todo is None:
        abort(404)

    if request.method == "POST":
        data, errors = todo_logic.parse_form(request.form)
        if not errors:
            todo_logic.update_todo(uid(), id, data)
            flash("Task disimpan.", "success")
            return redirect(safe_next(url_for("task")))
        for message in errors:
            flash(message, "error")
        return _task_form("edit", dict(data, id=id))
    return _task_form("edit", todo)


@app.route("/task/delete/id=<int:id>", methods=["POST"])
def delete_task(id):
    if todo_logic.get_todo(uid(), id) is None:
        abort(404)
    todo_logic.delete_todo(uid(), id)
    flash("Task dihapus.", "success")
    return redirect(safe_next(url_for("task")))


@app.route("/task/complete/id=<int:id>", methods=["POST"])
def complete_task(id):
    if not todo_logic.toggle_complete(uid(), id):
        abort(404)
    return redirect(safe_next(url_for("task")))


# ------------------------------------------------------------------ finance

@app.route("/finance", methods=["GET"])
def finance():
    period = request.args.get("period", "month")
    if period not in dict(finance_logic.PERIODS):
        period = "month"
    anchor = parse_date(request.args.get("date", "")) or today()
    bucket = request.args.get("bucket", "all")
    if bucket not in finance_logic.BUCKETS:
        bucket = "all"
    return render_template(
        "finance/finance.html",
        period=period, anchor=anchor, periods=finance_logic.PERIODS,
        types=finance_logic.TYPES, buckets=finance_logic.BUCKETS,
        directions=finance_logic.TRANSFER_DIRECTIONS, bucket_filter=bucket,
        **finance_logic.summary(uid(), period, anchor, bucket),
    )


def _finance_form(mode, tx_data, **extra):
    return render_template(
        "finance/form.html", mode=mode, tx=tx_data, types=finance_logic.TYPES,
        buckets=finance_logic.BUCKETS,
        names=finance_logic.names_by_type(uid()), next_url=safe_next(""), **extra,
    )


@app.route("/finance/add", methods=["GET", "POST"])
def finance_add():
    if request.method == "POST":
        data, errors = finance_logic.parse_form(request.form)
        if not errors:
            finance_logic.create_transaction(uid(), data)
            flash("Transaksi disimpan.", "success")
            return redirect(safe_next(url_for("finance")))
        for message in errors:
            flash(message, "error")
        return _finance_form("add", data)
    return _finance_form("add", finance_logic.blank_transaction(
        request.args.get("type", "expense"), request.args.get("bucket", "saku")))


@app.route("/finance/edit/id=<int:id>", methods=["GET", "POST"])
def finance_edit(id):
    tx = finance_logic.get_transaction(uid(), id)
    if tx is None:
        abort(404)
    if request.method == "POST":
        data, errors = finance_logic.parse_form(request.form)
        if not errors:
            finance_logic.update_transaction(uid(), id, data)
            flash("Transaksi diperbarui.", "success")
            return redirect(safe_next(url_for("finance")))
        for message in errors:
            flash(message, "error")
        return _finance_form("edit", dict(data, id=id))
    return _finance_form("edit", dict(tx))


@app.route("/finance/delete/id=<int:id>", methods=["POST"])
def finance_delete(id):
    if finance_logic.get_transaction(uid(), id) is None:
        abort(404)
    finance_logic.delete_transaction(uid(), id)
    flash("Transaksi dihapus.", "success")
    return redirect(safe_next(url_for("finance")))


def _transfer_form(mode, data, **extra):
    return render_template(
        "finance/transfer.html", mode=mode, tr=data,
        directions=finance_logic.TRANSFER_DIRECTIONS,
        balances=finance_logic.balances(uid()), next_url=safe_next(""), **extra,
    )


@app.route("/finance/transfer", methods=["GET", "POST"])
def finance_transfer():
    if request.method == "POST":
        data, errors = finance_logic.parse_transfer_form(uid(), request.form)
        if not errors:
            finance_logic.create_transfer(uid(), data)
            flash("Dana dipindahkan.", "success")
            return redirect(safe_next(url_for("finance")))
        for message in errors:
            flash(message, "error")
        return _transfer_form("add", data)
    return _transfer_form("add", finance_logic.blank_transfer(request.args.get("direction", "to_savings")))


@app.route("/finance/transfer/edit/id=<int:id>", methods=["GET", "POST"])
def finance_transfer_edit(id):
    transfer = finance_logic.get_transfer(uid(), id)
    if transfer is None:
        abort(404)
    if request.method == "POST":
        data, errors = finance_logic.parse_transfer_form(uid(), request.form, exclude_id=id)
        if not errors:
            finance_logic.update_transfer(uid(), id, data)
            flash("Perpindahan dana diperbarui.", "success")
            return redirect(safe_next(url_for("finance")))
        for message in errors:
            flash(message, "error")
        return _transfer_form("edit", dict(data, id=id))
    return _transfer_form("edit", dict(transfer))


@app.route("/finance/transfer/delete/id=<int:id>", methods=["POST"])
def finance_transfer_delete(id):
    if finance_logic.get_transfer(uid(), id) is None:
        abort(404)
    finance_logic.delete_transfer(uid(), id)
    flash("Perpindahan dana dihapus.", "success")
    return redirect(safe_next(url_for("finance")))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
