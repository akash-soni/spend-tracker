from datetime import datetime
from database.db import get_db


# ===== TRANSACTION HISTORY — SA1 =====

def get_recent_transactions(user_id, limit=10):
    """Return the most recent `limit` transactions for the user, newest first.

    Each item: {"date": "DD Mon YYYY", "description": str, "category": str, "amount": "₹X,XXX.XX"}
    Returns an empty list when the user has no expenses.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses"
            " WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()

    result = []
    for row in rows:
        formatted_date = datetime.strptime(row["date"], "%Y-%m-%d").strftime("%d %b %Y")
        description = row["description"] if row["description"] is not None else "—"
        amount = f"₹{row['amount']:,.2f}"
        result.append({
            "date": formatted_date,
            "description": description,
            "category": row["category"],
            "amount": amount,
        })
    return result


# ===== SUMMARY STATS — SA2 =====

def get_summary_stats(user_id):
    """Return summary statistics for the user's expenses.

    Returns: {"total_spent": "₹X,XXX.XX", "transaction_count": int, "top_category": str}
    When the user has no expenses: {"total_spent": "₹0.00", "transaction_count": 0, "top_category": "—"}
    """
    conn = get_db()
    try:
        total_spent = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]

        tx_count = conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]

        top_cat_row = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ?"
            " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    top_category = top_cat_row[0] if top_cat_row else "—"
    return {
        "total_spent": f"₹{total_spent:,.2f}",
        "transaction_count": tx_count,
        "top_category": top_category,
    }


# ===== CATEGORY BREAKDOWN — SA3 =====

def get_category_breakdown(user_id):
    """Return per-category totals ordered by amount descending.

    Each item: {"name": str, "amount": "₹X,XXX.XX", "pct": int}
    pct values are integers that sum to exactly 100 (largest category absorbs rounding remainder).
    Returns an empty list when the user has no expenses.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses"
            " WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    grand_total = sum(r["total"] for r in rows)
    raw_pcts = [r["total"] / grand_total * 100 for r in rows]
    int_pcts = [int(p) for p in raw_pcts]
    remainder = 100 - sum(int_pcts)
    int_pcts[0] += remainder

    result = []
    for i, row in enumerate(rows):
        result.append({
            "name": row["category"],
            "amount": f"₹{row['total']:,.2f}",
            "pct": int_pcts[i],
        })
    return result
