# Spec: Registration

## Overview
Implement the user registration flow so new visitors can create a Spendly account.
This step wires up the `POST /register` handler in `app.py`, validates the submitted
form data, inserts a hashed-password record into the `users` table, and redirects the
new user to the login page with a success flash message. The `GET /register` route and
`register.html` template already exist; only the backend logic and minor template
adjustments are needed.

## Depends on
- Step 01 — Database Setup (users table must exist; `get_db` must be working)

## Routes
- `GET /register` — render registration form — public *(already exists, no change)*
- `POST /register` — validate form, insert user, redirect to login — public *(new)*

## Database changes
No database changes. The `users` table (id, name, email, password_hash, created_at)
was created in Step 01 and is sufficient for this feature.

## Templates
- **Modify:** `templates/register.html`
  - Already renders `{{ error }}` inside `.auth-error` — no structural changes needed
  - Add `{{ success }}` block above the form (or rely on redirect + login flash) — keep
    consistent with the existing `{% if error %}` pattern for any inline error display

## Files to change
- `app.py`
  - Add `request`, `redirect`, `url_for`, `session`, `flash` to Flask imports
  - Set `app.secret_key` (use `os.urandom(24)` or a fixed dev string — document it)
  - Convert existing `GET`-only `/register` route to accept `["GET", "POST"]`
  - Implement POST handler logic (see Rules section)

## Files to create
No new files.

## New dependencies
No new dependencies. `werkzeug.security` is already installed.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never use string formatting in SQL
- Hash passwords with `werkzeug.security.generate_password_hash` before inserting
- Use CSS variables — never hardcode hex values in any template or style
- All templates extend `base.html`
- Validation order (fail fast, show first error):
  1. All three fields (name, email, password) must be non-empty
  2. Password must be at least 8 characters
  3. Email must not already exist in `users` (catch `sqlite3.IntegrityError` **or**
     do an explicit `SELECT` before insert — explicit SELECT is preferred for clarity)
- On validation failure: re-render `register.html` passing `error=<message>` and
  repopulate `name` and `email` values so the user does not have to retype them
- On success: redirect to `url_for('login')` — do not auto-login the user (that is
  Step 3)
- `app.secret_key` must be set before any `session` or `flash` usage; set it once
  near the top of `app.py` after `app = Flask(__name__)`

## Definition of done
- [ ] `GET /register` still renders the form without errors
- [ ] Submitting the form with all fields empty shows a validation error on the page
- [ ] Submitting with a password shorter than 8 characters shows a validation error
- [ ] Submitting a duplicate email shows "Email already registered" error
- [ ] Name and email fields are repopulated after a failed submission
- [ ] Submitting valid new data inserts a row in `users` with a hashed (not plaintext) password
- [ ] After successful registration, browser is redirected to `/login`
- [ ] The new user can be found in the database (`SELECT * FROM users`)
- [ ] App starts without errors (`python app.py`)
- [ ] No raw SQL string formatting anywhere in the new code
