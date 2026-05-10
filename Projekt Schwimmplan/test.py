from datetime import datetime, timedelta
import re

def hole_Datum_heute():
    heute = datetime.today()
    morgen = heute + timedelta(days=1)
    morgen_str = morgen.strftime("%d.%m.%Y")
    return morgen_str

def extrahiere_zeit(text,morgen_str):
    try: 
        muster = r"(\d{2}\.\d{2}\.\d{4})\s+([\d:freiF][\d:\-free i]+)"
        finden = list(re.finditer(muster, text))
        Paare = []
        for m in finden:
            datum = m.group(1)
            zeit = m.group(2).strip()
            Paare.append((datum, zeit))
        return Paare
    except:
        print(f"Fehler: Es gibt keine Zeiteinträge für den {morgen_str}!")

def finde_Paar_heute(Paare, morgen_str):  
    for element in Paare:
        if element[0] == morgen_str:
            datum = element[0]
            zeit = element[1]
    return datum, zeit

