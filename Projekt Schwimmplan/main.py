import re
from dotenv import load_dotenv
import os
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta


def Datum():
    heute = datetime.today()
    morgen = heute + timedelta(days=1)
    morgen_str = morgen.strftime("%d.%m.%Y")
    return morgen_str


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

Datum()
def Mailchecken():
    text = datei_lesen("/Users/macbook/VS Code/Projekt Schwimmplan/schichten.txt")
    zeit_extrahieren(text)
    Datum_heute(result, morgen_str)
    key = os.getenv("OPENWEATHER_KEY")
    url = f"https://api.openweathermap.org/data/2.5/weather?q=Mannheim&appid={key}&units=metric&lang=de"        
    response = requests.get(url)
    response = response.json()
    temp = response["main"]["temp"]
    beschreibung = response["weather"][0]["description"]
    luftfeuchtigkeit = response["main"]["humidity"]
    return temp, beschreibung, luftfeuchtigkeit, response


def Mail_Vorbereitung():
    gmail_passwort = os.getenv("GMAILPASSWORT")
    betreff = "Erinnerung für Morgen"
    empfaenger = os.getenv("GMAILEMAIL")
    absender = os.getenv("GMAILEMAIL")
    return gmail_passwort, betreff, empfaenger, absender

def Mail_inhalt(aufstehzeit, temperatur):
    mailinhalt= f"{aufstehzeit} \n {temperatur}"
    return mailinhalt

def aufstehzeit(Aufstehzeit, zeit, temp, luftfeuchtigkeit):
    if "frei" in zeit:
        aufstehzeit = f"Morgen hast du frei, schlaf aus!"
    else:
        aufstehzeit = f"Schlaf gut, du musst morgen um {Aufstehzeit} aufstehen.\n" 
    temperatur = f"Es hat außerdem morgen voraussichtlich {temp}°C,\n mit einer Luftfeuchtigkeit von {luftfeuchtigkeit}%. ."
    return aufstehzeit, temperatur

def wetter_beschreibung(response):
    beschreibung = response["weather"][0]["main"]
    print(f"beschreibung")
    if beschreibung == "Thunderstorm": 
        wetter_beschreibung == f"Es gewittert morgen."
    elif beschreibung == "Drizzle":
        wetter_beschreibung == f"Es nieselt morgen leicht."
    elif beschreibung == "Rain":
        wetter_beschreibung == f"Es wird morgen regnen."
    elif beschreibung == "Snow":
        wetter_beschreibung == "Es schneit morgen!"
    elif beschreibung == "Atmosphere":
        wetter_beschreibung == f"Es wird nebelig morgen."
    elif beschreibung == "Clear":
        wetter_beschreibung == f"Es wird morgen klar und wolkenlos"
    elif beschreibung == "Clouds":
        wetter_beschreibung == "Es wird morgen wolkig."
    else: 
        pass 
    return wetter_beschreibung


def Mail(mailinhalt, absender, empfaenger, betreff, gmail_passwort):
    msg = MIMEText(mailinhalt)
    msg["Subject"] = betreff
    msg["From"] = absender
    msg["To"] = empfaenger
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(absender, gmail_passwort)
        server.setnd_message(msg)
    print("Mail gesendet!")

def Mail_verschicken(mailinhalt, absender, empfaenger, betreff, gmail_passwort, aufstehzeit, temperatur ):
    Mail_inhalt(aufstehzeit, temperatur)
    Mail(mailinhalt, absender, empfaenger, betreff, gmail_passwort)


#main 
load_dotenv()
text = datei_lesen("/Users/macbook/VS Code/Projekt Schwimmplan/schichten.txt")
morgen_str = Datum()
result = zeit_extrahieren(text)
datum, zeit = Datum_heute(result, morgen_str)
temp, beschreibung, luftfeuchtigkeit, response = Mailchecken()
Aufstehzeit = Aufstehen(zeit)

gmail_passwort, betreff, empfaenger, absender = Mail_Vorbereitung()
aufstehzeit_text, temperatur = aufstehzeit(Aufstehzeit, zeit, temp, luftfeuchtigkeit)
mailinhalt = Mail_inhalt(aufstehzeit_text, temperatur)
Mail_verschicken(mailinhalt, absender, empfaenger, betreff, gmail_passwort, aufstehzeit_text, temperatur)
