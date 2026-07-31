import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
 
import bcrypt
import emoji
import requests
from dotenv import load_dotenv
from flask import Flask, request, render_template, session, redirect, flash
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import IntegrityError
 
 
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
 
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
migrate = Migrate(app, db)
 

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
 
 
# MODELS
 
class Register(db.Model):
 
    user_id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(40), unique=True)
    user_mail = db.Column(db.String(100), unique=True)
    user_verification = db.Column(db.Boolean, default=False)
    user_password_hash = db.Column(db.String)
    user_locked_until = db.Column(db.DateTime, nullable=True)
    user_trys = db.Column(db.Integer, default=0)
    user_city = db.Column(db.String)
    email_time_evening = db.Column(db.String)
    email_time_morning = db.Column(db.String)
    user_registered = db.Column(db.Boolean, default=False)
    first_mail_send = db.Column(db.String)
    second_mail_send = db.Column(db.String)
    user_time_zone = db.Column(db.Integer)
 
 
class Date(db.Model):
 
    date_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("register.user_id"))
    date = db.Column(db.String(10))
    time_begin = db.Column(db.String(12))
    time_end = db.Column(db.String(12))
    free = db.Column(db.Boolean)
 
 
class Verification(db.Model):
 
    user_verification_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("register.user_id"))
    user_token = db.Column(db.String)
    user_token_date = db.Column(db.DateTime)
 
 
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
            return render_template("register.html", user_name=username)

        if not EMAIL_REGEX.match(email):
            flash("Invalid email address.", "error")
            return render_template("register.html", user_name=username)

        existing_name = Register.query.filter_by(user_name=username).first()
        if existing_name and existing_name.user_registered:
            flash("Username already exists.", "error")
            return render_template("register.html")

        existing_mail = Register.query.filter_by(user_mail=email).first()
        if existing_mail and existing_mail.user_registered:
            flash("Email already exists.", "error")
            return render_template("register.html", user_name=username)
        for stale in {existing_name, existing_mail}:
 
            if stale is not None:
 
                Verification.query.filter_by(user_id=stale.user_id).delete()
                db.session.delete(stale)
 
        db.session.commit()
        token = secrets.token_urlsafe(64)
        token_date = datetime.now(timezone.utc)
        new_user = Register(user_name=username, user_mail=email, user_token_date=token_date)
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
 
        db.session.add(Verification(user_token=token, user_id=new_user.user_id))
        db.session.commit()
        return render_template("verifyregister.html")
 
    return render_template("register.html")
 
 
@app.route('/verify/<token>')
def verify_user(token):
    verification = Verification.query.filter_by(user_token=token).first()
    if not verification:
        flash("This link is invalid or has already been used.", "error")
        return redirect("/register")

    real_user = Register.query.filter_by(user_id=verification.user_id).first()
    if not real_user:
        flash("Account not found.", "error")
        return redirect("/register")
 
    real_user.user_verification = True
    db.session.delete(verification)
    db.session.commit()
 
    session["user_id"] = real_user.user_id
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
    user = Register.query.filter_by(user_id=session["user_id"]).first()
    if not user:
        return redirect("/")
 
    user.user_password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    user.user_password_hash = user.user_password_hash.decode("utf-8")
    user.user_registered = True
    db.session.commit()
    flash("Account created. You can log in now.", "success")
    return redirect("/login")
 
 
