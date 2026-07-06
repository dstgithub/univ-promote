# Promote Demo

A simple Flask-based promotion case management demo. Users can log in as faculty, reviewer, or admin to submit promotion cases, review cases, manage users, and export reports.

## Features

- Login system with roles: `faculty`, `reviewer`, and `admin`
- Faculty users can submit promotion cases with optional CV file upload
- Reviewers and admins can view, filter, and review cases
- Admin users can add and edit users
- Dashboard with summary statistics and recent cases
- Export case data as CSV or PDF
- Stores data in a local SQLite database (`promote.db`)

## Default users

The app initializes sample users automatically on first run:

- `alice` / `password` — role: `faculty`
- `bob` / `password` — role: `reviewer`
- `admin` / `password` — role: `admin`

## Requirements

- Python 3.11+ (recommended)
- Dependencies listed in `requirements.txt`

## Installation

1. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the app

Start the Flask application:

```bash
python app.py
```

Open the app in your browser:

```text
http://127.0.0.1:5000
```

## Project structure

- `app.py` — main Flask application
- `requirements.txt` — Python dependencies
- `templates/` — HTML templates for pages
- `static/` — CSS and static assets
- `uploads/` — uploaded CV files (created automatically)

## Notes

- The app uses a hard-coded secret key in `app.py`; replace `app.secret_key` with a secure value for production.
- Passwords are stored in plain text in SQLite for demonstration only; use hashed passwords in real apps.
- The SQLite database file `promote.db` is created automatically when the app is first run.
