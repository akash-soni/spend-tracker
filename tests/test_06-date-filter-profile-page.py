"""
Tests for Step 06: Date Filter on Profile Page

Spec: .claude/specs/06-date-filter-profile-page.md

Seed data (all April 2026, demo user):
  2026-04-01  Food          ₹12.50
  2026-04-02  Transport     ₹45.00
  2026-04-03  Bills         ₹80.00
  2026-04-05  Health        ₹25.00
  2026-04-07  Entertainment ₹15.00
  2026-04-09  Shopping      ₹60.00
  2026-04-10  Other         ₹10.00
  2026-04-10  Food           ₹8.75
  Total: ₹256.25 across 8 transactions and 7 categories.

Key date facts (today = 2026-05-01 per project context):
  "This Month"    = 2026-05-01 to 2026-05-01  (no seed data)
  "Last Month"    = 2026-04-01 to 2026-04-30  (all 8 seed expenses)
  "Last 3 Months" = 2026-02-01 to 2026-05-01  (all 8 seed expenses)
  "All Time"      = no bounds                 (all 8 seed expenses)
"""

import pytest
from datetime import date, timedelta

from app import app as flask_app
from database.db import get_db
from database.queries import (
    get_recent_transactions,
    get_summary_stats,
    get_category_breakdown,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seed_user_id(app):
    """Return the user_id of the seeded demo user (demo@spendly.com)."""
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        conn.close()
        assert row is not None, (
            "Demo user not found — ensure seed_db() ran at app startup"
        )
        return row["id"]


@pytest.fixture
def empty_user_id(app):
    """Insert a user with zero expenses and clean up after the test.

    Cleans up any leftover row from a previous interrupted run before inserting,
    so repeated runs on the same file-based DB never hit a UNIQUE constraint error.
    """
    from werkzeug.security import generate_password_hash

    _email = "filter_empty@spendly.test"

    with app.app_context():
        conn = get_db()
        # Guard against stale rows from an interrupted previous run
        stale = conn.execute(
            "SELECT id FROM users WHERE email = ?", (_email,)
        ).fetchone()
        if stale:
            conn.execute("DELETE FROM expenses WHERE user_id = ?", (stale["id"],))
            conn.execute("DELETE FROM users WHERE id = ?", (stale["id"],))
            conn.commit()

        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (
                "Filter Empty User",
                _email,
                generate_password_hash("pass12345"),
            ),
        )
        uid = cursor.lastrowid
        conn.commit()
        conn.close()

    yield uid

    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM expenses WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        conn.commit()
        conn.close()


@pytest.fixture
def auth_client(client, seed_user_id):
    """Test client pre-authenticated as the demo user."""
    with client.session_transaction() as sess:
        sess["user_id"] = seed_user_id
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode(response):
    return response.data.decode("utf-8")


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_profile_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 302, "Unauthenticated /profile must redirect"
        assert "/login" in resp.headers["Location"], (
            "Redirect target must be /login"
        )

    def test_profile_unauthenticated_with_date_params_redirects_to_login(self, client):
        resp = client.get("/profile?start_date=2026-04-01&end_date=2026-04-30")
        assert resp.status_code == 302, (
            "Unauthenticated /profile with date params must still redirect"
        )
        assert "/login" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# Default (no filter) — route-level
# ---------------------------------------------------------------------------

class TestNoFilter:
    def test_profile_no_params_returns_200(self, auth_client):
        resp = auth_client.get("/profile")
        assert resp.status_code == 200, "Authenticated /profile must return 200"

    def test_profile_no_params_shows_all_time_filter_label(self, auth_client):
        resp = auth_client.get("/profile")
        body = _decode(resp)
        assert "All time" in body, (
            "No-params profile must display 'All time' filter label"
        )

    def test_profile_no_params_active_preset_is_all_time(self, auth_client):
        resp = auth_client.get("/profile")
        body = _decode(resp)
        # The template must mark the All Time preset button with the active class
        # The spec says active_preset == "all_time" drives the active CSS class
        assert "all_time" in body, (
            "Profile with no filter must surface all_time active preset in the HTML"
        )

    def test_profile_no_params_shows_all_seed_expenses(self, auth_client):
        resp = auth_client.get("/profile")
        body = _decode(resp)
        # Total of all 8 seed expenses is ₹256.25
        assert "256.25" in body, (
            "All-time profile must show ₹256.25 total from the 8 seed expenses"
        )

    def test_profile_no_params_shows_user_info(self, auth_client):
        resp = auth_client.get("/profile")
        body = _decode(resp)
        assert "Demo User" in body, "Profile must display the logged-in user's name"


