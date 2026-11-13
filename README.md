# TRACEBACK

A college lost-and-found management web application built with Python, Flask, and SQLAlchemy. It supports SQLite for local development and PostgreSQL for production.

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
- SQLite or PostgreSQL database initialized automatically based on DATABASE_URL
- Safe CLI command to migrate existing SQLite records into an empty PostgreSQL database

## Database configuration

- If `DATABASE_URL` is not set, the app uses `instance/traceback.db` (SQLite).
- To switch to PostgreSQL, set `DATABASE_URL` in your local `.env` file to your PostgreSQL connection string. The app loads `.env` automatically.
- For production, set `DATABASE_URL` and `SECRET_KEY` as private environment variables in the hosting dashboard.

### Migrate existing SQLite data to PostgreSQL

1. Back up `instance/traceback.db` before starting.
2. Set `DATABASE_URL` to your new, empty PostgreSQL database.
3. Install the updated requirements and run:

```bash
flask --app app migrate-sqlite-to-postgres
```

The command copies all database tables and rows, preserves IDs, adjusts PostgreSQL ID sequences, and refuses to run if the target database already contains rows. It does not delete or modify the original SQLite file. Copy the separate `uploads/` folder as well if you need existing report photos.

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


## Zero-cost hosting preparation (Render + Neon)

The repository includes a Render Blueprint (render.yaml) for a free Python web service. The app uses Gunicorn in production and exposes /healthz for health checks.

### Deploy

1. Create a free account at https://render.com and connect this GitHub repository.
2. In Render, choose **New → Blueprint** and select this repository. Review the service and deploy it on the Free plan.
3. Create a free PostgreSQL database at https://neon.com.
4. In the Render service's **Environment** settings, add:
   - DATABASE_URL: the Neon connection string (Render app converts PostgreSQL URLs to the psycopg 3 driver format).
   - SECRET_KEY: a long, random secret generated privately; never commit it to GitHub or share it in chat.
5. If you need to preserve your existing local SQLite data, run the migration command from a trusted machine with the same Neon `DATABASE_URL` configured before opening the live site. Back up the SQLite file first; the migration requires an empty PostgreSQL database.
6. Redeploy, then open the Render-provided *.onrender.com URL and test registration, login, reports, claims, admin, support chat, and notifications.

### Important free-tier limitations

- Render's free web service can sleep after inactivity and its local filesystem is ephemeral.
- Do not rely on the app's local SQLite database or uploads/ folder on Render. Use Neon PostgreSQL for database persistence and configure durable object storage for user-uploaded report images before real campus use.
- The campus background video and logo are static repository assets, so they are deployed with the code.
- A genuine root domain such as traceback.com or traceback.in normally requires purchasing/renewing a domain. Render's free onrender.com hostname is the dependable no-cost launch URL. A free third-party subdomain may be possible, but its availability and provider approval are not guaranteed.
- Render's free Postgres offering is temporary; use an external managed free-tier PostgreSQL provider such as Neon and review its current limits.

The initial deployment does not create a database or set secrets automatically. Complete the dashboard environment setup above before opening the site to users.
