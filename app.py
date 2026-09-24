import os
import re
import secrets
from datetime import time, datetime, timedelta, timezone
from urllib.parse import quote
import bcrypt
import emoji
import requests
from dotenv import load_dotenv
from flask import Flask, request, render_template, session, redirect, flash
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
    "early": "Early shift",
    "late": "Late shift",
    "night": "Night shift",
    "off": "Day off",
}

LEAD_MINUTES = [30, 60, 90, 120, 180]


@app.context_processor
def inject_shift_types():
    return {"SHIFT_TYPES": SHIFT_TYPES, "LEAD_MINUTES": LEAD_MINUTES}
 
 
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
    city: Mapped[Optional[str]] = mapped_column()
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


# ROUTES - PUBLIC
 
@app.route("/", methods=["GET"])
def homepage():
    return render_template("homepage.html")
 
 
# ROUTES - REGISTRATION
 
@app.route("/register", methods=["POST", "GET"])
def register():
 
    if request.method == "POST":
 
        username = request.form["username"]
        email = request.form["email"]
 
        if len(username) > 20:
            flash("Username too long (max. 20 characters).", "error")
            return render_template("register.html", name=username)

        if not EMAIL_REGEX.match(email):
            flash("Invalid email address.", "error")
            return render_template("register.html", name=username)

        existing_name = User.query.filter_by(name=username).first()
        if existing_name and existing_name.registration_completed:
            flash("Username already exists.", "error")
            return render_template("register.html")

        existing_mail = User.query.filter_by(mail=email).first()
        if existing_mail and existing_mail.registration_completed:
            flash("Email already exists.", "error")
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
        subject = "Confirm your email"
        html = build_action_mail(
            subject=subject,
            headline="Confirm your email",
            intro=f"Welcome, {username}. Confirm your address and you can set a password and add your first shift.",
            button_label="Confirm my email",
            link=verify_link,
            note="If you didn't sign up for Shiftmates, you can ignore this email.",
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
        flash("This link is invalid or has already been used.", "error")
        return redirect("/register")
    token_time = verification.token_date.replace(tzinfo=timezone.utc)
    if token_time + timedelta(hours=1) < datetime.now(timezone.utc):
        flash("This link has expired.", "error")
        db.session.delete(verification)
        db.session.commit()
        return redirect("/register")
    
    real_user = User.query.filter_by(id=verification.user_id).first()
    if not real_user:
        flash("Account not found.", "error")
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
        flash("Password too short (min. 8 characters).", "error")
        return render_template("registeruser.html")

    if not any(z in password for z in sonderzeichen):
        flash("Password must contain a special character.", "error")
        return render_template("registeruser.html")

    if password != password_again:
        flash("Passwords don't match.", "error")
        return render_template("registeruser.html")
    user = User.query.filter_by(id=session["user_id"]).first()
    if not user:
        return redirect("/")
 
    user.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    user.password_hash = user.password_hash.decode("utf-8")
    user.registration_completed = True
    db.session.commit()
    flash("Account created. You can log in now.", "success")
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

        flash("Wrong username or password", "error")
        return render_template("login.html")
 
    if user.locked_until and now < user.locked_until:

        flash(f"Account locked until {user.locked_until.strftime('%H:%M:%S')}", "error")
        return render_template("login.html")
   
    if user.locked_until and now >= user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()
 
    if not user.password_hash:

        flash("Wrong username or password.", "error")
        return render_template("login.html")
 
    if bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
        user.failed_login_attempts = 0
        user.locked_until = None
        session["user_id"] = user.id
        db.session.commit()
        if not user.city:
            return redirect("/profile")
        else:
            return redirect("/index")
 
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= 5:

        user.locked_until = now + timedelta(minutes=15)
        db.session.commit()
        flash("Too many failed attempts. Account locked for 15 minutes.", "error")
        return render_template("login.html")
 
    db.session.commit()
    
    flash("Wrong username or password", "error")
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
        subject = "Reset your password"
        html = build_action_mail(
            subject=subject,
            headline="Reset your password",
            intro=f"Hi {user.name}, use the link below to set a new password.",
            button_label="Set a new password",
            link=verify_link,
            note="This link expires in one hour. If you didn't request a reset, ignore this email — your password stays unchanged.",
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

        flash("This link is invalid or has already been used.", "error")
        return redirect("/reset")

    token_time = verification.token_date.replace(tzinfo=timezone.utc)
    date_expired = token_time + timedelta(hours=1)

    if datetime.now(timezone.utc) > date_expired:

        flash("This link has expired.", "error")
        db.session.delete(verification)
        db.session.commit()
        return redirect("/reset")

    real_user = User.query.filter_by(id=verification.user_id).first()

    if not real_user:

        flash("Account not found.", "error")
        return redirect("/reset")

    if request.method == "GET":
        return render_template("newpassword.html", token=token)

    sonderzeichen = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
    password = request.form["password"]
    password_again = request.form["password_again"]

    if len(password) < 8:
        flash("Password too short (min. 8 characters)", "error")
        return render_template("newpassword.html", token=token)

    if not any(z in password for z in sonderzeichen):

        flash("Password doesn't contain special character", "error")
        return render_template("newpassword.html", token=token)

    if password != password_again:

        flash("Passwords don't match", "error")
        return render_template("newpassword.html", token=token)

    real_user.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    real_user.password_hash = real_user.password_hash.decode("utf-8")
    db.session.delete(verification)
    db.session.commit()
    flash("Password changed. You can log in now.", "success")
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
    
    city = request.form.get("city")
    daily_reminder_time = request.form.get("daily_reminder_time")
    lead_minutes = request.form.get("shift_reminder_lead_minutes")

    if not city:
        flash("No city set.", "error")
        return render_template("profile.html", user=user)

    
    
    if daily_reminder_time:
        try:
            parsed_time = datetime.strptime(daily_reminder_time, "%H:%M").time()
        except ValueError:
            flash("Invalid reminder time.", "error")
            return render_template("profile.html", user=user)
    else:
        parsed_time = user.daily_reminder_time.time()
    if lead_minutes:
        try:
            lead_minutes = int(lead_minutes)
            if lead_minutes not in LEAD_MINUTES:
                raise ValueError
        except ValueError:
            flash("Invalid lead time.", "error")
            return render_template("profile.html", user=user)
    user.daily_reminder_time = REMINDER_DAY.replace(hour=parsed_time.hour, minute=parsed_time.minute)
    if lead_minutes:
        user.shift_reminder_lead_minutes = lead_minutes

    key = os.getenv("openweather_key")
    url = f"https://api.openweathermap.org/data/2.5/weather?q={quote(city)}&appid={key}&units=metric&lang=de"

    try:
        response = requests.get(url, timeout=10).json()
    except requests.RequestException:
        flash("Weather service unavailable. Try again later.", "error")
        return render_template("profile.html", user=user)

    if str(response.get("cod")) != "200":
        flash("City not found.", "error")
        return render_template("profile.html", user=user)

    user.city = city
    user.time_zone = str(response["timezone"])
    
    db.session.commit()
    flash("Profile saved.", "success")
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
        flash("Reminders turned off.", "success")
        return redirect("/profile")
    
        
 
# ROUTES - SHIFTS
 
@app.route("/index", methods=["GET", "POST"])
def schicht_eintragen():
    if "user_id" not in session:
        return redirect("/login")
 
    user_id = session["user_id"]

    if request.method == "POST":
        date = request.form.get("datum")
        shift_type = request.form.get("shift_type")
        note = request.form.get("note") or None

        if shift_type not in SHIFT_TYPES and shift_type != "custom":
            flash("Please select a shift type.", "error")
            return render_template("index.html")

        if shift_type == "custom":
            shift_type = (request.form.get("shift_type_custom") or "").strip()
            if not shift_type:
                flash("Please name your own shift type.", "error")
                return render_template("index.html")
            if len(shift_type) > 30:
                flash("Shift type too long (max. 30 characters).", "error")
                return render_template("index.html")

        if not date:
            flash("Please pick a date.", "error")
            return render_template("index.html")

        try:
            date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            flash("Invalid date.", "error")
            return render_template("index.html")

        if shift_type == "off":
            start = datetime.combine(date, time(0, 0))
            end = start
        else:
            zeit_anfang = request.form.get("zeit_anfang")
            zeit_ende = request.form.get("zeit_ende")
            if not zeit_anfang or not zeit_ende:
                flash("Please fill in all fields.", "error")
                return render_template("index.html")
            try:
                zeit_anfang = datetime.strptime(zeit_anfang, "%H:%M").time()
                zeit_ende = datetime.strptime(zeit_ende, "%H:%M").time()
            except ValueError:
                flash("Invalid time.", "error")
                return render_template("index.html")
            start = datetime.combine(date, zeit_anfang)
            end = datetime.combine(date, zeit_ende)
            if end <= start:
                end = end + timedelta(days=1)

        db.session.add(Shift(user_id=user_id, start=start, end=end, shift_type=shift_type,
                             note=note, created_at=datetime.now(timezone.utc)))
        db.session.commit()
        flash("Shift saved successfully", "success")
        return redirect("/index")
    else:
        return render_template("index.html")
 
 
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
        flash("Shift deleted.", "success")
        return redirect("/shifts")

    return redirect("/shifts")
 
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
 

# HELPERS - WEATHER

def find_weather_data(user_id):
 
    try:
 
        user = User.query.filter_by(id=user_id).first()
        key = os.getenv("openweather_key")
        url = f"https://api.openweathermap.org/data/2.5/weather?q={quote(user.city)}&appid={key}&units=metric&lang=de"
        response = requests.get(url, timeout=10).json()
        mapping = {
            "Thunderstorm": emoji.emojize("There will be thunderstorms tomorrow :thunder_cloud_and_rain:"),
            "Drizzle": emoji.emojize("Light drizzle expected tomorrow. :cloud_with_rain:"),
            "Rain": emoji.emojize("It will rain tomorrow. :umbrella_with_rain_drops:"),
            "Snow": emoji.emojize("It will snow tomorrow :snowflake:"),
            "Atmosphere": emoji.emojize("It will be foggy date. :fog:"),
            "Clear": "Clear skies tomorrow.",
            "Clouds": "It will be cloudy tomorrow.",
        }
        weather_text = mapping.get(response["weather"][0]["main"], "")
        temp = f"{response['main'] ['temp']}°C"
        time_zone = response["timezone"]
        return weather_text, temp, time_zone
 
    except Exception as e:
 
        print(f"{e}")
        weather_text = ""
        temp = ""
        time_zone = 0
        return weather_text, temp, time_zone
 
 

 
 

# HELPERS - MAIL 

 

 
def send_email(to, subject, html):
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {os.getenv('resend_api_key')}"},
            json={
                "from": "Shiftmates <noreply@send.shiftmates.org>",
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

        meta = shift.start.strftime("%A, %d %B") if shift.start else ""
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
<html lang="en">
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
              <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="width:28px;height:28px;background-color:#1d1c1a;border-radius:50%;text-align:center;vertical-align:middle;font-family:Georgia, serif;font-size:15px;line-height:28px;color:#faf9f6;">S</td>
                  <td style="padding-left:8px;font-family:{font};font-size:15px;font-weight:600;color:#1d1c1a;">Shiftmates</td>
                </tr>
              </table>
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
              Button not working? Copy this link into your browser:<br>
              <span style="color:#1d1c1a;word-break:break-all;">{link}</span>
            </td>
          </tr>

        </table>

        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="560"
               style="max-width:560px;width:100%;">
          <tr>
            <td align="center" style="padding:16px 24px;font-family:{font};font-size:13px;line-height:1.6;color:#706e69;">
              Shiftmates &middot; <a href="https://www.shiftmates.org" style="color:#706e69;text-decoration:underline;">www.shiftmates.org</a>
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
 