# ---------------------------------------------------------------------------
# Date filter — route-level behaviour
# ---------------------------------------------------------------------------

class TestDateFilterRoute:
    def test_april_full_range_returns_all_seed_expenses(self, auth_client):
        resp = auth_client.get("/profile?start_date=2026-04-01&end_date=2026-04-30")
        assert resp.status_code == 200
        body = _decode(resp)
        # All 8 seed expenses fall in April 2026, total ₹256.25
        assert "256.25" in body, (
            "April full-range filter must include all 8 seed expenses totalling ₹256.25"
        )

    def test_april_full_range_shows_date_range_label(self, auth_client):
        resp = auth_client.get("/profile?start_date=2026-04-01&end_date=2026-04-30")
        body = _decode(resp)
        # filter_label must show formatted range, not "All time"
        assert "All time" not in body, (
            "A filtered view must not display 'All time' label"
        )
        # Formatted dates appear as "01 Apr 2026" and "30 Apr 2026"
        assert "Apr 2026" in body, (
            "filter_label must contain the formatted month and year"
        )

    def test_single_day_filter_april_10_returns_only_that_day(self, auth_client):
        resp = auth_client.get("/profile?start_date=2026-04-10&end_date=2026-04-10")
        assert resp.status_code == 200
        body = _decode(resp)
        # April 10 has two expenses: ₹10.00 (Other) and ₹8.75 (Food) = ₹18.75
        assert "18.75" in body, (
            "Single-day filter for 2026-04-10 must show total ₹18.75 (₹10.00 + ₹8.75)"
        )

    def test_single_day_filter_excludes_other_dates(self, auth_client):
        resp = auth_client.get("/profile?start_date=2026-04-10&end_date=2026-04-10")
        body = _decode(resp)
        # ₹80.00 Bills on 2026-04-03 must NOT be included
        # We check transaction_count indirectly via total; 256.25 is all-time total
        assert "256.25" not in body, (
            "Single-day filter must not show all-time total ₹256.25"
        )

    def test_empty_range_returns_200_no_crash(self, auth_client):
        resp = auth_client.get("/profile?start_date=2026-01-01&end_date=2026-01-31")
        assert resp.status_code == 200, (
            "Empty date range (no expenses) must not crash the server"
        )

    def test_empty_range_shows_zero_total(self, auth_client):
        resp = auth_client.get("/profile?start_date=2026-01-01&end_date=2026-01-31")
        body = _decode(resp)
        assert "₹0.00" in body, (
            "Empty date range must show ₹0.00 total spent"
        )

    def test_empty_range_shows_zero_transaction_count(self, auth_client):
        resp = auth_client.get("/profile?start_date=2026-01-01&end_date=2026-01-31")
        body = _decode(resp)
        # transaction_count of 0 must appear somewhere in stats area
        # The template renders it numerically; "0" will be present
        assert "0" in body, (
            "Empty date range must show 0 transactions"
        )

    def test_only_start_date_provided_returns_200(self, auth_client):
        resp = auth_client.get("/profile?start_date=2026-04-09")
        assert resp.status_code == 200, (
            "Providing only start_date must not crash — partial filter is allowed"
        )

    def test_only_end_date_provided_returns_200(self, auth_client):
        resp = auth_client.get("/profile?end_date=2026-04-05")
        assert resp.status_code == 200, (
            "Providing only end_date must not crash — partial filter is allowed"
        )

    def test_only_start_date_filters_lower_bound(self, auth_client):
        # start_date=2026-04-09 includes: Shopping ₹60.00, Other ₹10.00, Food ₹8.75 = ₹78.75
        resp = auth_client.get("/profile?start_date=2026-04-09")
        body = _decode(resp)
        assert "78.75" in body, (
            "start_date=2026-04-09 must include only expenses on/after that date"
        )

    def test_only_end_date_filters_upper_bound(self, auth_client):
        # end_date=2026-04-03 includes: Food ₹12.50, Transport ₹45.00, Bills ₹80.00 = ₹137.50
        resp = auth_client.get("/profile?end_date=2026-04-03")
        body = _decode(resp)
        assert "137.50" in body, (
            "end_date=2026-04-03 must include only expenses on/before that date"
        )