# ROUTES - AUTH

 
@app.route("/login", methods=["GET", "POST"])
def login():
    if not request.method == "POST":
        return render_template("login.html")
 
    now = datetime.today()
    username = request.form["username"]
    password = request.form["password"]
 
    user = Register.query.filter_by(user_name=username).first()
    if not user:

        flash("Wrong username or password", "error")
        return render_template("login.html")
 
    if user.user_locked_until and now < user.user_locked_until:

        flash(f"Account locked until {user.user_locked_until.strftime('%H:%M:%S')}", "error")
        return render_template("login.html")
    
    if user.user_locked_until and now >= user.user_locked_until:
        user.user_trys = 0
        user.user_locked_until = None
        db.session.commit()
 
    if not user.user_password_hash:

        flash("Wrong username or password.", "error")
        return render_template("login.html")
 
    if bcrypt.checkpw(password.encode("utf-8"), user.user_password_hash.encode("utf-8")):
        user.user_trys = 0
        user.user_locked_until = None
        session["user_id"] = user.user_id
        db.session.commit()
        if not user.user_city or not user.email_time_morning or not user.email_time_evening:
            return redirect("/profile")
        else:
            return redirect("/index")
 
    user.user_trys = (user.user_trys or 0) + 1
    if user.user_trys >= 5:

        user.user_locked_until = datetime.today() + timedelta(minutes=15)
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
        user = Register.query.filter_by(user_mail=mail).first()
        if not user:
            return render_template("passwordreset.html")
 
        token = secrets.token_urlsafe(64)
        token_date = datetime.now(timezone.utc)
        verify_link = f"{request.url_root}reset/{token}"
        subject = "Reset your password"
        html = build_action_mail(
            subject=subject,
            headline="Reset your password",
            intro=f"Hi {user.user_name}, use the link below to set a new password.",
            button_label="Set a new password",
            link=verify_link,
            note="This link expires in one hour. If you didn't request a reset, ignore this email — your password stays unchanged.",
        )
        send_email(user.user_mail, subject, html)
 
        db.session.add(Verification(user_token=token, user_id=user.user_id, user_token_date=token_date))
        db.session.commit()
        return render_template("passwordreset.html")
    else:
        return render_template("reset.html")
 
 
@app.route('/reset/<token>', methods=["GET", "POST"])
def reset_token(token):

    if request.method == "GET":

        verification = Verification.query.filter_by(user_token=token).first()

        if not verification:

            flash("Invalid token.", "error")
            return render_template("register.html")
 
        real_user = Register.query.filter_by(user_id=verification.user_id).first()

        if not real_user:

            flash("User not found.", "error")
            return render_template("register.html")
 
        token_time = verification.user_token_date.replace(tzinfo=timezone.utc)
        date_expired = token_time + timedelta(hours=1)
 
        if datetime.now(timezone.utc) > date_expired:

            flash("Expired token", "error")
            return render_template("register.html")
 
        return render_template("registeruser.html", token=token)
    else:
        verification = Verification.query.filter_by(user_token=token).first()
        if not verification:
            return render_template("register.html")
 
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
 
        user = Register.query.filter_by(user_id=verification.user_id).first()
        if not user:
            return redirect("/register")
 
        user.user_password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        user.user_password_hash = user.user_password_hash.decode("utf-8")
        db.session.delete(verification)
        db.session.commit()
        return redirect("/login")
 
 

# ROUTES - PROFILE

 
@app.route("/profile", methods=["POST", "GET"])
def show_profile():
    if "user_id" not in session:
     
            return redirect("/login")
     
    if not request.method == "POST":
 
        user = Register.query.filter_by(user_id=session["user_id"]).first()
        return render_template("profile.html", user=user)
 
   
 
    user_id = session["user_id"]
    user = Register.query.filter_by(user_id=user_id).first()
    email_time_morning = request.form["email_time_morning"]
    email_time_evening = request.form["email_time_evening"]
    city = request.form["city"]
 
    if not email_time_morning or not email_time_evening:

        flash("No email time set", "error")
        return render_template("profile.html", user=user)
    
    if not city:
        flash("No city set.", "error")
        return render_template("profile.html", user=user)
 
    key = os.getenv("openweather_key")
    url = f"https://api.openweathermap.org/data/2.5/weather?q={quote(city)}&appid={key}&units=metric&lang=de"
    response = requests.get(url, timeout=10).json()
    if str(response.get("cod")) == "404":
        flash("City not found.", "error") 
        return render_template("profile.html", user=user)
    
    
    user.user_city = city
    user.user_time_zone = response["timezone"]
    user.email_time_morning = email_time_morning
    user.email_time_evening = email_time_evening
    db.session.commit()
    return redirect("/index")

 
@app.route("/unsubscribe", methods=["GET", "POST"])
def unsubscribe():
    if "user_id" not in session:

        return redirect("/login")
    if request.method == "GET":
        return render_template("unsubscribe.html")
    if request.method == "POST":
        user = Register.query.filter_by(user_id=session["user_id"]).first()
        user.email_time_morning = None
        user.email_time_evening = None
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
        datum = request.form["datum"]
        zeit_anfang = request.form["zeit_anfang"]
        zeit_ende = request.form["zeit_ende"]
        datum_formatiert = datetime.strptime(datum, "%Y-%m-%d").strftime("%d.%m.%Y")
        free = request.form.get("frei")
 
        if free:
            db.session.add(Date(user_id=user_id, date=datum_formatiert, free=True))
        else:
            db.session.add(Date(user_id=user_id, date=datum_formatiert, time_begin=zeit_anfang, time_end=zeit_ende, free=False))
 
        db.session.commit()
        flash("Shift saved successfully", "success")
        return redirect("/index")
    else:
        return render_template("index.html")
 
 
