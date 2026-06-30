from flask import Flask, request, render_template, session, redirect
from flask_sqlalchemy import SQLAlchemy
import bcrypt
import datetime as dt
from dotenv import load_dotenv
import os
from flask_wtf.csrf import CSRFProtect
import secrets
from flask_mail import Mail, Message
import re
import requests
from datetime import datetime, timedelta
import emoji
from urllib.parse import quote

load_dotenv()


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///schichtplan.db"
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("gmail_email")
app.config['MAIL_USERNAME'] = os.getenv("gmail_email")
app.config['MAIL_PASSWORD'] = os.getenv("gmail_password")
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['SECRET_KEY'] = os.getenv("secret_key")
app.config['WTF_CSRF_ENABLED'] = True

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
mail = Mail(app)


class Register(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(40), unique=True)
    user_mail = db.Column(db.String(100), unique=True)
    user_verification = db.Column(db.Boolean, default=False)
    user_password_hash = db.Column(db.String)
    user_locked_until = db.Column(db.DateTime, nullable=True)
    user_trys = db.Column(db.Integer, default=0)
    user_city = db.Column(db.String)
    email_time = db.Column(db.String)
    user_registered = db.Column(db.Boolean, default=False)


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


EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

with app.app_context():
    db.create_all()


@app.route("/register", methods=["POST", "GET"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]

        if len(username) > 20:
            return render_template("register.html", error_message="Username too long")

        if not EMAIL_REGEX.match(email):
            return render_template("register.html", error_message="Invalid email address")

        if Register.query.filter_by(user_name=username).first():
            return render_template("register.html", error_message="Username already exists")

        if Register.query.filter_by(user_mail=email).first():
            return render_template("register.html", error_message="Email already exists", user_name=username)

        token = secrets.token_urlsafe(64)
        new_user = Register(user_name=username, user_mail=email)
        db.session.add(new_user)
        db.session.commit()

        db.session.add(Verification(user_token=token, user_id=new_user.user_id))
        db.session.commit()

        msg = Message(
            subject="Verify your email",
            sender=os.getenv("gmail_email"),
            recipients=[email]
        )
        msg.body = f"Dear {username}, click this link to verify your email: http://localhost:5555/verify/{token}"
        mail.send(msg)
        return render_template("verifyregister.html")

    return render_template("register.html")


@app.route('/verify/<token>')
def verify_user(token):
    verification = Verification.query.filter_by(user_token=token).first()
    if not verification:
        return render_template("register.html", error_message="Invalid or expired token")

    real_user = Register.query.filter_by(user_id=verification.user_id).first()
    if not real_user:
        return render_template("register.html", error_message="User not found")

    real_user.user_verification = True
    db.session.delete(verification)
    db.session.commit()

    session["user_id"] = real_user.user_id
    return redirect("/registeruser")


@app.route("/registeruser", methods=["GET", "POST"])
def registeruser():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        sonderzeichen = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        password = request.form["password"]
        password_again = request.form["password_again"]

        if len(password) < 15:
            return render_template("registeruser.html", error_message="Password too short (min. 15 characters)")

        if not any(z in password for z in sonderzeichen):
            return render_template("registeruser.html", error_message="Password must contain a special character")

        if password != password_again:
            return render_template("registeruser.html", error_message="Passwords don't match")

        user = Register.query.filter_by(user_id=session["user_id"]).first()
        if not user:
            return redirect("/register")

        user.user_password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        user.user_registered = True
        db.session.commit()
        return redirect("/login")

    return render_template("registeruser.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        now = dt.datetime.today()
        username = request.form["username"]
        password = request.form["password"]

        user = Register.query.filter_by(user_name=username).first()
        if not user:
            return render_template("login.html", error_message="Wrong username or password")

        if user.user_locked_until and now < user.user_locked_until:
            return render_template("login.html", error_message=f"Account locked until {user.user_locked_until.strftime('%H:%M:%S')}")

        if user.user_locked_until and now >= user.user_locked_until:
            user.user_trys = 0
            user.user_locked_until = None
            db.session.commit()

        if not user.user_password_hash:
            return render_template("login.html", error_message="Wrong username or password")

        if bcrypt.checkpw(password.encode("utf-8"), user.user_password_hash):
            user.user_trys = 0
            user.user_locked_until = None
            session["user_id"] = user.user_id
            db.session.commit()
            return redirect("/index")

        user.user_trys = (user.user_trys or 0) + 1
        if user.user_trys >= 5:
            user.user_locked_until = dt.datetime.today() + dt.timedelta(minutes=15)
            db.session.commit()
            return render_template("login.html", error_message="Too many failed attempts. Account locked for 15 minutes.")

        db.session.commit()
        return render_template("login.html", error_message="Wrong username or password", username=username)

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/index", methods=["GET", "POST"])
def schicht_eintragen():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    if request.method == "POST":
        datum = request.form["datum"]
        zeit_anfang = request.form["zeit_anfang"]
        zeit_ende = request.form["zeit_ende"]
        datum_formatiert = dt.datetime.strptime(datum, "%Y-%m-%d").strftime("%d.%m.%Y")
        free = request.form.get("frei")

        if free:
            db.session.add(Date(user_id=user_id, date=datum_formatiert, free=True))
        else:
            db.session.add(Date(user_id=user_id, date=datum_formatiert, time_begin=zeit_anfang, time_end=zeit_ende, free=False))

        db.session.commit()
        return render_template("index.html", error_message="Shift saved successfully")

    return render_template("index.html")


def get_date():
    today = datetime.today()
    tomorrow = today + timedelta(days=1)
    return tomorrow.strftime("%d.%m.%Y"), today.strftime("%d.%m.%Y")


def get_shift_for_tomorrow(morgen_str, user_id):
    shift = Date.query.filter_by(user_id=user_id, date=morgen_str).first()
    work = False
    if shift:
        if shift.free:
            wake_time = "You are free tomorrow, sleep well."
        else:
            work = True
            wake_time = f"Sleep well, you will have to work tomorrow from {shift.time_begin} to {shift.time_end}."
    else:
        wake_time = "No shift found for tomorrow."
    return wake_time, work


def find_weather_data(user_id):
    user = Register.query.filter_by(user_id=user_id).first()
    key = os.getenv("OPENWEATHER_KEY")
    url = f"https://api.openweathermap.org/data/2.5/weather?q={quote(user.user_city)}&appid={key}&units=metric&lang=de"
    response = requests.get(url, timeout=10).json()
    return response["main"]["temp"], response["weather"][0]["description"], response["main"]["humidity"], response


def weather(response):
    mapping = {
        "Thunderstorm": emoji.emojize("There will be thunderstorms tomorrow :thunder_cloud_and_rain:"),
        "Drizzle": emoji.emojize("Light drizzle expected tomorrow. :cloud_with_rain:"),
        "Rain": emoji.emojize("It will rain tomorrow. :umbrella_with_rain_drops:"),
        "Snow": emoji.emojize("It will snow tomorrow :snowflake:"),
        "Atmosphere": emoji.emojize("It will be foggy tomorrow. :fog:"),
        "Clear": "Clear skies tomorrow.",
        "Clouds": "It will be cloudy tomorrow.",
    }
    return mapping.get(response["weather"][0]["main"], "")


def build_mail(work, temp, user_name, tomorrow_str, weather_text, wake_time):
    return f"""
    <html>
    <body style="font-family: -apple-system, Helvetica Neue, Arial, sans-serif;">
    <h1>Reminder for tomorrow ({tomorrow_str})</h1>
    <p>Good evening {user_name},</p>
    <p>{wake_time}</p>
    <p>{weather_text}</p>
    <p>{temp}°C</p>
    </body>
    </html>
    """


def send_daily_emails():
    tomorrow_str, _ = get_date()
    for user in Register.query.all():
        if not user.user_registered:
            continue
        wake_time, work = get_shift_for_tomorrow(tomorrow_str, user.user_id)
        temp, _, _, response = find_weather_data(user.user_id)
        weather_text = weather(response)
        mail_text = build_mail(work, temp, user.user_name, tomorrow_str, weather_text, wake_time)
        msg = Message(subject="Reminder for tomorrow", sender=os.getenv("gmail_email"), recipients=[user.user_mail])
        msg.html = mail_text
        mail.send(msg)


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host='0.0.0.0', port=5555, debug=debug_mode)
