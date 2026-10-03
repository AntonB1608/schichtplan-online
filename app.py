import os
import re
import secrets
from datetime import time, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import bcrypt
import requests
from dotenv import load_dotenv
from flask import Flask, request, render_template, session, redirect, flash, send_from_directory
from markupsafe import escape
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Boolean, Integer, MetaData


# APP CONFIG
 
load_dotenv()
 
app = Flask(__name__)
 
debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
database_url = os.getenv("DATABASE_URL")
 
if database_url:
    database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///schichtplan.db"
 
app.config['SECRET_KEY'] = os.getenv("secret_key")
app.config['WTF_CSRF_ENABLED'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
 

csrf = CSRFProtect(app)

 

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


REMINDER_DAY = datetime(2000, 1, 1)

SHIFT_TYPES = {
    "early": "Frühschicht",
    "late": "Spätschicht",
    "night": "Nachtschicht",
    "off": "Frei",
}

LEAD_MINUTES = [30, 60, 90, 120, 180]

# Feste Farb-Palette für Vorlagen (warm, gedeckt, zum Marken-Look passend)
TEMPLATE_COLORS = ["#c98a3c", "#c05f45", "#4a5578", "#6f8f6a", "#4f7a8c", "#8a5a7a"]

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]


def datum_lang(d):
    """z. B. 'Dienstag, 8. September'"""
    return f"{WOCHENTAGE[d.weekday()]}, {d.day}. {MONATE[d.month - 1]}"


@app.template_filter("datum_kurz")
def datum_kurz(d):
    """z. B. 'Di, 08.09.2026'"""
    return f"{WOCHENTAGE[d.weekday()][:2]}, {d.strftime('%d.%m.%Y')}"


@app.context_processor
def inject_shift_types():
    return {"SHIFT_TYPES": SHIFT_TYPES, "LEAD_MINUTES": LEAD_MINUTES, "TEMPLATE_COLORS": TEMPLATE_COLORS}


def to_user_time(now_utc, tz_name):
    """Rechnet einen aware UTC-Zeitpunkt in die lokale Wanduhrzeit des Nutzers
    um und gibt sie als naive datetime zurueck (passend zu den lokal
    gespeicherten Schichtzeiten). Unbekannte Zeitzonen fallen auf UTC zurueck."""
    try:
        tz = ZoneInfo(tz_name) if tz_name else timezone.utc
    except Exception:
        tz = timezone.utc
    return now_utc.astimezone(tz).replace(tzinfo=None)
 
 
# MODELS

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })
 