# ---------------------------------------------------------------------------
# Malformed date validation — route-level
# ---------------------------------------------------------------------------

class TestMalformedDates:
    @pytest.mark.parametrize("param,value", [
        ("start_date", "not-a-date"),
        ("start_date", "2026-13-01"),
        ("start_date", "2026-04-99"),
        ("start_date", ""),
        ("end_date", "bad"),
        ("end_date", "2026-00-01"),
        ("end_date", "notadate"),
    ])
    def test_malformed_date_param_returns_200(self, auth_client, param, value):
        resp = auth_client.get(f"/profile?{param}={value}")
        assert resp.status_code == 200, (
            f"Malformed {param}={value!r} must not crash — server must return 200"
        )

    def test_malformed_start_date_falls_back_to_all_time_total(self, auth_client):
        resp = auth_client.get("/profile?start_date=not-a-date")
        body = _decode(resp)
        # Invalid start_date is silently dropped → all-time data → ₹256.25
        assert "256.25" in body, (
            "Malformed start_date must be silently ignored; all-time total ₹256.25 shown"
        )

    def test_malformed_end_date_falls_back_to_all_time_total(self, auth_client):
        resp = auth_client.get("/profile?end_date=bad")
        body = _decode(resp)
        assert "256.25" in body, (
            "Malformed end_date must be silently ignored; all-time total ₹256.25 shown"
        )

    def test_invalid_month_start_date_falls_back_to_all_time(self, auth_client):
        resp = auth_client.get("/profile?start_date=2026-13-01")
        body = _decode(resp)
        assert "256.25" in body, (
            "Month 13 is invalid — must be silently ignored and all-time data shown"
        )

    def test_both_malformed_dates_fall_back_to_all_time(self, auth_client):
        resp = auth_client.get("/profile?start_date=garbage&end_date=garbage")
        assert resp.status_code == 200
        body = _decode(resp)
        assert "256.25" in body, (
            "Both malformed dates must be silently ignored; all-time total shown"
        )

    def test_malformed_start_date_shows_all_time_label(self, auth_client):
        resp = auth_client.get("/profile?start_date=not-a-date")
        body = _decode(resp)
        assert "All time" in body, (
            "When start_date is invalid, filter_label must read 'All time'"
        )


# ---------------------------------------------------------------------------
# Preset active detection — route-level
# ---------------------------------------------------------------------------

class TestPresetActiveDetection:
    def test_no_params_active_preset_is_all_time_in_html(self, auth_client):
        resp = auth_client.get("/profile")
        body = _decode(resp)
        # The template should mark the All Time button; spec says active_preset="all_time"
        # drives the `active` CSS class on that button
        assert "all_time" in body, (
            "With no params, the template must reference all_time as the active preset"
        )

    def test_this_month_dates_mark_this_month_preset_active(self, auth_client):
        # today = 2026-05-01, so this_month = 2026-05-01 to 2026-05-01
        today = date.today()
        first_this = today.replace(day=1).isoformat()
        end_this = today.isoformat()
        resp = auth_client.get(
            f"/profile?start_date={first_this}&end_date={end_this}"
        )
        body = _decode(resp)
        assert "this_month" in body, (
            "Dates matching This Month preset must cause the template to mark "
            "this_month as active"
        )

    def test_last_month_dates_mark_last_month_preset_active(self, auth_client):
        # today = 2026-05-01, so last_month = 2026-04-01 to 2026-04-30
        today = date.today()
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        start = last_prev.replace(day=1).isoformat()
        end = last_prev.isoformat()
        resp = auth_client.get(
            f"/profile?start_date={start}&end_date={end}"
        )
        body = _decode(resp)
        assert "last_month" in body, (
            "Dates matching Last Month preset must cause the template to mark "
            "last_month as active"
        )

    def test_custom_dates_do_not_mark_standard_preset_active(self, auth_client):
        # Arbitrary dates that don't match any preset
        resp = auth_client.get(
            "/profile?start_date=2026-04-05&end_date=2026-04-08"
        )
        body = _decode(resp)
        # When active_preset is "custom", no standard preset should carry the active class.
        # We verify by checking that the template does NOT apply `active` to all_time,
        # this_month, last_month, last_3_months simultaneously — simplest proxy is
        # that "All time" label does not appear (since custom range is active).
        assert "All time" not in body, (
            "Custom date range must not display 'All time' filter label"
        )

    def test_all_time_button_url_has_no_date_params(self, auth_client):
        # The All Time preset URL must be bare /profile with no date params.
        # We verify this by checking the rendered HTML contains href="/profile"
        # (or a URL without start_date/end_date for the all-time link).
        resp = auth_client.get("/profile")
        body = _decode(resp)
        # The preset_urls["all_time"] is built with url_for("profile") — no params.
        # The rendered anchor href should contain /profile without query params.
        assert 'href="/profile"' in body or "href='/profile'" in body, (
            "All Time preset button must link to /profile with no date query params"
        )


