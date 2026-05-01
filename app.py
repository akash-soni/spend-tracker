from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, get_user_by_email, get_user_by_id
from database.queries import get_summary_stats, get_recent_transactions, get_category_breakdown

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-before-production"  # TODO: use env var in production

with app.app_context():
    init_db()
    seed_db()


@app.context_processor
def inject_current_user():
    user_id = session.get("user_id")
    return {"current_user": get_user_by_id(user_id) if user_id else None}


# ------------------------------------------------------------------ #
# Date-filter helpers                                                 #
# ------------------------------------------------------------------ #

def _parse_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except (ValueError, TypeError):
        return None


def _compute_presets():
    today = date.today()
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)

    m, y = today.month - 3, today.year
    if m <= 0:
        m, y = m + 12, y - 1

    return {
        "this_month":    (first_this.isoformat(), today.isoformat()),
        "last_month":    (last_prev.replace(day=1).isoformat(), last_prev.isoformat()),
        "last_3_months": (date(y, m, 1).isoformat(), today.isoformat()),
        "all_time":      (None, None),
    }


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not name or not email or not password:
        return render_template("register.html", error="All fields are required.", name=name, email=email)

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.", name=name, email=email)

    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return render_template("register.html", error="An account with that email already exists.", name=name, email=email)

    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash(password)),
    )
    conn.commit()
    conn.close()

    flash("Account created — please sign in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    user = get_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.", "error")
        return render_template("login.html")

    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]

    user_row = get_user_by_id(user_id)
    display_name = user_row["name"]
    initials = "".join(w[0].upper() for w in display_name.split()[:2])
    created_at = user_row["created_at"] or ""
    try:
        member_since = datetime.strptime(created_at[:10], "%Y-%m-%d").strftime("%B %Y")
    except ValueError:
        member_since = "—"
    user = {
        "name": display_name,
        "email": user_row["email"],
        "member_since": member_since,
        "initials": initials,
    }

    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))

    presets = _compute_presets()
    active_preset = "all_time"
    if start_date is not None or end_date is not None:
        active_preset = "custom"
        for key, (ps, pe) in presets.items():
            if key == "all_time":
                continue
            if start_date == ps and end_date == pe:
                active_preset = key
                break

    preset_urls = {}
    for key, (ps, pe) in presets.items():
        if ps is None:
            preset_urls[key] = url_for("profile")
        else:
            preset_urls[key] = url_for("profile", start_date=ps, end_date=pe)

    def _fmt(iso):
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d %b %Y")

    if start_date and end_date:
        filter_label = f"{_fmt(start_date)} – {_fmt(end_date)}"
    elif start_date:
        filter_label = f"From {_fmt(start_date)}"
    elif end_date:
        filter_label = f"Up to {_fmt(end_date)}"
    else:
        filter_label = "All time"

    stats = get_summary_stats(user_id, start_date, end_date)
    transactions = get_recent_transactions(user_id, start_date=start_date, end_date=end_date)
    categories = get_category_breakdown(user_id, start_date, end_date)

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        preset_urls=preset_urls,
        active_preset=active_preset,
        filter_label=filter_label,
        start_date=start_date or "",
        end_date=end_date or "",
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