@app.route("/shifts", methods=["GET", "POST"])
def show_shift():
 
    if "user_id" not in session:
        return redirect("/login")
 
    else:
 
        user_id = session["user_id"]
        shifts = Date.query.filter_by(user_id=user_id).all()
        return render_template("shifts.html", shifts=shifts)
 
 
@app.route("/delete/<int:date_id>", methods=["POST"])
def delete_shift(date_id):
    if "user_id" not in session:
            return redirect("/login")
    
    shift = Date.query.filter_by(date_id=date_id, user_id=session["user_id"]).first()
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

 
def get_date(now_local):
    tomorrow = now_local + timedelta(days=1)
    return tomorrow.strftime("%d.%m.%Y"), now_local.strftime("%d.%m.%Y")
 

# HELPERS - WEATHER

def find_weather_data(user_id):
 
    try:
 
        user = Register.query.filter_by(user_id=user_id).first()
        key = os.getenv("openweather_key")
        url = f"https://api.openweathermap.org/data/2.5/weather?q={quote(user.user_city)}&appid={key}&units=metric&lang=de"
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
 
 
def send_reminder(user, date_str, kind):
    shift = Date.query.filter_by(user_id=user.user_id, date=date_str).first()
    day = "tomorrow" if kind == "evening" else "today"

    if not shift:
        line = f"No shift saved for {day}."
    elif shift.free:
        line = f"You are free {day}."
    else:
        line = f"You work {day} from {shift.time_begin} to {shift.time_end}."

    weather_text, temp, _ = find_weather_data(user.user_id)
    weather_text = weather_text.replace("tomorrow", day)

    greeting = "Good evening" if kind == "evening" else "Good morning"
    subject = f"Reminder for {day}"

    font = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    label = "The night before" if kind == "evening" else "The morning of"

    weather_block = ""
    if weather_text or temp:
        weather_block = f"""
              <tr>
                <td style="padding:0 32px;">
                  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
                         style="border-top:1px solid #d2d2d7;">
                    <tr>
                      <td style="padding:20px 0 0 0;font-family:{font};font-size:15px;color:#3a3a3c;">
                        {weather_text}
                      </td>
                      <td align="right" style="padding:20px 0 0 0;font-family:{font};font-size:20px;font-weight:600;color:#1d1d1f;white-space:nowrap;">
                        {temp}
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:#f5f5f7;">

  <div style="display:none;max-height:0;overflow:hidden;font-size:1px;line-height:1px;color:#f5f5f7;">
    {line}
  </div>

  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
         style="background-color:#f5f5f7;">
    <tr>
      <td align="center" style="padding:32px 16px;">

        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600"
               style="max-width:600px;width:100%;background-color:#ffffff;border-radius:12px;">

          <tr>
            <td style="padding:24px 32px 0 32px;font-family:{font};font-size:15px;font-weight:600;color:#0071e3;letter-spacing:-0.01em;">
              Shiftmates
            </td>
          </tr>

          <tr>
            <td style="padding:20px 32px 0 32px;font-family:{font};font-size:12px;color:#6e6e73;text-transform:uppercase;letter-spacing:0.04em;">
              {label} &middot; {date_str}
            </td>
          </tr>

          <tr>
            <td style="padding:6px 32px 0 32px;font-family:{font};font-size:28px;line-height:1.2;font-weight:600;color:#1d1d1f;letter-spacing:-0.02em;">
              {line}
            </td>
          </tr>

          <tr>
            <td style="padding:14px 32px 24px 32px;font-family:{font};font-size:16px;color:#6e6e73;">
              {greeting}, {user.user_name}.
            </td>
          </tr>
{weather_block}
          <tr>
            <td style="padding:28px 32px 24px 32px;">
              <a href="https://www.shiftmates.org/shifts"
                 style="display:inline-block;font-family:{font};font-size:16px;color:#ffffff;background-color:#0071e3;padding:12px 24px;border-radius:980px;text-decoration:none;">
                View your shifts
              </a>
            </td>
          </tr>

        </table>

        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600"
               style="max-width:600px;width:100%;">
          <tr>
            <td align="center" style="padding:24px 32px;font-family:{font};font-size:12px;line-height:1.6;color:#6e6e73;">
              You are receiving this because you set a reminder time on Shiftmates.<br>
              <a href="https://www.shiftmates.org/profile" style="color:#6e6e73;text-decoration:underline;">Change your times</a>
              &nbsp;&middot;&nbsp;
              <a href="https://www.shiftmates.org/unsubscribe" style="color:#6e6e73;text-decoration:underline;">Turn reminders off</a>
              <br><br>
              Shiftmates &middot; Weather data by OpenWeather
            </td>
          </tr>
        </table>

      </td>
    </tr>
  </table>

</body>
</html>"""

    return send_email(user.user_mail, subject, html)
 
 
