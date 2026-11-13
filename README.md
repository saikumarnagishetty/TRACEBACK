# TRACEBACK

A minimal college lost-and-found management web application built with Python, Flask, and SQLite.

## Features

- Student, faculty, and staff registration with mobile number and profile details
- Direct sign-in after registration; no email OTP or SMTP setup required
- Post lost and found item reports
- Browse, search, and filter reports
- Submit ownership claims with proof details
- Report owners can review and resolve claims
- Admin control centre: manage members, account access, reports, and ownership claims
- Admin can activate/deactivate accounts, grant/revoke administrator access, close/reopen reports, and review/delete content
- In-app notifications for new claims, claim decisions, and private messages
- Private claim chat restricted to the report owner and claimant
- Private Contact Admin help desk with support tickets, threaded replies, notifications, and admin resolution controls
- Existing database files are upgraded safely without deleting user data
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
