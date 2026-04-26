import re
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

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