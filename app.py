from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, get_user_by_email, get_user_by_id

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
    conn = get_db()

    user_row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    total_spent = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]

    tx_count = conn.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]

    top_cat_row = conn.execute(
        "SELECT category FROM expenses WHERE user_id = ? GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        (user_id,),
    ).fetchone()

    tx_rows = conn.execute(
        "SELECT date, description, category, amount FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT 10",
        (user_id,),
    ).fetchall()

    cat_rows = conn.execute(
        "SELECT category, SUM(amount) AS total FROM expenses WHERE user_id = ? GROUP BY category ORDER BY total DESC",
        (user_id,),
    ).fetchall()

    conn.close()

    name = user_row["name"]
    initials = "".join(w[0].upper() for w in name.split()[:2])
    created_at = user_row["created_at"] or ""
    try:
        member_since = datetime.strptime(created_at[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        member_since = "—"

    user = {
        "name": name,
        "email": user_row["email"],
        "member_since": member_since,
        "initials": initials,
    }

    stats = {
        "total_spent": f"₹{total_spent:,.2f}",
        "transaction_count": tx_count,
        "top_category": top_cat_row[0] if top_cat_row else "—",
    }

    transactions = []
    for tx in tx_rows:
        try:
            date_fmt = datetime.strptime(tx["date"], "%Y-%m-%d").strftime("%d %b %Y")
        except ValueError:
            date_fmt = tx["date"]
        transactions.append({
            "date": date_fmt,
            "description": tx["description"] or "—",
            "category": tx["category"],
            "amount": f"₹{tx['amount']:,.2f}",
        })

    cat_total = sum(r["total"] for r in cat_rows) or 1
    categories = [
        {
            "name": r["category"],
            "amount": f"₹{r['total']:,.2f}",
            "percentage": round(r["total"] / cat_total * 100),
        }
        for r in cat_rows
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


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
