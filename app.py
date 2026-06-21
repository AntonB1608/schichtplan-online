from flask import Flask, request, render_template, session, redirect
from flask_sqlalchemy import SQLAlchemy
import bcrypt
from dotenv import load_dotenv
import os
from flask_wtf.csrf import CSRFProtect
import secrets 
from flask_mail import Mail, Message
from datetime import datetime
import random
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

class User(db.Model):
    user_id = db.Column(db.Integer, primary_key = True)
    user_name = db.Column(db.String(40), unique = True, nullable = False, )
    user_mail = db.Column(db.String(40), unique = True, nullable = False)
    user_verification = db.Column(db.Boolean)
    user_password = db.Column(db.String, nullable = False)

class Date(db.Model):
    date_id = db.Column(db.Integer, primary_key = True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"))
    date = db.Column(db.String(10), nullable = False)
    time_begin = db.Column(db.String(12))
    time_end = db.Column(db.String(12))
    frei = db.Column(db.Boolean)


class Verification(db.Model):
    user_verification_id = db.Column(db.Integer, primary_key = True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"))
    token = db.Column(db.Integer)

@app.route("/register", methods =["POST", "GET"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        if len(username) > 20:
            return render_template("register.html", fehlermeldung="username too long")
        user_exists = User.query.filter_by(user_name=username).first()
        if not user_exists:
            email_exists = User.query.filter_by (user_mail = email).first()
            if not email_exists:
                new_user = User(user_name = username, user_mail = email)
                db.session.add(new_user)
                db.session.commit()
                return render_template("registeruser.html")
            else:
                render_template("register.html", error_message = "Error: email already exists", user_name = username)
        else:
            return render_template("register.html", error_message = "Error: username already exists.", email = email)
        
    else:
        return render_template("register.html")

@app.route("/registeruser", methods = ["POST"])
def registeruser():
    sonderzeichen = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
    password = request.form["password"]
    password_again = request.form["password_again"]
    if len(password) < 15:
        return render_template("register.html", fehlermeldung = "password to short", username=username)
    has_sonderzeichen = any(zeichen in password for zeichen in sonderzeichen)
    if not has_sonderzeichen:
        return render_template("register.html", fehlermeldung = "password doesn't contain sonderzeichen", username=username)
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    if password == password_again:
        new_password = User(user_password = password_hash)
        db.session.add(new_password)           
        db.session.commit()
        return redirect("/login")
    else:
        return render_template("registeruser.html", fehlermeldung = "passwords dont match", username=username, password=password)



@app.route("/schicht", methods=["POST"])
def schicht_eintragen():
    datum = request.form["datum"]
    zeit_anfang = request.form["zeit_anfang"]
    zeit_ende = request.form["zeit_ende"]
    datum_formatiert = datetime.strptime(datum, "%Y-%m-%d").strftime("%d.%m.%Y")
    frei = request.form.get("frei")
    if frei:
        new_date = Date(user_id = user_id, date = datum_formatiert, frei = True)
        db.session.add(new_date)           
        db.session.commit()
    else:
        new_date = Date(user_id = user_id, date = datum_formatiert, time_begin = zeit_anfang, time_end = zeit_ende, frei = False)
        db.session.add(new_date)           
        db.session.commit()
        



if __name__ == "__main__":
    app.run(host = '0.0.0.0', port = 5555, debug=True)
     