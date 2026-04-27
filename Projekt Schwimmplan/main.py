import re
from dotenv import load_dotenv
import os
import requests
import smtplib
from email.mime.text import MIMEText

os.chdir(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()
def wetter():
    key = os.getenv("OPENWEATHER_KEY")
    url = f"https://api.openweathermap.org/data/2.5/weather?q=Mannheim&appid={key}&units=metric&lang=de"
    response = requests.get(url)
    response = response.json()
    weather = []
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
    print(result)
text = datei_lesen("/Users/macbook/VS Code/Projekt Schwimmplan/schichten.txt")
zeit_extrahieren(text)
temp, beschreibung, luftfeuchtigkeit = wetter()
print(f"Wetter in Mannheim: {temp}°C, {beschreibung}, Luftfeuchtigkeit: {luftfeuchtigkeit}%")