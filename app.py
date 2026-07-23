from flask import Flask, request, render_template, session, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
import bcrypt
from dotenv import load_dotenv
import os
from flask_wtf.csrf import CSRFProtect
import secrets
import requests
from datetime import datetime, timedelta, timezone
import emoji
from urllib.parse import quote
import re

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

    

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

with app.app_context():

    db.create_all()


@app.route("/register", methods=["POST", "GET"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]

        if len(username) > 20:

            return render_template ("register.html", error_message="Username too long")
        
        if not EMAIL_REGEX.match(email):

            return render_template("register.html", error_message="Invalid email address")
        
        existing_name = Register.query.filter_by(user_name=username).first()
        if existing_name and existing_name.user_registered:

            return render_template("register.html", error_message="Username already exists")
        
        existing_mail = Register.query.filter_by(user_mail=email).first()
        if existing_mail and existing_mail.user_registered:

            return render_template("register.html", error_message="Email already exists", user_name=username)
        
        for stale in {existing_name, existing_mail}:

            if stale is not None:

                Verification.query.filter_by(user_id=stale.user_id).delete()
                db.session.delete(stale)

        db.session.commit()
        token = secrets.token_urlsafe(64)
        new_user = Register(user_name=username, user_mail=email)
        db.session.add(new_user)
        try:

            db.session.commit()

        except IntegrityError:

            db.session.rollback()
            return render_template("verifyregister.html")

       
        verify_link = f"{request.url_root}verify/{token}"
        html = f"<p>Dear {username}, <a href='{verify_link}'>click here to verify your email</a></p>"
        to = email
        subject="Verify your email"
        send_email(to, subject, html)

        db.session.add(Verification(user_token=token, user_id=new_user.user_id))
        db.session.commit()
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

    if not request.method == "POST":
        return render_template("registeruser.html")
    
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

    


@app.route("/login", methods=["GET", "POST"])
def login():
    if not request.method == "POST":
        return render_template("login.html")

    now = datetime.today()
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
        if not user.user_city or not user.email_time:
            return redirect("/profile")
        else:
            return redirect("/index")
    

    user.user_trys = (user.user_trys or 0) + 1
    if user.user_trys >= 5:
        user.user_locked_until = datetime.today() + timedelta(minutes=15)
        db.session.commit()
        return render_template("login.html", error_message="Too many failed attempts. Account locked for 15 minutes.")

    db.session.commit()
    return render_template("login.html", error_message="Wrong username or password", username=username)

   

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/profile", methods=["POST", "GET"])
def show_profile():

    if "user_id" not in session:

        return redirect("/login")
    
    if not request.method == "POST":

        return render_template("profile.html")
    
    user_id = session["user_id"]
    email_time = request.form["email_time"]
    city = request.form["city"]
    if email_time and city:

        key = os.getenv("openweather_key")
        url = f"https://api.openweathermap.org/data/2.5/weather?q={quote(city)}&appid={key}&units=metric&lang=de"
        response = requests.get(url, timeout=10).json()
        if str(response.get("cod")) == "404":
            return render_template("profile.html", error_message="City not found")
        user = Register.query.filter_by(user_id=user_id).first()
        user.user_city = city
        user.user_time_zone = response["timezone"]
        user.email_time = email_time
        db.session.commit()
        return redirect("/index")
    
    if not email_time and not city:

        return render_template("profile.html", error_message = "Enter email_time and your city please.")
    
    elif not email_time and city:
    
        return render_template("profile.html", error_message =  "Enter email_time please.")
    
    elif email_time and not city:
    
        return render_template("profile.html", error_message = "Enter your city please")
    

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
        return render_template("index.html",good_message="Shift saved successfully")
    else:
        return render_template("index.html")


def get_date():
    today = datetime.today()
    tomorrow = today + timedelta(days=1)
    return tomorrow.strftime("%d.%m.%Y"), today.strftime("%d.%m.%Y")

def get_shift_for_tomorrow(morgen_str, user_id):
    shift = Date.query.filter_by(user_id=user_id, date=morgen_str).first()
    if shift:
        if shift.free:
            wake_time = "Hello, You are free tomorrow."
        else:
            wake_time = f"Hi, you will have to work tomorrow from {shift.time_begin} to {shift.time_end}."
    else:
        wake_time = "No shift found for tomorrow."
    return wake_time


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

def mail_line(temp, user_name, tomorrow_str, weather_text, wake_time):

    head_line = "<html><body style='font-family: -apple-system, Helvetica Neue, Arial, sans-serif;'>"
    main_line = f"<h1>Reminder for tomorrow ({tomorrow_str})</h1> <p>Good evening {user_name},</p>"
    work_line = f"<p>{wake_time}</p>"
    end_line = "</body></html>"
    if weather_text == "":

        weather_line = ""
        temp_line = ""

    if weather_text != "":

        weather_line = f"<p>{weather_text}</p>"
        temp_line = f"<p>The temperature will be {temp}."

    return head_line, main_line, end_line, weather_line, temp_line, work_line

def build_first_mail(head_line, main_line, end_line, weather_line, temp_line, work_line): 

    return f"""

        {head_line}
        {main_line}
        {work_line}
        {weather_line}
        {temp_line}
        {end_line}
        """

def build_second_mail(head_line, main_line, end_line, weather_line, temp_line, work_line):

    weather_line =  weather_line.replace("tomorrow", "today")
    main_line = main_line.replace("tomorrow", "today").replace("evening", "morning")
    work_line = work_line.replace("tomorrow", "today")

    return f"""

        {head_line}
        {main_line}
        {work_line}
        {temp_line}
        {end_line}
        """

def send_daily_emails():
    now = datetime.now(timezone.utc)
    for user in Register.query.all():
        
        print(f"checke user {user.user_name}: registered={user.user_registered}, email_time={user.email_time}, now={now}")
        
        if not user.user_registered:

            continue

        if not user.email_time:

            continue

        email_time = datetime.strptime(user.email_time, "%H:%M").time()
        
        
        right_now = now + timedelta(seconds=user.user_time_zone)
        right_now = right_now.time()
        if right_now < email_time: 

            continue
        tomorrow_str, today_str = get_date()
        wake_time = get_shift_for_tomorrow(tomorrow_str, user.user_id)
        weather_text, temp, time_zone = find_weather_data(user.user_id)
        head_line, main_line, end_line, weather_line, temp_line, work_line = mail_line(temp, user.user_name, tomorrow_str, weather_text, wake_time)
        if user.first_mail_send != today_str:
            html = build_first_mail(head_line, main_line, end_line, weather_line, temp_line, work_line)
            subject = "Reminder for tomorrow"
            to = user.user_mail
            send_email(to, subject, html)
            user.first_mail_send = today_str
            db.session.commit()

        if user.second_mail_send != today_str:
            html = build_second_mail(head_line, main_line, end_line, weather_line, temp_line, work_line)
            subject = "Reminder for today"
            to = user.user_mail
            send_email(to, subject, html)
            user.second_mail_send = today_str
            db.session.commit()

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

    shift = Date.query.filter_by(date_id=date_id, user_id=session["user_id"]).first()

    if shift:

        db.session.delete(shift)
        db.session.commit()

    return redirect("/shifts")

def scheduled_job():

    with app.app_context():

        send_daily_emails()
def send_email(to, subject, html):
    resp = requests.post(
        "https://api.resend.com/emails",
        headers= {"Authorization": f"Bearer {os.getenv('resend_api_key')}"},
        json={
            "from": "Anton <onboarding@resend.dev>",
            "to": [to],
            "subject": subject,
            "html": html,
        },
    )
    print(resp.status_code, resp.json())   
if __name__ == "__main__":

    app.run(host='0.0.0.0', port=5555, debug=debug_mode)