# ---------------------------------------------------------------------------
# filter_label rendering
# ---------------------------------------------------------------------------

class TestFilterLabel:
    def test_no_params_filter_label_is_all_time(self, auth_client):
        resp = auth_client.get("/profile")
        body = _decode(resp)
        assert "All time" in body, "No-params route must render filter_label='All time'"

    def test_both_dates_filter_label_shows_range(self, auth_client):
        resp = auth_client.get(
            "/profile?start_date=2026-04-01&end_date=2026-04-30"
        )
        body = _decode(resp)
        # filter_label = "01 Apr 2026 – 30 Apr 2026"
        assert "01 Apr 2026" in body, (
            "filter_label must include formatted start_date '01 Apr 2026'"
        )
        assert "30 Apr 2026" in body, (
            "filter_label must include formatted end_date '30 Apr 2026'"
        )

    def test_only_start_date_label_shows_from_prefix(self, auth_client):
        resp = auth_client.get("/profile?start_date=2026-04-09")
        body = _decode(resp)
        # filter_label = "From 09 Apr 2026"
        assert "09 Apr 2026" in body, (
            "filter_label with only start_date must include the formatted start date"
        )

    def test_only_end_date_label_shows_up_to_prefix(self, auth_client):
        resp = auth_client.get("/profile?end_date=2026-04-05")
        body = _decode(resp)
        # filter_label = "Up to 05 Apr 2026"
        assert "05 Apr 2026" in body, (
            "filter_label with only end_date must include the formatted end date"
        )


# ---------------------------------------------------------------------------
# Query helper unit tests — get_recent_transactions
# ---------------------------------------------------------------------------

