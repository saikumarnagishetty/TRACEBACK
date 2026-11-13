import os
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
import click
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager, UserMixin, current_user, login_required, login_user, logout_user
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import or_, inspect, text
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from wtforms import (
    BooleanField, PasswordField, SelectField, StringField, SubmitField,
    TextAreaField
)
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, Regexp

BASE_DIR = Path(__file__).resolve().parent
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
CATEGORIES = [
    "Electronics", "ID cards & documents", "Bags", "Books & stationery",
    "Clothing", "Keys", "Accessories", "Other"
]

app = Flask(__name__, instance_relative_config=True)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-this-secret"),
    SQLALCHEMY_DATABASE_URI=os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'traceback.db'}"
    ).replace("postgres://", "postgresql://", 1),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=4 * 1024 * 1024,
    UPLOAD_FOLDER=str(BASE_DIR / "uploads"),
)
Path(app.instance_path).mkdir(parents=True, exist_ok=True)
Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"
csrf = CSRFProtect(app)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    email_verified = db.Column(db.Boolean, default=True, nullable=False)
    verification_code_hash = db.Column(db.String(255))
    verification_expires_at = db.Column(db.DateTime)
    mobile_number = db.Column(db.String(20), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="student")
    enrollment_number = db.Column(db.String(40))
    semester = db.Column(db.String(20))
    course = db.Column(db.String(100))
    subject = db.Column(db.String(100))
    designation = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    items = db.relationship("Item", backref="author", lazy=True)
    claims = db.relationship("Claim", backref="claimant", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)



class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    message = db.Column(db.String(240), nullable=False)
    link = db.Column(db.String(240), nullable=False, default="/dashboard")
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class DirectMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claim.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.String(2000), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def add_notification(user_id, message, link):
    db.session.add(Notification(user_id=user_id, message=message, link=link))


def send_verification_email(user, code):
    host = os.environ.get("MAIL_SERVER")
    sender = os.environ.get("MAIL_DEFAULT_SENDER") or os.environ.get("MAIL_USERNAME")
    if not host or not sender:
        raise RuntimeError("Email delivery is not configured.")
    msg = EmailMessage()
    msg["Subject"] = "Verify your TRACEBACK account"
    msg["From"] = sender
    msg["To"] = user.email
    msg.set_content(f"Hello {user.name},\n\nYour TRACEBACK verification code is {code}. It expires in 10 minutes. Ignore this email if you did not register.")
    port = int(os.environ.get("MAIL_PORT", "587"))
    username, password = os.environ.get("MAIL_USERNAME"), os.environ.get("MAIL_PASSWORD")
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=20) as smtp:
            if username and password: smtp.login(username, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls()
            if username and password: smtp.login(username, password)
            smtp.send_message(msg)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    report_type = db.Column(db.String(10), nullable=False)  # lost / found
    status = db.Column(db.String(12), default="open", nullable=False)
    image_filename = db.Column(db.String(180))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    claims = db.relationship("Claim", backref="item", cascade="all, delete-orphan", lazy=True)


class Claim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(12), default="pending", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class RegisterForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=80)])
    email = StringField("Email address", validators=[DataRequired(), Email(), Length(max=120)])
    mobile_number = StringField("Mobile number", validators=[DataRequired(), Regexp(r"^\+?[0-9]{10,15}$", message="Enter a valid mobile number with 10–15 digits (country code optional).")])
    role = SelectField("I am a", choices=[("student", "Student"), ("faculty", "Faculty"), ("staff", "Non-teaching staff")], validators=[DataRequired()])
    enrollment_number = StringField("Enrollment number", validators=[Optional(), Length(max=40)])
    semester = SelectField("Semester", choices=[("", "Select semester")] + [(str(i), f"Semester {i}") for i in range(1, 13)], validators=[Optional()])
    course = StringField("Course / programme", validators=[Optional(), Length(max=100)])
    subject = StringField("Subject / department", validators=[Optional(), Length(max=100)])
    designation = StringField("Designation", validators=[Optional(), Length(max=100)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")


class ItemForm(FlaskForm):
    report_type = SelectField("Report type", choices=[("lost", "I lost something"), ("found", "I found something")])
    title = StringField("Item name", validators=[DataRequired(), Length(min=3, max=100)])
    category = SelectField("Category", choices=[(c, c) for c in CATEGORIES])
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=10, max=1500)])
    location = StringField("Campus location", validators=[DataRequired(), Length(max=120)])
    event_date = StringField("Date", validators=[DataRequired()])
    submit = SubmitField("Publish report")