db = SQLAlchemy(app, model_class=Base)
migrate = Migrate(app, db)
class User(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    mail: Mapped[str] = mapped_column(String(100), unique=True)
    mail_verified: Mapped[bool] = mapped_column(default=False)
    password_hash: Mapped[Optional[str]] = mapped_column()
    locked_until: Mapped[Optional[datetime]] = mapped_column()
    failed_login_attempts: Mapped[int] = mapped_column(default=0)
    registration_completed: Mapped[bool] = mapped_column(default=False)
    time_zone: Mapped[Optional[str]] = mapped_column()
    daily_reminder_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    daily_reminder_time: Mapped[datetime] = mapped_column(default=REMINDER_DAY.replace(hour=18), nullable=False)
    shift_reminder_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    shift_reminder_lead_minutes: Mapped[int] = mapped_column(default=60, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    daily_reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(default=None)

class Verification(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    token_date: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

class Team(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    invite_code: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
 
class TeamMember(db.Model):
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"))
    role: Mapped[str] = mapped_column()
    joined_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

class Shift(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("team.id"))
    start: Mapped[Optional[datetime]]= mapped_column()
    end: Mapped[Optional[datetime]] = mapped_column()
    shift_type: Mapped[str] = mapped_column()
    note: Mapped[Optional[str]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    shift_reminder_sent_at: Mapped[datetime] = mapped_column(default=None, nullable=True)


class ShiftTemplate(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    name: Mapped[str] = mapped_column(String(30))
    color: Mapped[str] = mapped_column(String(7))
    start_time: Mapped[Optional[str]] = mapped_column()
    end_time: Mapped[Optional[str]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


# ROUTES - PUBLIC
 
@app.route("/", methods=["GET"])
def homepage():
    return render_template("homepage.html")


@app.route("/security")
def security():
    return render_template("security.html")


@app.route("/testen")
def demo():
    # Ausprobieren ohne Konto: läuft komplett im Browser, nichts wird gespeichert.
    return render_template("demo.html")


TEAM_SIZES = ["2-10", "11-30", "31-100", "100+"]


@app.route("/teams", methods=["GET", "POST"])
def teams():
    if request.method == "GET":
        return render_template("teams.html", form={}, team_sizes=TEAM_SIZES)

    form = {
        "name": request.form.get("name", "").strip()[:80],
        "workplace": request.form.get("workplace", "").strip()[:120],
        "team_size": request.form.get("team_size", ""),
        "email": request.form.get("email", "").strip()[:120],
        "message": request.form.get("message", "").strip()[:1000],
    }

    # Spam-Bot hat das unsichtbare Feld ausgefuellt: so tun, als ob alles geklappt hat
    if request.form.get("website"):
        return render_template("teams.html", sent=True, form={}, team_sizes=TEAM_SIZES)

    if not form["name"] or not form["workplace"] or form["team_size"] not in TEAM_SIZES:
        return render_template("teams.html", form=form, team_sizes=TEAM_SIZES,
                               error="Bitte gib deinen Namen, deinen Arbeitsplatz und die Teamgröße an.")
    if not EMAIL_REGEX.match(form["email"]):
        return render_template("teams.html", form=form, team_sizes=TEAM_SIZES,
                               error="Bitte gib eine gültige E-Mail-Adresse ein.")

    rows = "".join(
        f'<tr><td style="padding:6px 16px 6px 0;color:#706e69;vertical-align:top;">{label}</td>'
        f'<td style="padding:6px 0;color:#1d1c1a;white-space:pre-line;">{escape(value) or "&ndash;"}</td></tr>'
        for label, value in [
            ("Name", form["name"]),
            ("Workplace", form["workplace"]),
            ("Team size", form["team_size"]),
            ("Email", form["email"]),
            ("Message", form["message"]),
        ]
    )
    html = (
        f'<div style="font-family:{MAIL_FONT};font-size:15px;line-height:1.5;">'
        f'<p style="margin:0 0 16px;font-size:18px;font-weight:600;color:#1d1c1a;">New team request</p>'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0">{rows}</table>'
        f'<p style="margin:16px 0 0;color:#706e69;">Reply to this email to answer them directly.</p>'
        f'</div>'
    )
    subject = f"Team-Anfrage: {form['workplace']} ({form['team_size']})"
    ok = send_email("team@shiftmates.org", subject, html, reply_to=form["email"])

    if not ok:
        return render_template("teams.html", form=form, team_sizes=TEAM_SIZES,
                               error="Bei uns ist etwas schiefgelaufen. Bitte versuch es in einer Minute noch einmal.")
    return render_template("teams.html", sent=True, form={}, team_sizes=TEAM_SIZES)


@app.route("/robots.txt")
def robots():
    return send_from_directory(app.static_folder, "robots.txt")
 
 
# ROUTES - REGISTRATION
 
@app.route("/register", methods=["POST", "GET"])
def register():
 
    if request.method == "POST":
 
        username = request.form["username"]
        email = request.form["email"]
 
        if len(username) > 20:
            flash("Benutzername zu lang (max. 20 Zeichen).", "error")
            return render_template("register.html", name=username)

        if not EMAIL_REGEX.match(email):
            flash("Ungültige E-Mail-Adresse.", "error")
            return render_template("register.html", name=username)

        existing_name = User.query.filter_by(name=username).first()
        if existing_name and existing_name.registration_completed:
            flash("Diesen Benutzernamen gibt es schon.", "error")
            return render_template("register.html")

        existing_mail = User.query.filter_by(mail=email).first()
        if existing_mail and existing_mail.registration_completed:
            flash("Diese E-Mail-Adresse ist schon registriert.", "error")
            return render_template("register.html", name=username)
        for stale in {existing_name, existing_mail}:
 
            if stale is not None:
 
                Verification.query.filter_by(user_id=stale.id).delete()
                db.session.delete(stale)
 
        db.session.commit()
        token = secrets.token_urlsafe(64)
        token_date = datetime.now(timezone.utc)
        new_user = User(name=username, mail=email, created_at=token_date)
        db.session.add(new_user)
        try:
 
            db.session.commit()
 
        except IntegrityError:
 
            db.session.rollback()
            return render_template("verifyregister.html")
 
        verify_link = f"{request.url_root}verify/{token}"
        subject = "Bestätige deine E-Mail-Adresse"
        html = build_action_mail(
            subject=subject,
            headline="Bestätige deine E-Mail-Adresse",
            intro=f"Willkommen, {username}. Bestätige deine Adresse, dann kannst du ein Passwort festlegen und deine erste Schicht eintragen.",
            button_label="E-Mail bestätigen",
            link=verify_link,
            note="Du hast dich nicht bei Shiftmates registriert? Dann kannst du diese Mail einfach ignorieren.",
        )
        send_email(email, subject, html)
 
        db.session.add(Verification(token=token, user_id=new_user.id))
        db.session.commit()
        return render_template("verifyregister.html")
 
    return render_template("register.html")
 
 
@app.route('/verify/<token>')
def verify_user(token):
    verification = Verification.query.filter_by(token=token).first()
    if not verification:
        flash("Dieser Link ist ungültig oder wurde schon benutzt.", "error")
        return redirect("/register")
    token_time = verification.token_date.replace(tzinfo=timezone.utc)
    if token_time + timedelta(hours=1) < datetime.now(timezone.utc):
        flash("Dieser Link ist abgelaufen.", "error")
        db.session.delete(verification)
        db.session.commit()
        return redirect("/register")
    
    real_user = User.query.filter_by(id=verification.user_id).first()
    if not real_user:
        flash("Konto nicht gefunden.", "error")
        return redirect("/register")
 
    real_user.mail_verified = True
    db.session.delete(verification)
    db.session.commit()
 
    session["user_id"] = real_user.id
    return redirect("/registeruser")
 
 
@app.route("/registeruser", methods=["GET", "POST"])
def registeruser():
    if "user_id" not in session:
        return redirect("/login")
 
    if not request.method == "POST":
        return render_template("registeruser.html")
 
    sonderzeichen = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
    password = request.form["password"]
    password_again = request.form["password_again"]
 
    if len(password) < 8:
        flash("Passwort zu kurz (mindestens 8 Zeichen).", "error")
        return render_template("registeruser.html")

    if not any(z in password for z in sonderzeichen):
        flash("Das Passwort braucht mindestens ein Sonderzeichen.", "error")
        return render_template("registeruser.html")

    if password != password_again:
        flash("Die Passwörter stimmen nicht überein.", "error")
        return render_template("registeruser.html")
    user = User.query.filter_by(id=session["user_id"]).first()
    if not user:
        return redirect("/")
 
    user.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    user.password_hash = user.password_hash.decode("utf-8")
    user.registration_completed = True
    db.session.commit()
    flash("Konto erstellt. Du kannst dich jetzt anmelden.", "success")
    return redirect("/login")
 
 
# ROUTES - AUTH

 
@app.route("/login", methods=["GET", "POST"])
def login():
    if not request.method == "POST":
        return render_template("login.html")
 
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    username = request.form["username"]
    password = request.form["password"]
 
    user = User.query.filter_by(name=username).first()
    if not user:

        flash("Benutzername oder Passwort falsch.", "error")
        return render_template("login.html")
 
    if user.locked_until and now < user.locked_until:

        flash("Dein Konto ist nach zu vielen Fehlversuchen vorübergehend gesperrt. Versuch es in ein paar Minuten noch einmal.", "error")
        return render_template("login.html")
   
    if user.locked_until and now >= user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()
 
    if not user.password_hash:

        flash("Benutzername oder Passwort falsch.", "error")
        return render_template("login.html")
 
    if bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
        user.failed_login_attempts = 0
        user.locked_until = None
        session["user_id"] = user.id
        db.session.commit()
        if not user.time_zone:
            return redirect("/profile")
        else:
            return redirect("/index")
 
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= 5:

        user.locked_until = now + timedelta(minutes=15)
        db.session.commit()
        flash("Zu viele Fehlversuche. Dein Konto ist für 15 Minuten gesperrt.", "error")
        return render_template("login.html")
 
    db.session.commit()
    
    flash("Benutzername oder Passwort falsch.", "error")
    return render_template("login.html")
 
 
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")
 
 

# ROUTES - PASSWORD RESET
 
@app.route("/reset", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        mail = request.form["mail"]
        user = User.query.filter_by(mail=mail).first()
        if not user:
            return render_template("passwordreset.html")
 
        token = secrets.token_urlsafe(64)
        token_date = datetime.now(timezone.utc)
        verify_link = f"{request.url_root}reset/{token}"
        subject = "Setze dein Passwort zurück"
        html = build_action_mail(
            subject=subject,
            headline="Setze dein Passwort zurück",
            intro=f"Hallo {user.name}, über den Knopf unten legst du ein neues Passwort fest.",
            button_label="Neues Passwort festlegen",
            link=verify_link,
            note="Der Link ist eine Stunde gültig. Du hast das nicht angefordert? Dann ignorier diese Mail, dein Passwort bleibt unverändert.",
        )
        send_email(user.mail, subject, html)
 
        db.session.add(Verification(token=token, user_id=user.id, token_date=token_date))
        db.session.commit()
        return render_template("passwordreset.html")
    else:
        return render_template("reset.html")
 
 
@app.route('/reset/<token>', methods=["GET", "POST"])
def reset_token(token):

    verification = Verification.query.filter_by(token=token).first()

    if not verification:

        flash("Dieser Link ist ungültig oder wurde schon benutzt.", "error")
        return redirect("/reset")

    token_time = verification.token_date.replace(tzinfo=timezone.utc)
    date_expired = token_time + timedelta(hours=1)

    if datetime.now(timezone.utc) > date_expired:

        flash("Dieser Link ist abgelaufen.", "error")
        db.session.delete(verification)
        db.session.commit()
        return redirect("/reset")

    real_user = User.query.filter_by(id=verification.user_id).first()

    if not real_user:

        flash("Konto nicht gefunden.", "error")
        return redirect("/reset")

    if request.method == "GET":
        return render_template("newpassword.html", token=token)

    sonderzeichen = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
    password = request.form["password"]
    password_again = request.form["password_again"]

    if len(password) < 8:
        flash("Passwort zu kurz (mindestens 8 Zeichen).", "error")
        return render_template("newpassword.html", token=token)

    if not any(z in password for z in sonderzeichen):

        flash("Das Passwort braucht mindestens ein Sonderzeichen.", "error")
        return render_template("newpassword.html", token=token)

    if password != password_again:

        flash("Die Passwörter stimmen nicht überein.", "error")
        return render_template("newpassword.html", token=token)

    real_user.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    real_user.password_hash = real_user.password_hash.decode("utf-8")
    db.session.delete(verification)
    db.session.commit()
    flash("Passwort geändert. Du kannst dich jetzt anmelden.", "success")
    return redirect("/login")
 
 

# ROUTES - PROFILE

 
@app.route("/profile", methods=["POST", "GET"])
def show_profile():
    if "user_id" not in session:
        return redirect("/login")

    user = db.session.get(User, session["user_id"])
    if user is None:
        return redirect("/login")
    if request.method != "POST":
        return render_template("profile.html", user=user)
    
    timezone_name = request.form.get("time_zone")
    daily_reminder_time = request.form.get("daily_reminder_time")
    lead_minutes = request.form.get("shift_reminder_lead_minutes")

    if not timezone_name:
        flash("Wir konnten deine Zeitzone nicht ermitteln. Bitte lade die Seite neu.", "error")
        return render_template("profile.html", user=user)

    try:
        ZoneInfo(timezone_name)
    except Exception:
        flash("Ungültige Zeitzone.", "error")
        return render_template("profile.html", user=user)

    
    
    if daily_reminder_time:
        try:
            parsed_time = datetime.strptime(daily_reminder_time, "%H:%M").time()
        except ValueError:
            flash("Ungültige Uhrzeit für die Erinnerung.", "error")
            return render_template("profile.html", user=user)
    else:
        parsed_time = user.daily_reminder_time.time()
    if lead_minutes:
        try:
            lead_minutes = int(lead_minutes)
            if lead_minutes not in LEAD_MINUTES:
                raise ValueError
        except ValueError:
            flash("Ungültige Vorlaufzeit.", "error")
            return render_template("profile.html", user=user)
    user.daily_reminder_time = REMINDER_DAY.replace(hour=parsed_time.hour, minute=parsed_time.minute)
    if lead_minutes:
        user.shift_reminder_lead_minutes = lead_minutes

    user.time_zone = timezone_name
    user.daily_reminder_enabled = bool(request.form.get("daily_reminder_enabled"))
    user.shift_reminder_enabled = bool(request.form.get("shift_reminder_enabled"))
    
    db.session.commit()
    flash("Profil gespeichert.", "success")
    return redirect("/index")
 



@app.route("/unsubscribe", methods=["POST", "GET"]) 
def unsubscribe():
    if "user_id" not in session:

        return redirect("/login")
    if request.method == "GET":
        return render_template("unsubscribe.html")
    if request.method == "POST":
        user = db.session.get(User, session["user_id"])
        if user is None:
            return redirect("/login")
        user.daily_reminder_enabled = False
        user.shift_reminder_enabled = False
        db.session.commit()
        flash("Erinnerungen abgeschaltet.", "success")
        return redirect("/profile")
    
        
 
# ROUTES - SHIFTS
 
@app.route("/index", methods=["GET", "POST"])
def schicht_eintragen():
    if "user_id" not in session:
        return redirect("/login")
 
    user_id = session["user_id"]
    templates = ShiftTemplate.query.filter_by(user_id=user_id).order_by(ShiftTemplate.created_at).all()

    # Tage, an denen schon eine Schicht liegt – fürs Tage-Raster, damit man
    # sieht, wo man sich sonst doppelt einträgt. Ab Montag dieser Woche reicht.
    week_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start -= timedelta(days=week_start.weekday())
    booked = Shift.query.filter(Shift.user_id == user_id, Shift.start >= week_start).all()
    booked_dates = sorted({s.start.strftime("%Y-%m-%d") for s in booked if s.start})

    def render_index():
        return render_template("index.html", templates=templates, booked_dates=booked_dates)

    if request.method == "POST":
        # Mehrere Tage: kommagetrennt aus dem Tage-Raster (datum = Fallback)
        dates_raw = request.form.get("dates") or request.form.get("datum") or ""
        shift_type = request.form.get("shift_type")
        note = request.form.get("note") or None

        if shift_type not in SHIFT_TYPES and shift_type != "custom":
            flash("Bitte wähle eine Schichtart.", "error")
            return render_index()

        if shift_type == "custom":
            shift_type = (request.form.get("shift_type_custom") or "").strip()
            if not shift_type:
                flash("Bitte gib deiner Schichtart einen Namen.", "error")
                return render_index()
            if len(shift_type) > 30:
                flash("Schichtart zu lang (max. 30 Zeichen).", "error")
                return render_index()

        date_strs = [d for d in dates_raw.split(",") if d]
        if not date_strs:
            flash("Bitte wähle mindestens einen Tag.", "error")
            return render_index()
        try:
            dates = [datetime.strptime(d, "%Y-%m-%d") for d in date_strs]
        except ValueError:
            flash("Ungültiges Datum.", "error")
            return render_index()

        # Zeiten nur einmal prüfen – sie gelten für alle gewählten Tage
        zeit_anfang = zeit_ende = None
        if shift_type != "off":
            zeit_anfang = request.form.get("zeit_anfang")
            zeit_ende = request.form.get("zeit_ende")
            if not zeit_anfang or not zeit_ende:
                flash("Bitte füll alle Felder aus.", "error")
                return render_index()
            try:
                zeit_anfang = datetime.strptime(zeit_anfang, "%H:%M").time()
                zeit_ende = datetime.strptime(zeit_ende, "%H:%M").time()
            except ValueError:
                flash("Ungültige Uhrzeit.", "error")
                return render_index()

        for date in dates:
            if shift_type == "off":
                start = datetime.combine(date, time(0, 0))
                end = start
            else:
                start = datetime.combine(date, zeit_anfang)
                end = datetime.combine(date, zeit_ende)
                if end <= start:
                    end = end + timedelta(days=1)
            db.session.add(Shift(user_id=user_id, start=start, end=end, shift_type=shift_type,
                                 note=note, created_at=datetime.now(timezone.utc)))
        db.session.commit()

        # Optional: diese Schicht als Vorlage merken
        if request.form.get("save_template"):
            tname = (request.form.get("template_name") or "").strip()[:30]
            tcolor = request.form.get("template_color")
            if tname and tcolor in TEMPLATE_COLORS:
                if shift_type == "off":
                    t_start = t_end = None
                else:
                    t_start = request.form.get("zeit_anfang")
                    t_end = request.form.get("zeit_ende")
                db.session.add(ShiftTemplate(user_id=user_id, name=tname, color=tcolor,
                                             start_time=t_start, end_time=t_end))
                db.session.commit()

        n = len(dates)
        flash(f"{n} Schicht{'en' if n != 1 else ''} gespeichert.", "success")
        return redirect("/index")
    else:
        return render_index()
 
 
@app.route("/shifts", methods=["GET"])
def show_shift():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    shifts = Shift.query.filter_by(user_id=user_id).order_by(Shift.start).all()
    return render_template("shifts.html", shifts=shifts)
 
 
@app.route("/delete/<int:date_id>", methods=["POST"])
def delete_shift(date_id):
    if "user_id" not in session:
            return redirect("/login")
    
    shift = Shift.query.filter_by(id=date_id, user_id=session["user_id"]).first()
    if shift:
        db.session.delete(shift)
        db.session.commit()
        flash("Schicht gelöscht.", "deleted")
        return redirect("/shifts")

    return redirect("/shifts")


# ROUTES - TEAM

INVITE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # ohne 0/O/1/I/L, leichter vorzulesen


def generate_invite_code():
    for _ in range(20):
        code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(6))
        if not Team.query.filter_by(invite_code=code).first():
            return code
    return secrets.token_hex(4).upper()


def team_if_leader(team_id, user_id):
    """Gibt das Team nur zurueck, wenn dieser Nutzer dessen Leiter ist – sonst None.
    Das ist die harte Berechtigung fuer alles, was fremde Schichten betrifft."""
    membership = TeamMember.query.filter_by(user_id=user_id, team_id=team_id, role="leader").first()
    if membership is None:
        return None
    return db.session.get(Team, team_id)


@app.route("/team")
def team_home():
    if "user_id" not in session:
        return redirect("/login")
    memberships = TeamMember.query.filter_by(user_id=session["user_id"]).all()
    led, member_of = [], []
    for m in memberships:
        team = db.session.get(Team, m.team_id)
        if team is None:
            continue
        (led if m.role == "leader" else member_of).append(team)
    return render_template("team.html", led=led, member_of=member_of)


@app.route("/team/erstellen", methods=["POST"])
def team_create():
    if "user_id" not in session:
        return redirect("/login")
    name = (request.form.get("team_name") or "").strip()[:60]
    if not name:
        flash("Bitte gib dem Team einen Namen.", "error")
        return redirect("/team")
    if Team.query.filter_by(name=name).first():
        flash("Diesen Teamnamen gibt es schon. Wähl einen anderen.", "error")
        return redirect("/team")
    team = Team(name=name, invite_code=generate_invite_code())
    db.session.add(team)
    db.session.commit()
    db.session.add(TeamMember(user_id=session["user_id"], team_id=team.id, role="leader"))
    db.session.commit()
    flash("Team erstellt. Teile den Code mit deinem Team.", "success")
    return redirect(f"/team/{team.id}")


@app.route("/team/beitreten", methods=["POST"])
def team_join():
    if "user_id" not in session:
        return redirect("/login")
    code = (request.form.get("invite_code") or "").strip().upper()
    team = Team.query.filter_by(invite_code=code).first()
    if team is None:
        flash("Diesen Team-Code gibt es nicht.", "error")
        return redirect("/team")
    already = TeamMember.query.filter_by(user_id=session["user_id"], team_id=team.id).first()
    if already:
        flash("Du bist schon in diesem Team.", "error")
        return redirect("/team")
    db.session.add(TeamMember(user_id=session["user_id"], team_id=team.id, role="member"))
    db.session.commit()
    flash(f"Du bist dem Team {team.name} beigetreten.", "success")
    return redirect("/team")


@app.route("/team/<int:team_id>")
def team_view(team_id):
    if "user_id" not in session:
        return redirect("/login")

    # Harte Berechtigung: nur der Leiter dieses Teams darf hier rein.
    team = team_if_leader(team_id, session["user_id"])
    if team is None:
        flash("Du bist nicht der Leiter dieses Teams.", "error")
        return redirect("/team")

    members = TeamMember.query.filter_by(team_id=team_id).all()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    roster = []
    for m in members:
        u = db.session.get(User, m.user_id)
        if u is None:
            continue
        shifts = Shift.query.filter(
            Shift.user_id == u.id,
            Shift.start >= today,
        ).order_by(Shift.start).all()
        roster.append({"user": u, "role": m.role, "shifts": shifts})

    return render_template("team_view.html", team=team, roster=roster)


@app.route("/team/<int:team_id>/schicht/<int:shift_id>", methods=["GET", "POST"])
def team_edit_shift(team_id, shift_id):
    if "user_id" not in session:
        return redirect("/login")

    # Harte Berechtigung: nur der Leiter dieses Teams.
    team = team_if_leader(team_id, session["user_id"])
    if team is None:
        flash("Du bist nicht der Leiter dieses Teams.", "error")
        return redirect("/team")

    shift = db.session.get(Shift, shift_id)
    if shift is None:
        flash("Diese Schicht gibt es nicht mehr.", "error")
        return redirect(f"/team/{team_id}")

    # Die Schicht muss einem Mitglied genau dieses Teams gehören.
    if TeamMember.query.filter_by(team_id=team_id, user_id=shift.user_id).first() is None:
        flash("Diese Schicht gehört nicht zu deinem Team.", "error")
        return redirect(f"/team/{team_id}")

    owner = db.session.get(User, shift.user_id)
    action = f"/team/{team_id}/schicht/{shift_id}"

    def render_edit():
        return render_template("team_shift_edit.html", team=team, shift=shift, owner=owner,
                               action=action)

    if request.method == "POST":
        date_str = request.form.get("datum")
        shift_type = request.form.get("shift_type")
        note = (request.form.get("note") or "").strip() or None

        if not date_str:
            flash("Bitte wähle einen Tag.", "error")
            return render_edit()
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            flash("Ungültiges Datum.", "error")
            return render_edit()

        if shift_type == "custom":
            shift_type = (request.form.get("shift_type_custom") or "").strip()[:30]
            if not shift_type:
                flash("Bitte gib der Schichtart einen Namen.", "error")
                return render_edit()
        elif shift_type not in SHIFT_TYPES:
            flash("Bitte wähle eine Schichtart.", "error")
            return render_edit()

        if shift_type == "off":
            start = datetime.combine(date, time(0, 0))
            end = start
        else:
            za = request.form.get("zeit_anfang")
            ze = request.form.get("zeit_ende")
            if not za or not ze:
                flash("Bitte füll alle Felder aus.", "error")
                return render_edit()
            try:
                za = datetime.strptime(za, "%H:%M").time()
                ze = datetime.strptime(ze, "%H:%M").time()
            except ValueError:
                flash("Ungültige Uhrzeit.", "error")
                return render_edit()
            start = datetime.combine(date, za)
            end = datetime.combine(date, ze)
            if end <= start:
                end = end + timedelta(days=1)

        shift.start = start
        shift.end = end
        shift.shift_type = shift_type
        shift.note = note
        shift.shift_reminder_sent_at = None  # geänderte Schicht: Erinnerung darf neu rausgehen
        db.session.commit()

        # Das Teammitglied per Mail informieren – aber nicht sich selbst.
        if owner and owner.id != session["user_id"] and owner.mail:
            html = build_action_mail(
                subject="Deine Schicht wurde geändert",
                headline="Deine Schicht wurde geändert",
                intro=f"{escape(team.name)} hat eine deiner Schichten angepasst. Hier ist der neue Stand:",
                button_label="Meine Schichten ansehen",
                link="https://www.shiftmates.org/shifts",
                shifts_html=build_shift_rows([shift]),
            )
            send_email(owner.mail, "Deine Schicht wurde geändert", html)
            flash(f"Schicht geändert. {owner.name} wurde per Mail informiert.", "success")
        else:
            flash("Schicht geändert.", "success")
        return redirect(f"/team/{team_id}")

    return render_edit()


@app.route("/team/<int:team_id>/mitglied/<int:user_id>/neu", methods=["GET", "POST"])
def team_new_shift(team_id, user_id):
    if "user_id" not in session:
        return redirect("/login")

    # Harte Berechtigung: nur der Leiter dieses Teams.
    team = team_if_leader(team_id, session["user_id"])
    if team is None:
        flash("Du bist nicht der Leiter dieses Teams.", "error")
        return redirect("/team")

    # Die Schicht darf nur für ein Mitglied genau dieses Teams angelegt werden.
    if TeamMember.query.filter_by(team_id=team_id, user_id=user_id).first() is None:
        flash("Diese Person ist nicht in deinem Team.", "error")
        return redirect(f"/team/{team_id}")

    owner = db.session.get(User, user_id)
    action = f"/team/{team_id}/mitglied/{user_id}/neu"

    def render_new():
        return render_template("team_shift_edit.html", team=team, owner=owner,
                               shift=None, action=action)

    if request.method == "POST":
        date_str = request.form.get("datum")
        shift_type = request.form.get("shift_type")
        note = (request.form.get("note") or "").strip() or None

        if not date_str:
            flash("Bitte wähle einen Tag.", "error")
            return render_new()
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            flash("Ungültiges Datum.", "error")
            return render_new()

        if shift_type == "custom":
            shift_type = (request.form.get("shift_type_custom") or "").strip()[:30]
            if not shift_type:
                flash("Bitte gib der Schichtart einen Namen.", "error")
                return render_new()
        elif shift_type not in SHIFT_TYPES:
            flash("Bitte wähle eine Schichtart.", "error")
            return render_new()

        if shift_type == "off":
            start = datetime.combine(date, time(0, 0))
            end = start
        else:
            za = request.form.get("zeit_anfang")
            ze = request.form.get("zeit_ende")
            if not za or not ze:
                flash("Bitte füll alle Felder aus.", "error")
                return render_new()
            try:
                za = datetime.strptime(za, "%H:%M").time()
                ze = datetime.strptime(ze, "%H:%M").time()
            except ValueError:
                flash("Ungültige Uhrzeit.", "error")
                return render_new()
            start = datetime.combine(date, za)
            end = datetime.combine(date, ze)
            if end <= start:
                end = end + timedelta(days=1)

        shift = Shift(user_id=user_id, team_id=team_id, start=start, end=end,
                      shift_type=shift_type, note=note, created_at=datetime.now(timezone.utc))
        db.session.add(shift)
        db.session.commit()

        # Das Teammitglied per Mail informieren – aber nicht sich selbst.
        if owner and owner.id != session["user_id"] and owner.mail:
            html = build_action_mail(
                subject="Du hast eine neue Schicht",
                headline="Du hast eine neue Schicht",
                intro=f"{escape(team.name)} hat dir eine Schicht eingetragen:",
                button_label="Meine Schichten ansehen",
                link="https://www.shiftmates.org/shifts",
                shifts_html=build_shift_rows([shift]),
            )
            send_email(owner.mail, "Du hast eine neue Schicht", html)
            flash(f"Schicht eingetragen. {owner.name} wurde per Mail informiert.", "success")
        else:
            flash("Schicht eingetragen.", "success")
        return redirect(f"/team/{team_id}")

    return render_new()


# ROUTES - INFORMATION

@app.route("/impressum")
def impressum():
    return render_template("impressum.html")

@app.route("/datenschutz")
def datenschutz():
    return render_template("datenschutz.html")

# HELPERS - DATE & SHIFT

 
#def get_date(now_local):
    tomorrow = now_local + timedelta(days=1)
    return tomorrow.strftime("%d.%m.%Y"), now_local.strftime("%d.%m.%Y")
 


 
 

# HELPERS - MAIL 

 

 
def send_email(to, subject, html, reply_to="team@shiftmates.org"):
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {os.getenv('resend_api_key')}"},
            json={
                "from": "Shiftmates <noreply@send.shiftmates.org>",
                "reply_to": reply_to,
                "to": [to],
                "subject": subject,
                "html": html,
            },
            timeout=10,
        )
        if resp.status_code >= 400:
            print(f"Resend failed {resp.status_code}: {resp.text}")
            return False
        return True
    except requests.RequestException as e:
        print(f"Resend request failed: {e}")
        return False
    
MAIL_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"


def build_shift_rows(shifts):
    rows = ""
    for shift in shifts:
        label = escape(SHIFT_TYPES.get(shift.shift_type, shift.shift_type))

        if shift.shift_type == "off" or not shift.start or not shift.end:
            zeit = "&mdash;"
        else:
            zeit = f"{shift.start.strftime('%H:%M')}&ndash;{shift.end.strftime('%H:%M')}"
            if shift.end.date() != shift.start.date():
                zeit += " +1"

        meta = datum_lang(shift.start) if shift.start else ""
        if shift.note:
            meta += f" &middot; {escape(shift.note)}"

        rows += f"""
      <tr>
        <td style="padding:16px 0 0 0;border-top:1px solid #e8e5df;font-family:{MAIL_FONT};font-size:17px;font-weight:600;color:#1d1c1a;">{label}</td>
        <td align="right" style="padding:16px 0 0 0;border-top:1px solid #e8e5df;font-family:{MAIL_FONT};font-size:17px;font-weight:600;color:#1d1c1a;white-space:nowrap;">{zeit}</td>
      </tr>
      <tr>
        <td colspan="2" style="padding:4px 0 16px 0;font-family:{MAIL_FONT};font-size:13px;color:#706e69;">{meta}</td>
      </tr>"""

    return f"""
          <tr>
            <td style="padding:8px 24px 0 24px;">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
                     style="border-bottom:1px solid #e8e5df;">{rows}
              </table>
            </td>
          </tr>"""


def build_action_mail(subject, headline, intro, button_label, link, note="", shifts_html=""):
    font = MAIL_FONT

    note_block = ""
    if note:
        note_block = f"""
          <tr>
            <td style="padding:8px 24px 0 24px;font-family:{font};font-size:13px;line-height:1.6;color:#706e69;">
              {note}
            </td>
          </tr>"""

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:#faf9f6;">

  <div style="display:none;max-height:0;overflow:hidden;font-size:1px;line-height:1px;color:#faf9f6;">
    {intro}
  </div>

  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
         style="background-color:#faf9f6;">
    <tr>
      <td align="center" style="padding:48px 16px;">

        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="560"
               style="max-width:560px;width:100%;background-color:#ffffff;border:1px solid #d8d5cf;border-radius:10px;">

          <tr>
            <td style="padding:16px 24px;border-bottom:1px solid #e8e5df;">
              <img src="https://www.shiftmates.org/static/brand/shiftmates-logo.png" width="144" height="26" alt="Shiftmates"
                   style="display:block;border:0;outline:none;text-decoration:none;width:144px;height:26px;font-family:{font};font-size:15px;font-weight:600;color:#1d1c1a;">
            </td>
          </tr>

          <tr>
            <td style="padding:24px 24px 0 24px;font-family:{font};font-size:18px;line-height:1.35;font-weight:600;color:#1d1c1a;">
              {headline}
            </td>
          </tr>

          <tr>
            <td style="padding:16px 24px 0 24px;font-family:{font};font-size:15px;line-height:1.5;color:#454440;">
              {intro}
            </td>
          </tr>
{shifts_html}{note_block}
          <tr>
            <td style="padding:24px 24px 24px 24px;">
              <a href="{link}"
                 style="display:inline-block;font-family:{font};font-size:16px;font-weight:500;color:#faf9f6;background-color:#1d1c1a;border:1px solid #1d1c1a;padding:12px 32px;text-decoration:none;">
                {button_label}
              </a>
            </td>
          </tr>

          <tr>
            <td style="padding:16px 24px;border-top:1px solid #e8e5df;font-family:{font};font-size:13px;line-height:1.6;color:#706e69;">
              Der Knopf funktioniert nicht? Kopier diesen Link in deinen Browser:<br>
              <span style="color:#1d1c1a;word-break:break-all;">{link}</span>
            </td>
          </tr>

        </table>

        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="560"
               style="max-width:560px;width:100%;">
          <tr>
            <td align="center" style="padding:16px 24px;font-family:{font};font-size:13px;line-height:1.6;color:#706e69;">
              Shiftmates &middot; <a href="https://www.shiftmates.org" style="color:#706e69;text-decoration:underline;">www.shiftmates.org</a>
              &middot; <a href="https://www.shiftmates.org/unsubscribe" style="color:#706e69;text-decoration:underline;">Erinnerungen abschalten</a>
            </td>
          </tr>
        </table>

      </td>
    </tr>
  </table>

</body>
</html>"""

# MAIN


if __name__ == "__main__":
 
    app.run(host='0.0.0.0', port=5555, debug=debug_mode)
 