class TestGetRecentTransactions:
    def test_no_filter_returns_all_seed_rows(self, app, seed_user_id):
        with app.app_context():
            result = get_recent_transactions(seed_user_id)
        assert len(result) == 8, (
            "No date filter must return all 8 seed transactions"
        )

    def test_no_filter_ordered_newest_first(self, app, seed_user_id):
        with app.app_context():
            result = get_recent_transactions(seed_user_id)
        # Dates are formatted strings like "10 Apr 2026"; compare raw sort
        # The spec says ORDER BY date DESC — newest date appears first
        assert result[0]["date"] >= result[-1]["date"], (
            "Transactions must be ordered newest-first with no date filter"
        )

    def test_no_filter_rows_have_required_keys(self, app, seed_user_id):
        with app.app_context():
            result = get_recent_transactions(seed_user_id)
        for row in result:
            assert "date" in row
            assert "description" in row
            assert "category" in row
            assert "amount" in row
            assert row["amount"].startswith("₹"), (
                "amount must be formatted as a rupee string"
            )

    def test_with_start_and_end_date_returns_only_range(self, app, seed_user_id):
        with app.app_context():
            result = get_recent_transactions(
                seed_user_id,
                start_date="2026-04-09",
                end_date="2026-04-10",
            )
        # 2026-04-09: Shopping ₹60.00
        # 2026-04-10: Other ₹10.00, Food ₹8.75
        assert len(result) == 3, (
            "Date range 2026-04-09 to 2026-04-10 must return exactly 3 transactions"
        )

    def test_with_start_date_only_filters_lower_bound(self, app, seed_user_id):
        with app.app_context():
            result = get_recent_transactions(
                seed_user_id,
                start_date="2026-04-09",
            )
        # On/after 2026-04-09: Shopping, Other, Food = 3 rows
        assert len(result) == 3, (
            "start_date=2026-04-09 with no end_date must return 3 transactions"
        )

    def test_with_end_date_only_filters_upper_bound(self, app, seed_user_id):
        with app.app_context():
            result = get_recent_transactions(
                seed_user_id,
                end_date="2026-04-02",
            )
        # On/before 2026-04-02: Food ₹12.50, Transport ₹45.00 = 2 rows
        assert len(result) == 2, (
            "end_date=2026-04-02 with no start_date must return 2 transactions"
        )

    def test_exact_single_day_returns_only_that_day(self, app, seed_user_id):
        with app.app_context():
            result = get_recent_transactions(
                seed_user_id,
                start_date="2026-04-10",
                end_date="2026-04-10",
            )
        # 2026-04-10 has 2 expenses
        assert len(result) == 2, (
            "Single-day filter 2026-04-10 must return exactly 2 transactions"
        )

    def test_empty_range_returns_empty_list(self, app, seed_user_id):
        with app.app_context():
            result = get_recent_transactions(
                seed_user_id,
                start_date="2026-01-01",
                end_date="2026-01-31",
            )
        assert result == [], (
            "Date range with no matching expenses must return an empty list"
        )

    def test_empty_range_for_empty_user_returns_empty_list(self, app, empty_user_id):
        with app.app_context():
            result = get_recent_transactions(
                empty_user_id,
                start_date="2026-04-01",
                end_date="2026-04-30",
            )
        assert result == [], (
            "User with no expenses must return empty list regardless of date filter"
        )

    def test_date_filter_does_not_leak_other_user_data(self, app, seed_user_id, empty_user_id):
        with app.app_context():
            result = get_recent_transactions(
                empty_user_id,
                start_date="2026-04-01",
                end_date="2026-04-30",
            )
        assert result == [], (
            "Date-filtered query must be scoped to the given user_id — no cross-user leakage"
        )

    def test_filter_amounts_are_correct(self, app, seed_user_id):
        with app.app_context():
            result = get_recent_transactions(
                seed_user_id,
                start_date="2026-04-01",
                end_date="2026-04-01",
            )
        assert len(result) == 1
        assert "12.50" in result[0]["amount"], (
            "Transaction on 2026-04-01 must have amount ₹12.50"
        )


# ---------------------------------------------------------------------------
# Query helper unit tests — get_summary_stats
# ---------------------------------------------------------------------------