class ClaimForm(FlaskForm):
    message = TextAreaField(
        "How can you verify this is yours?",
        validators=[DataRequired(), Length(min=10, max=1000)]
    )
    submit = SubmitField("Submit claim")


@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(User, int(user_id))
    return user if user and user.is_active else None


@app.context_processor
def inject_globals():
    unread_notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).count() if current_user.is_authenticated else 0
    return {"categories": CATEGORIES, "unread_notifications": unread_notifications}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    report_type = request.args.get("type", "")
    items_query = Item.query.filter_by(status="open")
    if query:
        pattern = f"%{query}%"
        items_query = items_query.filter(or_(
            Item.title.ilike(pattern), Item.description.ilike(pattern),
            Item.location.ilike(pattern)
        ))
    if category in CATEGORIES:
        items_query = items_query.filter_by(category=category)
    if report_type in {"lost", "found"}:
        items_query = items_query.filter_by(report_type=report_type)
    items = items_query.order_by(Item.created_at.desc()).all()
    return render_template("index.html", items=items, q=query, selected_category=category, selected_type=report_type)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            role = form.role.data
            role_errors = []
            if role == "student":
                if not form.enrollment_number.data or not form.enrollment_number.data.strip(): role_errors.append("Enrollment number is required for students.")
                if not form.semester.data: role_errors.append("Please select your semester.")
                if not form.course.data or not form.course.data.strip(): role_errors.append("Course is required for students.")
            elif role == "faculty":
                if not form.subject.data or not form.subject.data.strip(): role_errors.append("Subject / department is required for faculty.")
            elif role == "staff":
                if not form.designation.data or not form.designation.data.strip(): role_errors.append("Designation is required for non-teaching staff.")
            if role_errors:
                for error in role_errors: flash(error, "error")
                return render_template("auth.html", form=form, mode="register")
            user = User(
                name=form.name.data.strip(), email=email, mobile_number=form.mobile_number.data.strip(), role=role,
                enrollment_number=(form.enrollment_number.data or "").strip() or None if role == "student" else None,
                semester=form.semester.data if role == "student" else None,
                course=(form.course.data or "").strip() or None if role == "student" else None,
                subject=(form.subject.data or "").strip() or None if role == "faculty" else None,
                designation=(form.designation.data or "").strip() or None if role == "staff" else None,
                is_admin=False, email_verified=False
            )
            user.set_password(form.password.data)
            code = f"{secrets.randbelow(1000000):06d}"
            user.verification_code_hash = generate_password_hash(code)
            user.verification_expires_at = datetime.utcnow() + timedelta(minutes=10)
            db.session.add(user)
            db.session.commit()
            try:
                send_verification_email(user, code)
                flash("A 6-digit verification code was sent to your email.", "success")
            except Exception:
                app.logger.exception("Email delivery failed")
                flash("Account created, but email delivery failed. Configure SMTP and resend the code.", "error")
            return redirect(url_for("verify_email", user_id=user.id))
    return render_template("auth.html", form=form, mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.is_active and user.check_password(form.password.data):
            if not user.email_verified:
                flash("Please verify your email before signing in.", "error")
                return redirect(url_for("verify_email", user_id=user.id))
            login_user(user)
            flash("You are signed in.", "success")
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("index"))
        flash("Incorrect email or password.", "error")
    return render_template("auth.html", form=form, mode="login")



@app.route("/verify-email/<int:user_id>", methods=["GET", "POST"])
def verify_email(user_id):
    user = db.get_or_404(User, user_id)
    if user.email_verified:
        flash("Email already verified. Please sign in.", "info")
        return redirect(url_for("login"))
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if user.verification_code_hash and user.verification_expires_at and user.verification_expires_at >= datetime.utcnow() and check_password_hash(user.verification_code_hash, code):
            user.email_verified = True
            user.verification_code_hash = None
            user.verification_expires_at = None
            db.session.commit()
            login_user(user)
            flash("Email verified. Welcome to TRACEBACK!", "success")
            return redirect(url_for("index"))
        flash("Invalid or expired code. Request a new one.", "error")
    return render_template("verify_email.html", user=user)


