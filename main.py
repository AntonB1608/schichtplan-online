import weather
from dotenv import load_dotenv
import os 

load_dotenv()
def weather(response):
    weather_description = response["weather"][0]["main"]
    if weather_description == "Thunderstorm": 
        weather_text = emoji.emojize("Es gewittert morgen :thunder_cloud_and_rain:")
    elif weather_description == "Drizzle":
        weather_text = emoji.emojize("Es nieselt morgen leicht.:cloud_with_rain:")
    elif weather_description == "Rain":
        weather_text = emoji.emojize("Es wird morgen regnen.:umbrella_with_rain_drops:")
    elif weather_description == "Snow":
        weather_text = emoji.emojize("Es schneit morgen :snowflake:")
    elif weather_description == "Atmosphere":
        weather_text = emoji.emojize("Es wird nebelig morgen. :fog:")
    elif weather_description == "Clear":
        weather_text = emoji.emojize("Es wird morgen klar und wolkenlos")
    elif weather_description == "Clouds":
        weather_text = "Es wird morgen wolkig."
    else: 
        weather_text = ""
    return weather_text

def find_weather_data(user_id):
    user = Register.query.filter_by(user_id = user_id).first()
    key = os.getenv("OPENWEATHER_KEY")
    url = f"https://api.openweathermap.org/data/2.5/weather?q=Mannheim&appid={key}&units=metric&lang=de"        
    response = requests.get(url)
    response = response.json()
    temp = response["main"]["temp"]
    description = response["weather"][0]["description"]
    humidity = response["main"]["humidity"]
    return temp, description, humidity, response
















def erstelle_Mail_inhalt(aufstehzeit_str, temperatur, wetter_text, morgen_str, zeit, name):
    mailinhalt = f"""
    <html>
    <body style="font-family: Georgia;">
    <meta charset="UTF-8">
    <h1>Erinnerung für Morgen den {morgen_str}</h1>
    <p>Hallo {name}</p>
    <p>{aufstehzeit_str}</p>
    <p>Du arbeitest morgen von {zeit} Uhr</p>
    <p>{wetter_text}</p>
    <p>{temperatur}</p>
    </body>
    </html>
    """
    return mailinhalt



def erstelle_zweite_Mailinhalt(arbeit, zeit, name, heute_str):
    if arbeit:
        zweitemailinhalt = f"""
        <html>
        <body style="font-family: Georgia;">
        <meta charset="UTF-8">
        <h1>Erinnerung für heute den {heute_str}</h1>
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
        <h1>Erinnerung für heute den {heute_str}</h1>
        <p>Guten Morgen {name}</p>
        <p>Du arbeitest heute nicht. Genieße dein freien Tag!</p>
        </body>
        </html>
        """
    return zweitemailinhalt




def bereite_Mail():
    gmail_passwort = os.getenv("GMAILPASSWORT")
    empfaenger = absender = os.getenv("GMAILEMAIL")
    return gmail_passwort, empfaenger, absender




def sende_erste_Mail(mailinhalt, absender, empfaenger, gmail_passwort, heute_str):
    msg = MIMEText(mailinhalt, "html")
    betreff = f"Erinnerung für morgen, den {morgen_str}"
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
    zweiter_betreff = f"Erinnerung für heute, den {heute_str}"
    msg["Subject"] = zweiter_betreff
    msg["From"] = absender
    msg["To"] = empfaenger
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(absender, gmail_passwort)
        server.send_message(msg)
    print("Zweite Mail gesendet!")

if __name__ == "__main__":
    text = lese_datei("/Users/macbook/Schichtplan_tool/schichten.txt")
    morgen_str, heute_str = hole_datum_heute()
    paare = extrahiere_zeit(text)
    name = os.getenv("NAME")
    try:
        datum, zeit = finde_paar_heute(paare, morgen_str)
    except:
        print("Kein passender Eintrag für morgen vorhanden")
        exit()
    try: 
        temp, beschreibung, luftfeuchtigkeit, response = finde_wetterdaten(text)
        wetter_text = wähle_wetter_beschreibung(response)
        aufstehzeit_str, temperatur, arbeit = finde_aufstehzeit_temp(zeit, temp, luftfeuchtigkeit)
        mailinhalt = erstelle_Mail_inhalt(aufstehzeit_str, temperatur, wetter_text, morgen_str, zeit, name)
        zweite_mailinhalt = erstelle_zweite_Mailinhalt(arbeit, zeit, name)
        gmail_passwort, empfaenger, absender = bereite_Mail()
        sende_erste_Mail(mailinhalt, absender, empfaenger, gmail_passwort, heute_str)
        sende_zweite_Mail(zweite_mailinhalt, absender, empfaenger, morgen_str, gmail_passwort)
    except Exception as e:
        print(f"Fehler: {e}")