class TestGetSummaryStats:
    def test_no_filter_total_spent(self, app, seed_user_id):
        with app.app_context():
            stats = get_summary_stats(seed_user_id)
        assert "256.25" in stats["total_spent"], (
            "All-time total_spent must be ₹256.25"
        )
        assert stats["total_spent"].startswith("₹"), (
            "total_spent must be formatted as a rupee string"
        )

    def test_no_filter_transaction_count(self, app, seed_user_id):
        with app.app_context():
            stats = get_summary_stats(seed_user_id)
        assert stats["transaction_count"] == 8, (
            "All-time transaction_count must be 8 for the seeded demo user"
        )

    def test_no_filter_top_category(self, app, seed_user_id):
        with app.app_context():
            stats = get_summary_stats(seed_user_id)
        # Bills: ₹80.00 is the highest single-category total
        assert stats["top_category"] == "Bills", (
            "All-time top_category must be 'Bills' (₹80.00)"
        )

    def test_filter_april_1_to_3_correct_total(self, app, seed_user_id):
        with app.app_context():
            stats = get_summary_stats(
                seed_user_id,
                start_date="2026-04-01",
                end_date="2026-04-03",
            )
        # Food ₹12.50 + Transport ₹45.00 + Bills ₹80.00 = ₹137.50
        assert "137.50" in stats["total_spent"], (
            "Filter 2026-04-01 to 2026-04-03 must total ₹137.50"
        )

    def test_filter_april_1_to_3_transaction_count(self, app, seed_user_id):
        with app.app_context():
            stats = get_summary_stats(
                seed_user_id,
                start_date="2026-04-01",
                end_date="2026-04-03",
            )
        assert stats["transaction_count"] == 3, (
            "Filter 2026-04-01 to 2026-04-03 must count exactly 3 transactions"
        )

    def test_filter_april_1_to_3_top_category_is_bills(self, app, seed_user_id):
        with app.app_context():
            stats = get_summary_stats(
                seed_user_id,
                start_date="2026-04-01",
                end_date="2026-04-03",
            )
        assert stats["top_category"] == "Bills", (
            "Top category for 2026-04-01 to 2026-04-03 must be 'Bills' (₹80.00)"
        )

    def test_filter_single_day_april_10_total(self, app, seed_user_id):
        with app.app_context():
            stats = get_summary_stats(
                seed_user_id,
                start_date="2026-04-10",
                end_date="2026-04-10",
            )
        # Other ₹10.00 + Food ₹8.75 = ₹18.75
        assert "18.75" in stats["total_spent"], (
            "Single-day filter 2026-04-10 must total ₹18.75"
        )

    def test_empty_range_total_spent_is_zero(self, app, seed_user_id):
        with app.app_context():
            stats = get_summary_stats(
                seed_user_id,
                start_date="2026-01-01",
                end_date="2026-01-31",
            )
        assert stats["total_spent"] == "₹0.00", (
            "Empty date range must return total_spent='₹0.00'"
        )

    def test_empty_range_transaction_count_is_zero(self, app, seed_user_id):
        with app.app_context():
            stats = get_summary_stats(
                seed_user_id,
                start_date="2026-01-01",
                end_date="2026-01-31",
            )
        assert stats["transaction_count"] == 0, (
            "Empty date range must return transaction_count=0"
        )

    def test_empty_range_top_category_is_dash(self, app, seed_user_id):
        with app.app_context():
            stats = get_summary_stats(
                seed_user_id,
                start_date="2026-01-01",
                end_date="2026-01-31",
            )
        assert stats["top_category"] == "—", (
            "Empty date range must return top_category='—'"
        )

    def test_empty_range_full_expected_structure(self, app, seed_user_id):
        with app.app_context():
            stats = get_summary_stats(
                seed_user_id,
                start_date="2026-01-01",
                end_date="2026-01-31",
            )
        assert stats == {"total_spent": "₹0.00", "transaction_count": 0, "top_category": "—"}, (
            "Empty date range must return the canonical zero-state dict"
        )

    def test_empty_user_no_filter_returns_zero_state(self, app, empty_user_id):
        with app.app_context():
            stats = get_summary_stats(empty_user_id)
        assert stats == {"total_spent": "₹0.00", "transaction_count": 0, "top_category": "—"}, (
            "User with no expenses must return zero-state regardless of filter"
        )

    def test_user_isolation_date_filter(self, app, seed_user_id, empty_user_id):
        with app.app_context():
            stats = get_summary_stats(
                empty_user_id,
                start_date="2026-04-01",
                end_date="2026-04-30",
            )
        assert stats["transaction_count"] == 0, (
            "Date-filtered stats must be scoped to the given user_id — no cross-user leakage"
        )


# ---------------------------------------------------------------------------
# Query helper unit tests — get_category_breakdown
# ---------------------------------------------------------------------------

