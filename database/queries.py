from datetime import datetime
from database.db import get_db


def _date_where(extra_conditions, params, start_date, end_date):
    conditions = list(extra_conditions)
    params = list(params)
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    return " AND ".join(conditions), params


# ===== TRANSACTION HISTORY =====

def get_recent_transactions(user_id, limit=10, start_date=None, end_date=None):
    where, params = _date_where(["user_id = ?"], [user_id], start_date, end_date)
    conn = get_db()
    try:
        rows = conn.execute(
            f"SELECT date, description, category, amount FROM expenses"
            f" WHERE {where} ORDER BY date DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    finally:
        conn.close()

    result = []
    for row in rows:
        formatted_date = datetime.strptime(row["date"], "%Y-%m-%d").strftime("%d %b %Y")
        description = row["description"] if row["description"] is not None else "—"
        result.append({
            "date": formatted_date,
            "description": description,
            "category": row["category"],
            "amount": f"₹{row['amount']:,.2f}",
        })
    return result


# ===== SUMMARY STATS =====

def get_summary_stats(user_id, start_date=None, end_date=None):
    where, params = _date_where(["user_id = ?"], [user_id], start_date, end_date)
    conn = get_db()
    try:
        total_spent = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE {where}",
            params,
        ).fetchone()[0]

        tx_count = conn.execute(
            f"SELECT COUNT(*) FROM expenses WHERE {where}",
            params,
        ).fetchone()[0]

        top_cat_row = conn.execute(
            f"SELECT category FROM expenses WHERE {where}"
            f" GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            params,
        ).fetchone()
    finally:
        conn.close()

    return {
        "total_spent": f"₹{total_spent:,.2f}",
        "transaction_count": tx_count,
        "top_category": top_cat_row[0] if top_cat_row else "—",
    }


# ===== CATEGORY BREAKDOWN =====

def get_category_breakdown(user_id, start_date=None, end_date=None):
    where, params = _date_where(["user_id = ?"], [user_id], start_date, end_date)
    conn = get_db()
    try:
        rows = conn.execute(
            f"SELECT category, SUM(amount) AS total FROM expenses"
            f" WHERE {where} GROUP BY category ORDER BY total DESC",
            params,
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    grand_total = sum(r["total"] for r in rows)
    raw_pcts = [r["total"] / grand_total * 100 for r in rows]
    int_pcts = [int(p) for p in raw_pcts]
    int_pcts[0] += 100 - sum(int_pcts)

    return [
        {
            "name": row["category"],
            "amount": f"₹{row['total']:,.2f}",
            "pct": int_pcts[i],
        }
        for i, row in enumerate(rows)
    ]
