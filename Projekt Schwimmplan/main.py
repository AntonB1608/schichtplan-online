import func

morgen_str = func.Datum()                        # ← fehlte komplett

text = func.datei_lesen("/Users/macbook/VS Code/Projekt Schwimmplan/schichten.txt")
result = func.zeit_extrahieren(text)
temp, beschreibung, luftfeuchtigkeit = func.wetter()
datum, zeit = func.Datum_heute(result, morgen_str)   # ← morgen_str ergänzt

Aufstehzeit = func.Aufstehen(zeit)

inhalt, absender, empfaenger, betreff, gmail_passwort = func.Mail_Inhalt(Aufstehzeit, zeit, temp, beschreibung, luftfeuchtigkeit)  # ← Aufstehzeit ergänzt

func.Mail(inhalt, absender, empfaenger, betreff, gmail_passwort)