@app.post("/verify-email/<int:user_id>/resend")
def resend_verification(user_id):
    user = db.get_or_404(User, user_id)
    if user.email_verified: return redirect(url_for("login"))
    code = f"{secrets.randbelow(1000000):06d}"
    user.verification_code_hash = generate_password_hash(code)
    user.verification_expires_at = datetime.utcnow() + timedelta(minutes=10)
    db.session.commit()
    try:
        send_verification_email(user, code)
        flash("A new verification code was sent.", "success")
    except Exception:
        app.logger.exception("Email resend failed")
        flash("Email delivery is not configured yet.", "error")
    return redirect(url_for("verify_email", user_id=user.id))


@app.route("/notifications")
@login_required
def notifications():
    entries = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(100).all()
    return render_template("notifications.html", notifications=entries)


@app.post("/notifications/<int:notification_id>/read")
@login_required
def mark_notification_read(notification_id):
    note = db.get_or_404(Notification, notification_id)
    if note.user_id != current_user.id: abort(403)
    note.is_read = True
    db.session.commit()
    return redirect(note.link if note.link.startswith("/") and not note.link.startswith("//") else url_for("notifications"))


@app.post("/notifications/read-all")
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return redirect(url_for("notifications"))


@app.route("/chat/<int:claim_id>", methods=["GET", "POST"])
@login_required
def chat(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    if current_user.id not in {claim.user_id, claim.item.user_id}: abort(403)
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if not body or len(body) > 2000:
            flash("Message must contain 1–2000 characters.", "error")
        else:
            db.session.add(DirectMessage(claim_id=claim.id, sender_id=current_user.id, body=body))
            recipient = claim.item.user_id if current_user.id == claim.user_id else claim.user_id
            add_notification(recipient, f"New private message about {claim.item.title}.", url_for("chat", claim_id=claim.id))
            db.session.commit()
            return redirect(url_for("chat", claim_id=claim.id))
    messages = DirectMessage.query.filter_by(claim_id=claim.id).order_by(DirectMessage.created_at.asc()).all()
    other_user = db.session.get(User, claim.item.user_id if current_user.id == claim.user_id else claim.user_id)
    return render_template("chat.html", claim=claim, messages=messages, other_user=other_user)


@app.post("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


@app.route("/report/new", methods=["GET", "POST"])
@login_required
def new_item():
    form = ItemForm()
    if form.validate_on_submit():
        try:
            event_date = datetime.strptime(form.event_date.data, "%Y-%m-%d").date()
        except ValueError:
            flash("Please enter a valid date.", "error")
            return render_template("item_form.html", form=form)
        image_filename = None
        image = request.files.get("image")
        if image and image.filename:
            if not allowed_file(image.filename):
                flash("Use a PNG, JPG, JPEG, or WEBP image.", "error")
                return render_template("item_form.html", form=form)
            image_filename = f"{current_user.id}_{int(datetime.utcnow().timestamp())}_{secure_filename(image.filename)}"
            image.save(Path(app.config["UPLOAD_FOLDER"]) / image_filename)
        item = Item(
            title=form.title.data.strip(), description=form.description.data.strip(),
            category=form.category.data, location=form.location.data.strip(),
            event_date=event_date, report_type=form.report_type.data,
            image_filename=image_filename, author=current_user
        )
        db.session.add(item)
        db.session.commit()
        flash("Your report has been published.", "success")
        return redirect(url_for("item_detail", item_id=item.id))
    return render_template("item_form.html", form=form)


@app.route("/item/<int:item_id>")
def item_detail(item_id):
    item = db.get_or_404(Item, item_id)
    form = ClaimForm()
    return render_template("item_detail.html", item=item, form=form)


@app.post("/item/<int:item_id>/claim")
@login_required
def create_claim(item_id):
    item = db.get_or_404(Item, item_id)
    form = ClaimForm()
    if item.user_id == current_user.id:
        flash("You cannot claim your own report.", "error")
    elif item.status != "open":
        flash("This report is no longer open for claims.", "error")
    elif form.validate_on_submit():
        existing = Claim.query.filter_by(item_id=item.id, user_id=current_user.id, status="pending").first()
        if existing:
            flash("You already have a pending claim for this report.", "info")
        else:
            claim = Claim(message=form.message.data.strip(), item=item, claimant=current_user)
            db.session.add(claim)
            db.session.flush()
            add_notification(item.user_id, f"New ownership claim for {item.title}.", url_for("item_detail", item_id=item.id))
            db.session.commit()
            flash("Claim sent to the report owner for review.", "success")
    else:
        flash("Please provide at least 10 characters explaining your proof.", "error")
    return redirect(url_for("item_detail", item_id=item.id))


@app.post("/claim/<int:claim_id>/review")
@login_required
def review_claim(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    if claim.item.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    decision = request.form.get("decision")
    if decision not in {"approved", "rejected"}:
        abort(400)
    claim.status = decision
    if decision == "approved":
        claim.item.status = "resolved"
        for other in claim.item.claims:
            if other.id != claim.id and other.status == "pending":
                other.status = "rejected"
    add_notification(claim.user_id, f"Your claim for {claim.item.title} was {decision}.", url_for("item_detail", item_id=claim.item_id))
    db.session.commit()
    flash(f"Claim {decision}.", "success")
    return redirect(url_for("item_detail", item_id=claim.item_id))


@app.route("/dashboard")
@login_required
def dashboard():
    my_items = Item.query.filter_by(user_id=current_user.id).order_by(Item.created_at.desc()).all()
    claims_received = Claim.query.join(Item).filter(Item.user_id == current_user.id).order_by(Claim.created_at.desc()).all()
    my_claims = Claim.query.filter_by(user_id=current_user.id).order_by(Claim.created_at.desc()).all()
    return render_template("dashboard.html", my_items=my_items, claims_received=claims_received, my_claims=my_claims)


@app.cli.command("create-admin")
@click.option("--email", prompt=True, help="Email address for the administrator account.")
def create_admin_command(email):
    """Create an administrator or promote an existing local account."""
    email = email.strip().lower()
    if not email:
        raise click.ClickException("Email address is required.")

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user:
            if user.is_admin:
                click.echo(f"{email} is already an administrator.")
                return
            if not click.confirm(f"Promote the existing account {email} to administrator?", default=False):
                click.echo("No changes made.")
                return
            user.is_admin = True
        else:
            name = click.prompt("Administrator full name")
            password = click.prompt("New administrator password", hide_input=True, confirmation_prompt=True)
            if len(password) < 8:
                raise click.ClickException("Password must contain at least 8 characters.")
            user = User(name=name.strip(), email=email, role="staff",
                        designation="Administrator", is_admin=True)
            user.set_password(password)
            db.session.add(user)

        db.session.commit()
        click.echo(f"Administrator access enabled for {email}.")


@app.cli.command("reset-admin-password")
@click.option("--email", prompt=True, help="Email address of the existing administrator account.")
def reset_admin_password_command(email):
    """Reset the password for an existing administrator account."""
    email = email.strip().lower()
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            raise click.ClickException("No account exists for that email. Create the account first.")
        if not user.is_admin:
            if not click.confirm(f"{email} is not an admin. Promote this account and reset its password?", default=False):
                click.echo("No changes made.")
                return
            user.is_admin = True
        password = click.prompt("New administrator password", hide_input=True, confirmation_prompt=True)
        if len(password) < 8:
            raise click.ClickException("Password must contain at least 8 characters.")
        user.set_password(password)
        db.session.commit()
        click.echo(f"Administrator password updated for {email}.")


@app.route("/admin")
@login_required
def admin():
    if not current_user.is_admin:
        abort(403)
    return render_template(
        "admin.html",
        users=User.query.order_by(User.created_at.desc()).all(),
        items=Item.query.order_by(Item.created_at.desc()).all(),
        claims=Claim.query.order_by(Claim.created_at.desc()).all(),
        pending=Claim.query.filter_by(status="pending").count(),
        active_users=User.query.filter_by(is_active=True).count(),
        inactive_users=User.query.filter_by(is_active=False).count(),
        open_items=Item.query.filter_by(status="open").count(),
        resolved_items=Item.query.filter_by(status="resolved").count()
    )


def require_admin():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


@app.post("/admin/user/<int:user_id>/toggle-active")
@login_required
def admin_toggle_user(user_id):
    require_admin()
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id and user.is_active:
        flash("You cannot deactivate your own account.", "error")
    else:
        user.is_active = not user.is_active
        db.session.commit()
        flash("Account " + ("activated" if user.is_active else "deactivated") + ".", "success")
    return redirect(url_for("admin") + "#members")


@app.post("/admin/user/<int:user_id>/toggle-admin")
@login_required
def admin_toggle_admin(user_id):
    require_admin()
    user = db.get_or_404(User, user_id)
    if user.is_admin and User.query.filter_by(is_admin=True).count() <= 1:
        flash("The last administrator cannot be removed.", "error")
    elif user.id == current_user.id and user.is_admin:
        flash("You cannot remove your own administrator access.", "error")
    else:
        user.is_admin = not user.is_admin
        db.session.commit()
        flash("Administrator access " + ("granted" if user.is_admin else "revoked") + ".", "success")
    return redirect(url_for("admin") + "#members")


@app.post("/admin/user/<int:user_id>/delete")
@login_required
def admin_delete_user(user_id):
    require_admin()
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot delete your own account while signed in.", "error")
    elif user.is_admin and User.query.filter_by(is_admin=True).count() <= 1:
        flash("The last administrator cannot be deleted.", "error")
    else:
        owned_items = Item.query.filter_by(user_id=user.id).all()
        for item in owned_items:
            Claim.query.filter_by(item_id=item.id).delete(synchronize_session=False)
            db.session.delete(item)
        Claim.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        db.session.delete(user)
        db.session.commit()
        flash("Member and their reports/claims were deleted.", "success")
    return redirect(url_for("admin") + "#members")


@app.post("/admin/item/<int:item_id>/status")
@login_required
def admin_set_item_status(item_id):
    require_admin()
    item = db.get_or_404(Item, item_id)
    status = request.form.get("status")
    if status not in {"open", "resolved"}:
        abort(400)
    item.status = status
    db.session.commit()
    flash("Report marked " + status + ".", "success")
    return redirect(url_for("admin") + "#reports")


@app.post("/admin/item/<int:item_id>/delete")
@login_required
def admin_delete_item(item_id):
    require_admin()
    item = db.get_or_404(Item, item_id)
    Claim.query.filter_by(item_id=item.id).delete(synchronize_session=False)
    db.session.delete(item)
    db.session.commit()
    flash("Report and its claims deleted.", "success")
    return redirect(url_for("admin") + "#reports")


@app.post("/admin/claim/<int:claim_id>/review")
@login_required
def admin_review_claim(claim_id):
    require_admin()
    claim = db.get_or_404(Claim, claim_id)
    decision = request.form.get("decision")
    if decision not in {"approved", "rejected"}:
        abort(400)
    if claim.status != "pending":
        flash("This claim has already been reviewed.", "info")
    else:
        claim.status = decision
        if decision == "approved":
            claim.item.status = "resolved"
            for other in claim.item.claims:
                if other.id != claim.id and other.status == "pending":
                    other.status = "rejected"
        db.session.commit()
        flash("Claim " + decision + " by administrator.", "success")
    return redirect(url_for("admin") + "#claims")


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.errorhandler(413)
def too_large(_error):
    flash("Image is too large. Maximum upload size is 4 MB.", "error")
    return redirect(url_for("new_item"))


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have permission to view this page."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="We couldn't find that page or report."), 404


with app.app_context():
    db.create_all()
    # Add profile columns to existing databases without deleting existing data.
    user_columns = {column["name"] for column in inspect(db.engine).get_columns("user")}
    profile_columns = {
        "role": "VARCHAR(20) NOT NULL DEFAULT 'student'",
        "enrollment_number": "VARCHAR(40)",
        "semester": "VARCHAR(20)",
        "course": "VARCHAR(100)",
        "subject": "VARCHAR(100)",
        "designation": "VARCHAR(100)",
        "is_active": "BOOLEAN NOT NULL DEFAULT 1",
        "mobile_number": "VARCHAR(20)",
        "email_verified": "BOOLEAN NOT NULL DEFAULT 1",
        "verification_code_hash": "VARCHAR(255)",
        "verification_expires_at": "DATETIME",
    }
    with db.engine.begin() as connection:
        for column_name, column_type in profile_columns.items():
            if column_name not in user_columns:
                connection.execute(text("ALTER TABLE user ADD COLUMN " + column_name + " " + column_type))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
