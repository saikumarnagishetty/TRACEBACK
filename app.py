import os
from datetime import datetime
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
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional

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
    email = StringField("College email", validators=[DataRequired(), Email(), Length(max=120)])
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
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_globals():
    return {"categories": CATEGORIES}


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
            admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
            user = User(
                name=form.name.data.strip(), email=email, role=role,
                enrollment_number=(form.enrollment_number.data or "").strip() or None if role == "student" else None,
                semester=form.semester.data if role == "student" else None,
                course=(form.course.data or "").strip() or None if role == "student" else None,
                subject=(form.subject.data or "").strip() or None if role == "faculty" else None,
                designation=(form.designation.data or "").strip() or None if role == "staff" else None,
                is_admin=(email == admin_email and bool(admin_email))
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to TRACEBACK. Your account is ready.", "success")
            return redirect(url_for("index"))
    return render_template("auth.html", form=form, mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash("You are signed in.", "success")
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("index"))
        flash("Incorrect email or password.", "error")
    return render_template("auth.html", form=form, mode="login")


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
            db.session.add(Claim(message=form.message.data.strip(), item=item, claimant=current_user))
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


@app.route("/admin")
@login_required
def admin():
    if not current_user.is_admin:
        abort(403)
    return render_template(
        "admin.html",
        users=User.query.order_by(User.created_at.desc()).all(),
        items=Item.query.order_by(Item.created_at.desc()).all(),
        pending=Claim.query.filter_by(status="pending").count()
    )


@app.post("/admin/item/<int:item_id>/close")
@login_required
def admin_close_item(item_id):
    if not current_user.is_admin:
        abort(403)
    item = db.get_or_404(Item, item_id)
    item.status = "resolved"
    db.session.commit()
    flash("Report closed by administrator.", "success")
    return redirect(url_for("admin"))


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
    }
    with db.engine.begin() as connection:
        for column_name, column_type in profile_columns.items():
            if column_name not in user_columns:
                connection.execute(text("ALTER TABLE user ADD COLUMN " + column_name + " " + column_type))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
