# Spec: Date Filter for Profile Page

## Overview
Step 06 adds a date-range filter to the profile page so users can slice their
spending data by time period. Currently the profile page always shows all-time
aggregates regardless of when the expenses occurred. This step introduces a
filter bar with four quick-select presets (This Month, Last Month, Last 3
Months, All Time) and an optional custom date-range picker. Selecting a filter
re-renders the same `/profile` route with `start_date` and `end_date` query
parameters; the three query helpers are updated to respect these bounds.
The summary stats, transaction list, and category breakdown all reflect the
active filter simultaneously.

## Depends on
- Step 1: Database setup (`expenses` table with `date TEXT` column exists)
- Step 2: Registration (users stored in DB)
- Step 3: Login / Logout (`session["user_id"]` set on login)
- Step 4: Profile page UI (template structure already in place)
- Step 5: Backend connection (query helpers in `database/queries.py` live)

## Routes
No new routes. The existing `GET /profile` route is modified to accept optional
query parameters:
- `start_date` — ISO date string `YYYY-MM-DD` (inclusive lower bound)
- `end_date` — ISO date string `YYYY-MM-DD` (inclusive upper bound)

When neither is supplied the route behaves exactly as today (all-time view).

## Database changes
No database changes. The `expenses.date` column (`TEXT NOT NULL`, stored as
`YYYY-MM-DD`) already supports range queries with `>=` / `<=` comparisons
in SQLite.

## Templates
- **Modify**: `templates/profile.html`
  - Add a filter bar above the summary stats with four preset buttons:
    `This Month`, `Last Month`, `Last 3 Months`, `All Time`
  - Add a collapsible custom date-range form with two `<input type="date">`
    fields (`start_date`, `end_date`) and an `Apply` button
  - Highlight the active preset (add `active` CSS class to the matching button)
  - Show the active date range as a human-readable label beneath the filter bar
    (e.g. "Showing: 1 Apr 2026 – 30 Apr 2026" or "Showing: All time")
  - All three data sections (stats, transactions, categories) already use Jinja
    variables — no structural changes needed there

## Files to change
- `app.py`
  - Read `start_date` and `end_date` from `request.args`
  - Validate that both are valid ISO dates when provided; ignore malformed values
  - Pass `start_date`, `end_date` to all three query helpers
  - Pass the active filter context (`active_preset`, `start_date`, `end_date`)
    to the template so the filter bar can render correctly
- `database/queries.py`
  - `get_recent_transactions(user_id, limit=10, start_date=None, end_date=None)`
    — add optional date bounds to the `WHERE` clause
  - `get_summary_stats(user_id, start_date=None, end_date=None)`
    — add optional date bounds to all three sub-queries
  - `get_category_breakdown(user_id, start_date=None, end_date=None)`
    — add optional date bounds to the aggregate query
- `templates/profile.html`
  — filter bar UI (see Templates section above)
- `static/css/profile.css`
  — styles for `.filter-bar`, `.filter-presets`, `.filter-btn`, `.filter-btn.active`,
  `.filter-custom`, `.filter-label`; use CSS variables only

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- `start_date` / `end_date` are appended to WHERE clauses with `AND date >= ?`
  and `AND date <= ?` only when the values are not `None`
- Date validation in `app.py` must use `datetime.strptime(value, "%Y-%m-%d")`
  in a try/except; silently drop invalid values (treat as if not supplied)
- Preset date arithmetic must use Python's `datetime` / `date` from the stdlib;
  no third-party date libraries
- "This Month" = first day of the current calendar month to today
- "Last Month" = first day to last day of the previous calendar month
- "Last 3 Months" = first day of the month three months ago to today
- "All Time" = no bounds (both params omitted from the redirect URL)
- Preset buttons submit via `<a href="...">` links (GET, no JS required)
- Custom date-range form must use `method="GET"` and `action="{{ url_for('profile') }}"`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles (the existing `style="width: {{ cat.pct }}%"` on the
  category bar is an intentional dynamic value and is acceptable to keep)
- Passwords are not touched in this step

## Definition of done
- [ ] Visiting `/profile` with no query params shows all-time data (same as
  before this step) and the "All Time" preset button is highlighted
- [ ] Clicking "This Month" redirects to `/profile?start_date=YYYY-MM-01&end_date=YYYY-MM-DD`
  and the stats / transactions / categories reflect only expenses in the current month
- [ ] Clicking "Last Month" shows only expenses from the previous calendar month
- [ ] Clicking "Last 3 Months" shows expenses from the last three months
- [ ] Clicking "All Time" removes date params from the URL and shows all expenses
- [ ] The active preset button has a visually distinct style (`.active` class)
- [ ] The filter label beneath the bar shows the human-readable date range
- [ ] Entering a valid custom start and end date via the custom form and pressing
  Apply filters the page correctly
- [ ] Entering a malformed date in the custom form does not crash the server —
  the filter is silently ignored and all-time data is shown
- [ ] A user with no expenses in the filtered range sees ₹0.00 total, 0
  transactions, and an empty category breakdown — no errors or exceptions
- [ ] Existing all-time behaviour is unchanged when no filter is active