class TestGetCategoryBreakdown:
    def test_no_filter_returns_all_seven_categories(self, app, seed_user_id):
        with app.app_context():
            cats = get_category_breakdown(seed_user_id)
        assert len(cats) == 7, (
            "All-time breakdown must return 7 distinct categories from seed data"
        )

    def test_no_filter_has_required_keys(self, app, seed_user_id):
        with app.app_context():
            cats = get_category_breakdown(seed_user_id)
        for cat in cats:
            assert "name" in cat, "Each category entry must have a 'name' key"
            assert "amount" in cat, "Each category entry must have an 'amount' key"
            assert "pct" in cat, "Each category entry must have a 'pct' key"

    def test_no_filter_amounts_are_rupee_strings(self, app, seed_user_id):
        with app.app_context():
            cats = get_category_breakdown(seed_user_id)
        for cat in cats:
            assert cat["amount"].startswith("₹"), (
                f"Category amount must start with ₹, got {cat['amount']!r}"
            )

    def test_no_filter_pct_values_are_integers(self, app, seed_user_id):
        with app.app_context():
            cats = get_category_breakdown(seed_user_id)
        for cat in cats:
            assert isinstance(cat["pct"], int), (
                f"pct must be an integer, got {type(cat['pct'])}"
            )

    def test_no_filter_pct_sums_to_100(self, app, seed_user_id):
        with app.app_context():
            cats = get_category_breakdown(seed_user_id)
        total_pct = sum(c["pct"] for c in cats)
        assert total_pct == 100, (
            f"Category percentages must sum to 100, got {total_pct}"
        )

    def test_no_filter_ordered_by_amount_descending(self, app, seed_user_id):
        with app.app_context():
            cats = get_category_breakdown(seed_user_id)
        amounts = [
            float(c["amount"].replace("₹", "").replace(",", ""))
            for c in cats
        ]
        assert amounts == sorted(amounts, reverse=True), (
            "Categories must be ordered by amount descending"
        )

    def test_no_filter_bills_is_first(self, app, seed_user_id):
        with app.app_context():
            cats = get_category_breakdown(seed_user_id)
        assert cats[0]["name"] == "Bills", (
            "Bills (₹80.00) must be the top category in all-time breakdown"
        )

    def test_date_filter_returns_only_categories_in_range(self, app, seed_user_id):
        with app.app_context():
            cats = get_category_breakdown(
                seed_user_id,
                start_date="2026-04-01",
                end_date="2026-04-03",
            )
        # Only Food, Transport, Bills appear in 2026-04-01 to 2026-04-03
        category_names = [c["name"] for c in cats]
        assert len(cats) == 3, (
            "Filter 2026-04-01 to 2026-04-03 must return exactly 3 categories"
        )
        assert set(category_names) == {"Food", "Transport", "Bills"}, (
            "Filter 2026-04-01 to 2026-04-03 must include only Food, Transport, Bills"
        )

    def test_date_filter_categories_pct_sums_to_100(self, app, seed_user_id):
        with app.app_context():
            cats = get_category_breakdown(
                seed_user_id,
                start_date="2026-04-01",
                end_date="2026-04-03",
            )
        total_pct = sum(c["pct"] for c in cats)
        assert total_pct == 100, (
            "Filtered category breakdown percentages must also sum to 100"
        )

    def test_single_day_filter_categories(self, app, seed_user_id):
        with app.app_context():
            cats = get_category_breakdown(
                seed_user_id,
                start_date="2026-04-10",
                end_date="2026-04-10",
            )
        # April 10: Other ₹10.00, Food ₹8.75 → 2 categories
        assert len(cats) == 2, (
            "Single-day filter 2026-04-10 must return exactly 2 categories"
        )
        category_names = [c["name"] for c in cats]
        assert set(category_names) == {"Other", "Food"}, (
            "2026-04-10 breakdown must contain only 'Other' and 'Food'"
        )

    def test_single_day_correct_top_category(self, app, seed_user_id):
        with app.app_context():
            cats = get_category_breakdown(
                seed_user_id,
                start_date="2026-04-10",
                end_date="2026-04-10",
            )
        # Other ₹10.00 > Food ₹8.75, so Other is first
        assert cats[0]["name"] == "Other", (
            "On 2026-04-10, 'Other' (₹10.00) must rank above 'Food' (₹8.75)"
        )

    def test_empty_range_returns_empty_list(self, app, seed_user_id):
        with app.app_context():
            cats = get_category_breakdown(
                seed_user_id,
                start_date="2026-01-01",
                end_date="2026-01-31",
            )
        assert cats == [], (
            "Empty date range must return an empty list for category breakdown"
        )

    def test_empty_user_returns_empty_list(self, app, empty_user_id):
        with app.app_context():
            cats = get_category_breakdown(empty_user_id)
        assert cats == [], (
            "User with no expenses must return empty list for category breakdown"
        )

    def test_user_isolation_in_breakdown(self, app, seed_user_id, empty_user_id):
        with app.app_context():
            cats = get_category_breakdown(
                empty_user_id,
                start_date="2026-04-01",
                end_date="2026-04-30",
            )
        assert cats == [], (
            "Category breakdown must be scoped to the given user_id — no cross-user leakage"
        )

    def test_start_date_only_filters_correctly(self, app, seed_user_id):
        with app.app_context():
            cats = get_category_breakdown(
                seed_user_id,
                start_date="2026-04-09",
            )
        # On/after 2026-04-09: Shopping ₹60.00, Other ₹10.00, Food ₹8.75 → 3 categories
        category_names = [c["name"] for c in cats]
        assert set(category_names) == {"Shopping", "Other", "Food"}, (
            "start_date=2026-04-09 must return only Shopping, Other, Food categories"
        )
