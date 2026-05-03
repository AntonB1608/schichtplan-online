import re
from dotenv import load_dotenv
import os
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
load_dotenv()
def Datum():
    heute = datetime.today()
    morgen = heute + timedelta(days=1)
    morgen_str = morgen.strftime("%d.%m.%Y")
    return morgen_str

def wetter():
    key = os.getenv("OPENWEATHER_KEY")
    url = f"https://api.openweathermap.org/data/2.5/weather?q=Mannheim&appid={key}&units=metric&lang=de"
    response = requests.get(url)
    response = response.json()
    temp = response["main"]["temp"]
    beschreibung = response["weather"][0]["description"]
    luftfeuchtigkeit = response["main"]["humidity"]
    return temp, beschreibung, luftfeuchtigkeit

def datei_lesen(pfad):
    with open(pfad, "r", encoding="utf-8") as f:
        return f.read()

def zeit_extrahieren(text):
    muster = r"(\d{2}\.\d{2}\.\d{4})\s+([\d:freiF][\d:\-free i]+)"
    matches = list(re.finditer(muster, text))
    result = []
    for m in matches:
        datum = m.group(1)
        zeit = m.group(2).strip()
        result.append((datum, zeit))
    return result

def Datum_heute(result, morgen_str):  
    datum = None
    zeit = None
    for element in result:
        if element[0] == morgen_str:
            datum = element[0]
            zeit = element[1]
    return datum, zeit

def Aufstehen(zeit):
    if "frei" in zeit:
        Aufstehzeit = "Du kannst heute ausschlafen!"
    elif "06:00" in zeit:
        Aufstehzeit = "5 Uhr!"
    elif "07:00" in zeit:
        Aufstehzeit = "6 Uhr!"
    elif "08:00" in zeit:
        Aufstehzeit = "7 Uhr!"
    else:
        Aufstehzeit = "7:30!"
    return Aufstehzeit

def Mail_Inhalt(Aufstehzeit, zeit, temp, beschreibung, luftfeuchtigkeit):
    gmail_passwort = os.getenv("GMAILPASSWORT")
    betreff = "Erinnerung für Morgen"
    empfaenger = os.getenv("GMAILEMAIL")
    absender = os.getenv("GMAILEMAIL")
    if "frei" in zeit:
        inhalt = f"Morgen hast du frei, schlaf aus!"
    else:
        inhalt = f"Schlaf gut, du musst morgen um {Aufstehzeit} aufstehen. Du arbeitest von {zeit} Uhr. Es hat morgen voraussichtlich {temp}°C mit einer Luftfeuchtigkeit von {luftfeuchtigkeit}%. Das Wetter wird {beschreibung}."
    return inhalt, absender, empfaenger, betreff, gmail_passwort

def Mail(inhalt, absender, empfaenger, betreff, gmail_passwort):
    msg = MIMEText(inhalt)
    msg["Subject"] = betreff
    msg["From"] = absender
    msg["To"] = empfaenger
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(absender, gmail_passwort)
        server.send_message(msg)
    print("Mail gesendet!")