def send_daily_emails():
    now_utc = datetime.now(timezone.utc)
 
    users = Register.query.filter(
        Register.user_registered.is_(True),
        Register.email_time_morning.isnot(None),
        Register.email_time_evening.isnot(None),
        Register.user_time_zone.isnot(None),
    ).all()
 
    for user in users:
        now_local = now_utc + timedelta(seconds=user.user_time_zone)
        tomorrow_str, today_str = get_date(now_local)
 
        evening_time = datetime.strptime(user.email_time_evening, "%H:%M").time()
        morning_time = datetime.strptime(user.email_time_morning, "%H:%M").time()
 
        if now_local.time() >= evening_time and user.first_mail_send != today_str:
            if send_reminder(user, tomorrow_str, "evening"):
                
                user.first_mail_send = today_str
                db.session.commit()
 
        if morning_time <= now_local.time() < evening_time and user.second_mail_send != today_str:
            if send_reminder(user, today_str, "morning"):
                user.second_mail_send = today_str
                db.session.commit()
 
def build_action_mail(subject, headline, intro, button_label, link, note=""):
    font = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

    note_block = ""
    if note:
        note_block = f"""
          <tr>
            <td style="padding:0 32px 8px 32px;font-family:{font};font-size:14px;line-height:1.6;color:#6e6e73;">
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
<body style="margin:0;padding:0;background-color:#f5f5f7;">

  <div style="display:none;max-height:0;overflow:hidden;font-size:1px;line-height:1px;color:#f5f5f7;">
    {intro}
  </div>

  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
         style="background-color:#f5f5f7;">
    <tr>
      <td align="center" style="padding:32px 16px;">

        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600"
               style="max-width:600px;width:100%;background-color:#ffffff;border-radius:12px;">

          <tr>
            <td style="padding:24px 32px 0 32px;font-family:{font};font-size:15px;font-weight:600;color:#0071e3;letter-spacing:-0.01em;">
              Shiftmates
            </td>
          </tr>

          <tr>
            <td style="padding:22px 32px 0 32px;font-family:{font};font-size:28px;line-height:1.2;font-weight:600;color:#1d1d1f;letter-spacing:-0.02em;">
              {headline}
            </td>
          </tr>

          <tr>
            <td style="padding:14px 32px 4px 32px;font-family:{font};font-size:16px;line-height:1.6;color:#3a3a3c;">
              {intro}
            </td>
          </tr>
{note_block}
          <tr>
            <td style="padding:20px 32px 8px 32px;">
              <a href="{link}"
                 style="display:inline-block;font-family:{font};font-size:16px;color:#ffffff;background-color:#0071e3;padding:12px 26px;border-radius:980px;text-decoration:none;">
                {button_label}
              </a>
            </td>
          </tr>

          <tr>
            <td style="padding:8px 32px 28px 32px;font-family:{font};font-size:13px;line-height:1.6;color:#86868b;">
              Button not working? Copy this link into your browser:<br>
              <span style="color:#0071e3;word-break:break-all;">{link}</span>
            </td>
          </tr>

        </table>

        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600"
               style="max-width:600px;width:100%;">
          <tr>
            <td align="center" style="padding:24px 32px;font-family:{font};font-size:12px;line-height:1.6;color:#6e6e73;">
              Shiftmates &middot; <a href="https://www.shiftmates.org" style="color:#6e6e73;text-decoration:underline;">www.shiftmates.org</a>
            </td>
          </tr>
        </table>

      </td>
    </tr>
  </table>

</body>
</html>"""
# JOBS


if __name__ == "__main__":
 
    app.run(host='0.0.0.0', port=5555, debug=debug_mode)
 