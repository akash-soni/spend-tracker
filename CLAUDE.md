# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate virtual environment (Windows)
venv\Scripts\activate

# Activate virtual environment (Unix)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the development server (starts on localhost:5001)
python app.py

# Run tests
pytest

# Run a single test file
pytest tests/test_app.py

# Run a single test
pytest tests/test_app.py::test_name
```

## Architecture

This is a Flask-based expense tracking web app called **Spendly**, built as a step-by-step educational project. Features are added incrementally — many routes are stubs awaiting implementation.

**Stack:**
- Backend: Flask 3.1.3, SQLite (file: `expense_tracker.db`)
- Frontend: Jinja2 templates, vanilla CSS/JS (no frameworks)
- Fonts: DM Serif Display (headings), DM Sans (body) via Google Fonts

**Key files:**
- `app.py` — Flask app with all routes; placeholder routes are commented with their target step number
- `database/db.py` — SQLite helpers stub (`get_db`, `init_db`, `seed_db` to be implemented)
- `templates/base.html` — Base layout with nav and footer; all pages extend this
- `static/css/style.css` — Global design system with CSS custom properties
- `static/css/landing.css` — Landing page-specific styles
- `static/js/main.js` — Client-side JS stub

**Routes implemented:**
- `GET /` → landing page with hero section and YouTube modal
- `GET /register`, `GET /login` → auth forms (no backend handler yet)
- `GET /terms`, `GET /privacy` → static legal pages

**Routes stubbed (future steps):**
- `GET /logout` (Step 3), `GET /profile` (Step 4)
- `GET /expenses/add` (Step 7), `/expenses/<id>/edit` (Step 8), `/expenses/<id>/delete` (Step 9)

## Design System

CSS custom properties are defined in `:root` in `style.css`:
- `--ink-*` — dark text colors
- `--paper-*` — light background colors
- `--accent-*` — teal accent (`#0d9488`)
- `--accent2-*` — gold accent (`#c17f24`)
- `--danger-*` — red for destructive actions

Max content width is `1200px`. Border radii: `--radius-sm` (6px), `--radius-md` (12px), `--radius-lg` (20px).
