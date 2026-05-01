import pytest
from app import app as flask_app
from database.db import get_db
from database.queries import get_recent_transactions, get_summary_stats, get_category_breakdown


@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seed_user_id(app):
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        conn.close()
        return row["id"]


@pytest.fixture
def empty_user_id(app):
    """A user with no expenses."""
    with app.app_context():
        conn = get_db()
        from werkzeug.security import generate_password_hash
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Empty User", "empty@spendly.com", generate_password_hash("password123")),
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        yield user_id
        # cleanup
        conn = get_db()
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()


# ===== ROUTE TESTS =====

def test_profile_unauthenticated(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_authenticated(client, seed_user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = seed_user_id
    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "₹" in body
    assert "256.25" in body
    assert "Bills" in body


# ===== TRANSACTION HISTORY TESTS — SA1 =====

def test_get_recent_transactions_with_expenses(app, seed_user_id):
    with app.app_context():
        transactions = get_recent_transactions(seed_user_id)
    assert len(transactions) == 8
    for item in transactions:
        assert "date" in item
        assert "description" in item
        assert "category" in item
        assert "amount" in item
        assert item["amount"].startswith("₹")
    # Seed dates run 2026-04-01 to 2026-04-10; newest-first means first item is 2026-04-10
    first_date = transactions[0]["date"]
    last_date = transactions[-1]["date"]
    assert first_date > last_date


def test_get_recent_transactions_no_expenses(app, empty_user_id):
    with app.app_context():
        result = get_recent_transactions(empty_user_id)
    assert result == []


# ===== SUMMARY STATS TESTS — SA2 =====

def test_get_summary_stats_with_expenses(app, seed_user_id):
    with app.app_context():
        stats = get_summary_stats(seed_user_id)
    assert stats["transaction_count"] == 8
    assert "256.25" in stats["total_spent"]
    assert stats["total_spent"].startswith("₹")
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_no_expenses(app, empty_user_id):
    with app.app_context():
        result = get_summary_stats(empty_user_id)
    assert result == {"total_spent": "₹0.00", "transaction_count": 0, "top_category": "—"}


# ===== CATEGORY BREAKDOWN TESTS — SA3 =====
# SA3: add tests for get_category_breakdown below this line

def test_get_category_breakdown_with_expenses(app, seed_user_id):
    with app.app_context():
        cats = get_category_breakdown(seed_user_id)
    assert len(cats) == 7
    # Verify each item has the required keys
    for cat in cats:
        assert "name" in cat
        assert "amount" in cat
        assert "pct" in cat
        assert cat["amount"].startswith("₹")
        assert isinstance(cat["pct"], int)
    # Verify ordered by amount descending (parse ₹X,XXX.XX → float)
    amounts = [float(c["amount"].replace("₹", "").replace(",", "")) for c in cats]
    assert amounts == sorted(amounts, reverse=True)
    # Verify pct values sum to exactly 100
    assert sum(c["pct"] for c in cats) == 100


def test_get_category_breakdown_no_expenses(app, empty_user_id):
    with app.app_context():
        result = get_category_breakdown(empty_user_id)
    assert result == []
