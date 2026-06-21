from flask import Flask, request, render_template, session, redirect
from flask_sqlalchemy import SQLAlchemy
import bcrypt
import datetime as dt
from dotenv import load_dotenv
import os
from flask_wtf.csrf import CSRFProtect
import secrets 
from flask_mail import Mail, Message

load_dotenv()
 
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///schichtplan.db"
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = os.getenv("GMAIL_USER")
app.config['MAIL_PASSWORD'] = os.getenv("GMAIL_PASSWORD")
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

db = SQLAlchemy(app)

class Register(db.Model):
    userid = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(40), unique = True, nullable = False, )
    usermail = db.Column(db.String(40), unique = True, nullable = False)
    userverification = db.Column(db.Boolean)
    userpassword = db.Column(db.String, nullable = False)
    userpasswordhash = db.Column(db.String)
    userlockeduntil = db.Column(db.String(40))
    usertrys = db.Column(db.String(5))


class Date(db.Model):
    dateid = db.Column(db.Integer, primary_key = True)
    userid = db.Column(db.Integer, db.ForeignKey("register.userid"))
    date = db.Column(db.String(10), nullable = False)
    timebegin = db.Column(db.String(12))
    timeend = db.Column(db.String(12))
    frei = db.Column(db.Boolean)


class Verification(db.Model):
    userverification_id = db.Column(db.Integer, primary_key = True)
    userid = db.Column(db.Integer, db.ForeignKey("register.userid"))
    token = db.Column(db.Integer)
with app.app_context():
    db.create_all()
@app.route("/register", methods =["POST", "GET"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        if len(username) > 20:
            return render_template("register.html", fehlermeldung="username too long")
        user_exists = Register.query.filter_by(username=username).first()
        if user_exists:
            return render_template("register.html", fehlermeldung = "username already exists")
        email_exists = Register.query.filter_by (usermail = email).first()
        if not email_exists:
            token = secrets.token_urlsafe(64)
            new_user = Register(username = username, usermail = email)
            db.session.add(new_user)
            db.session.commit()
            user_verification = Verification(token = token)
            db.session.add(user_verification)
            db.session.commit()
            msg = Message(
            subject="Verify your email",
            sender=os.getenv("GMAIL_USER"),
            recipients=[email]
            )
            msg.body = f" Dear {username}, /n Click this link to verify your email: http://localhost:5555/verify/{token}"
            mail.send(msg)
            return render_template("registeruser.html", fehlermeldung = "Verification email send.")
        else:
            return render_template("register.html", fehlermeldung = "Error: email already exists", user_name = username)
         
        
    else:
        return render_template("register.html")

@app.route("/registeruser", methods = ["POST"])
def registeruser():
    username = request.form["username"]
    user_exists = Register.query.filter_by(username = username)
    if not user_exists:
        return render_template("/registeruser.html", fehlermeldung = "User not found")
    sonderzeichen = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
    password = request.form["password"]
    password_again = request.form["password_again"]
    if len(password) < 15:
        return render_template("registeruser.html", fehlermeldung = "password to short")
    has_sonderzeichen = any(zeichen in password for zeichen in sonderzeichen)
    if not has_sonderzeichen:
        return render_template("registeruser.html", fehlermeldung = "password doesn't contain sonderzeichen")
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    if password == password_again:
        new_password = Register(user_password = password_hash)
        db.session.add(new_password)           
        db.session.commit()
        return redirect("/login")
    else:
        return render_template("registeruser.html", fehlermeldung = "passwords dont match", password=password)
@app.route("/login", methods = ["POST"])
def login():
    current_date_time = dt.datetime.today()
    username = request.form["username"]
    password = request.form["password"]
    user_exists = Register.query.filter_by(user_name=username).first()
    if user_exists:
        if Register.userlockeduntil and current_date_time < Register.userlockeduntil:
            return render_template("login.html", fehlermeldung=f"You are blocked until {user.locked_until}")
        if Register.userlockeduntil and current_date_time > Register.userlockeduntil:
            Register.usertrys = 0
            db.session.commit()
        if bcrypt.checkpw(password.encode("utf-8"), Register.userpasswordhash):
            User_user_locked_until = None
            session["username"] = username
            db.session.commit()
            return redirect("/index.html")
        User_user_trys += 1
        if Register.usertrys >= 5: 
            Register.userlocked_until = dt.datetime.today() + dt.timedelta(minutes=15)
            db.session.commit()
            return render_template("login.html", fehlermeldung=f"wrong password, you are blocked until {user.locked_until}", username=username)            
        db.session.commit()
        return render_template("login.html", fehlermeldung="wrong password", username=username)
    else:
        return render_template("login.html") 
        
@app.route('/verify/<token>')
def verifiy_user(token):    
    user = Register.query.filter_by(token = token).first()
    if not user:
        return "Invalid token"
    user.email_verified = True
    user.token = None
    session["username"] = user.username
    db.session.commit()
    return redirect("/registeruser.html")
           
@app.route("/schicht", methods=["POST"])
def schicht_eintragen():
    datum = request.form["datum"]
    zeit_anfang = request.form["zeit_anfang"]
    zeit_ende = request.form["zeit_ende"]
    datum_formatiert = datetime.strptime(datum, "%Y-%m-%d").strftime("%d.%m.%Y")
    frei = request.form.get("frei")
    if frei:
        new_date = Date(date = datum_formatiert, frei = True)
        db.session.add(new_date)           
        db.session.commit()
    else:
        new_date = Date(date = datum_formatiert, time_begin = zeit_anfang, time_end = zeit_ende, frei = False)
        db.session.add(new_date)           
        db.session.commit()
        



if __name__ == "__main__":
    app.run(host = '0.0.0.0', port = 5555, debug=True)
     