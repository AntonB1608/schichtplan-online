import re
from dotenv import load_dotenv
import os
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import emoji
load_dotenv()

###def

#Datum, Uhrzeit finden
def hole_datum_heute():
    heute = datetime.today()
    morgen = heute + timedelta(days=1)
    morgen_str = morgen.strftime("%d.%m.%Y")
    return morgen_str

def extrahiere_zeit(text):
    muster = r"(\d{2}\.\d{2}\.\d{4})\s+([\d:freiF][\d:\-free i]+)"
    finden = list(re.finditer(muster, text))
    paare = []
    for m in finden:
        datum = m.group(1)
        zeit = m.group(2).strip()
        paare.append((datum, zeit))
    return paare

def finde_paar_heute(paare, morgen_str):  
    try: 
        for element in paare:
            if element[0] == morgen_str:
                datum = element[0]
                zeit = element[1]
        return datum, zeit
    except: 
        print(f"Es gibt keine Zeiteinträge für den {morgen_str}")

def finde_aufstehzeit_temp(zeit, temp, luftfeuchtigkeit):
    if "frei" in zeit:
        aufstehzeit_str = f"Morgen hast du frei, schlaf aus!"
    else: 
        erste_zeit = datetime.strptime(zeit.split("-")[0], "%H:%M")
        erste_zeit = erste_zeit.hour
        if erste_zeit <= 12:
            aufstehzeit = erste_zeit - 1
        else: 
            aufstehzeit = 10
        aufstehzeit_str = f"Schlaf gut, du musst morgen um {aufstehzeit} aufstehen." 
    temperatur = f"Es hat außerdem morgen voraussichtlich {temp}°C, mit einer Luftfeuchtigkeit von {luftfeuchtigkeit}%. ."
    return aufstehzeit_str, temperatur





def lese_datei(pfad):        
    with open(pfad, "r", encoding="utf-8") as f:
        return f.read()

def wähle_wetter_beschreibung(response):
    beschreibung = response["weather"][0]["main"]
    if beschreibung == "Thunderstorm": 
        wetter_text = emoji.emojize("Es gewittert morgen :thunder_cloud_and_rain:")
    elif beschreibung == "Drizzle":
        wetter_text = emoji.emojize("Es nieselt morgen leicht.:cloud_with_rain:")
    elif beschreibung == "Rain":
        wetter_text = emoji.emojize("Es wird morgen regnen.:umbrella_with_rain_drops:")
    elif beschreibung == "Snow":
        wetter_text = emoji.emojize("Es schneit morgen :snowflake:")
    elif beschreibung == "Atmosphere":
        wetter_text = emoji.emojize("Es wird nebelig morgen. :fog:")
    elif beschreibung == "Clear":
        wetter_text = emoji.emojize("Es wird morgen klar und wolkenlos")
    elif beschreibung == "Clouds":
        wetter_text = "Es wird morgen wolkig."
    else: 
        pass 
    return wetter_text



def erstelle_Mail_inhalt(aufstehzeit_str, temperatur, wetter_text, morgen_str, zeit, name):
    mailinhalt = f"""
    <html>
    <body style="font-family: Georgia;">
    <meta charset="UTF-8">
    <h1>Erinnerung für Morgen den {morgen_str}</h1>
    <Hallo {name}</p>
    <p>{aufstehzeit_str}</p>
    <p>Du arbeitest morgen von {zeit} Uhr</p>
    <p>{wetter_text}</p>
    <p>{temperatur}</p>
    </body>
    </html>
    """
    return mailinhalt



def erstelle_zweite_Mailinhalt(arbeit, zeit, name):
    if arbeit:
        zweitemailinhalt = f"""
        <html>
        <body style="font-family: Georgia;">
        <meta charset="UTF-8">
        <h1>Erinnerung für heute</h1>
        <p>Hallo {name},</p>
        <p> Du arbeitest heute um {zeit} Uhr.</p>
        </body>
        </html>
        """
    else: 
        zweitemailinhalt = f"""
        <html>
        <body style="font-family: Georgia;">
        <meta charset="UTF-8">
        <h1>Erinnerung für heute</h1>
        <p>Guten Morgen {name}</p>
        <p>Du arbeitest heute nicht. Genieße dein freien Tag!</p>
        </body>
        </html>
        """
    return zweitemailinhalt

def finde_wetterdaten(text):
    key = os.getenv("OPENWEATHER_KEY")
    url = f"https://api.openweathermap.org/data/2.5/weather?q=Mannheim&appid={key}&units=metric&lang=de"        
    response = requests.get(url)
    response = response.json()
    temp = response["main"]["temp"]
    beschreibung = response["weather"][0]["description"]
    luftfeuchtigkeit = response["main"]["humidity"]
    return temp, beschreibung, luftfeuchtigkeit, response


def bereite_Mail():
    gmail_passwort = os.getenv("GMAILPASSWORT")
    betreff = "Erinnerung für Morgen"
    empfaenger = os.getenv("GMAILEMAIL")
    absender = os.getenv("GMAILEMAIL")
    return gmail_passwort, betreff, empfaenger, absender, name

def bereite_zweite_Mail():
    gmail_passwort = os.getenv("GMAILPASSWORT")
    zweiter_betreff = "Erinnerung für Heute"
    empfaenger = os.getenv("GMAILEMAIL")
    absender = os.getenv("GMAILEMAIL")
    return gmail_passwort, zweiter_betreff, empfaenger, absender




def sende_erste_Mail(mailinhalt, absender, empfaenger, betreff, gmail_passwort):
    msg = MIMEText(mailinhalt, "html")
    msg["Subject"] = betreff
    msg["From"] = absender
    msg["To"] = empfaenger
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(absender, gmail_passwort)
        server.send_message(msg)
    print("Mail gesendet!")

def sende_zweite_Mail(zweite_mailinhalt, absender, empfaenger, zweiter_betreff, gmail_passwort):
    msg = MIMEText(zweite_mailinhalt, "html")
    msg["Subject"] = zweiter_betreff
    msg["From"] = absender
    msg["To"] = empfaenger
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(absender, gmail_passwort)
        server.send_message(msg)
    print("Zweite Mail gesendet!")


#main 



if __name__ == "__main__":
    text = lese_datei("/Users/macbook/Schichtplan_tool/schichten.txt")
    morgen_str = hole_datum_heute()
    paare = extrahiere_zeit(text)
    name = os.getenv("NAME")
    try:
        datum, zeit = finde_paar_heute(paare, morgen_str)
    except:
        print("Kein passender Eintrag für morgen vorhanden")
        exit()
    aufstehzeit_roh, arbeit = finde_aufstehzeit_temp(zeit, temp, luftfeuchtigkeit):
    temp, beschreibung, luftfeuchtigkeit, response = finde_wetterdaten(text)
    wetter_text = wähle_wetter_beschreibung(response)
    aufstehzeit_text, temperatur = finde_aufstehzeit_temp(aufstehzeit_roh, zeit, temp, luftfeuchtigkeit)
    mailinhalt = erstelle_Mail_inhalt(aufstehzeit_text, temperatur, wetter_text, morgen_str, zeit, name)
    zweite_mailinhalt = erstelle_zweite_Mailinhalt(arbeit, zeit, name)
    gmail_passwort, betreff, empfaenger, absender = bereite_Mail()
    gmail_passwort, zweiter_betreff, empfaenger, absender = bereite_zweite_Mail()
    sende_erste_Mail(mailinhalt, absender, empfaenger, betreff, gmail_passwort)
    sende_zweite_Mail(zweite_mailinhalt, absender, empfaenger, zweiter_betreff, gmail_passwort)