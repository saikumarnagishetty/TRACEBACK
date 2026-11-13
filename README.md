# TRACEBACK

A minimal college lost-and-found management web application built with Python, Flask, and SQLite.

The repository was inspected before implementation. It was empty (no files, commits, or branches), so this is a clean initial implementation.

## Features

- Student registration and login
- Post lost and found item reports
- Browse, search, and filter reports
- Submit ownership claims with proof details
- Report owners can review and resolve claims
- Admin control centre: manage members, account access, reports, and ownership claims
- Admin can activate/deactivate accounts, grant/revoke administrator access, close/reopen reports, and review/delete content
- Existing database files are upgraded safely with the account-active field
- SQLite database initialized automatically

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000.

Set `SECRET_KEY` to a long random value in production. Public registration never grants administrator privileges. Create the first administrator from the project directory with:

```bash
flask --app app create-admin
```

Enter the administrator email when prompted. If the account already exists, confirm that you want to promote it; otherwise, enter a name and a new password. Run this command only on a trusted machine with access to the application database. Existing administrator accounts remain administrators.

## Notes

This is an educational starter application. Use HTTPS, a production WSGI server, backups, and a managed database before deploying for a real campus.