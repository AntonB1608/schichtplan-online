# Bedrohungsmodell (Threat Model) — Shiftmates

> Sicherheit ist kein Zustand, den man erreicht, sondern ein Risiko, das man
> laufend steuert. Dieses Dokument hält fest, **welche Daten** Shiftmates hält,
> **warum**, welche **Risiken** daraus entstehen und mit welchen **Maßnahmen**
> wir sie senken. Es verspricht ausdrücklich **keine** hundertprozentige
> Sicherheit — das kann niemand seriös versprechen.

Stand: 2026-09-30

---

## 1. Warum Shiftmates sicherheitskritisch ist, obwohl es harmlos aussieht

Shiftmates erinnert Menschen an ihre Arbeitsschichten. Klingt banal. Aber ein
Schichtplan ist in Wahrheit eine **Anwesenheits- bzw. Abwesenheitsinformation**:
er verrät, wann eine Person **nicht zu Hause** ist. Damit rücken die Daten in die
Nähe von Standortdaten und werden zu einem möglichen Werkzeug für Einbruch oder
Stalking.

Diese Einordnung ist die Grundlage aller weiteren Entscheidungen: Wir behandeln
die Daten so, wie es ihre Sensibilität verlangt — nicht so, wie die App auf den
ersten Blick wirkt.

---

## 2. Schützenswerte Werte (Assets), nach Priorität

1. **Der Schichtplan (Zeiten)** — die Kern-Abwesenheitsinformation. Das eigentlich
   sensible Gut.
2. **Die E-Mail-Adresse** — zugleich Identifikator und Zustellkanal. Nicht
   entfernbar (die App *muss* mailen können), daher besonders zu schützen.
3. **Zugangsdaten** — Passwort-Hash und Session. Der Schlüssel zu allem oben.

---

## 3. Datenbestand & Datensparsamkeit (Feld für Feld)

Leitfrage für **jedes** Feld — nicht „könnte es bei einem Leak schaden?" (das
könnte alles), sondern:

> **„Zahlt dieses Datum seine Miete? Macht es das Produkt für den Nutzer spürbar
> besser — und überwiegt dieser Nutzen das Risiko?"**

| Feld | Zweck | Nutzen | Risiko bei Leak | Entscheidung |
|------|-------|--------|-----------------|--------------|
| `username` | Login & Anzeige | hoch | gering (Pseudonym, **keine** Klarnamen) | **behalten** |
| `email` | Zustellung der Erinnerungen | hoch (ist das Produkt) | mittel–hoch (Identifikator) | **behalten & schützen** |
| `password_hash` | Authentifizierung | hoch | gering (bcrypt, gesalzen) | **behalten** |
| Schichten (`start`/`end`/`shift_type`) | Kernfunktion | maximal | hoch (Abwesenheitszeiten) | **behalten & schützen** |
| `note` (Freitext) | Zusatzinfo pro Schicht | mittel | mittel (Nutzer könnten Orte eintragen) | **behalten, Nutzung lenken** (keine Adressen) |
| `time_zone` | korrekte Sendezeit der Erinnerung | hoch | gering (deckt große Region ab) | **behalten** |
| `city` | *nur* zur Ableitung der Zeitzone (+ Wetter) | ~0 (Zeitzone gibt es gratis aus dem Browser) | **hoch (konkreter Ort)** | **ENTFERNT** |

### Der `city`-Fall als Musterbeispiel

Die Stadt wurde **nicht aus Angst** entfernt, sondern aus einer nüchternen
Rechnung: Ihr einziger dauerhafter Zweck war die Ableitung der Zeitzone. Die
Zeitzone liefert der Browser des Nutzers kostenlos
(`Intl.DateTimeFormat().resolvedOptions().timeZone`). Damit steht dem **hohen
Risiko** (ein konkreter Ort pro Nutzer) praktisch **kein Nutzen** gegenüber. Ein
Feld, das viel Risiko und fast keinen Wert bringt, wird gestrichen — unabhängig
davon, ob man sich vor Angreifern fürchtet oder nicht. Das optionale
Wetter-Feature, das ebenfalls die Stadt nutzte, entfällt bewusst zugunsten der
Datensparsamkeit.

### Bewusst NICHT erhoben

Echter Name · Wohnadresse · Telefonnummer · genauer Standort/GPS · Geburtsdatum.
Daten, die wir nicht haben, kann niemand stehlen.

---

## 4. Angreifer — wer, und was sie wollen

| Angreifer | Ziel | Wichtigste Gegenmaßnahme |
|-----------|------|--------------------------|
| **Massen-/Gelegenheitsangreifer** (automatisiert, will viele leichte Ziele) | irgendein verwertbarer Datensatz | Ortsdaten entfernt → Massen-Leak wird nahezu wertlos |
| **Gezielter Angreifer** (kennt das Opfer, will dessen Plan) | Abwesenheitszeiten einer bestimmten Person | Kontoschutz + DB-Schutz (E-Mail bleibt Ansatzpunkt, siehe Restrisiko) |
| **Neugieriger Insider / Betreiber** | Bewegungsprofile der Nutzer | Datensparsamkeit + minimale Zugriffsrechte |
| **Automatisierte Bots** | Credential Stuffing, Scannen, Spam | Rate-Limiting, Lockout, aktuelle Abhängigkeiten |

---

## 5. Zwei Angriffsebenen (die Blast-Radius-Logik)

- **Ebene 1 — ein Konto übernehmen.** Kostet einen Nutzer. Wege: schwaches
  Passwort, Credential Stuffing, Phishing. Türen: Auth-Endpunkte.
- **Ebene 2 — die ganze Datenbank abgreifen.** Kostet *alle* Nutzer auf einmal
  und macht den Betreiber haftbar. Wege: geleakte DB-Zugangsdaten, ungeschütztes
  Backup, kompromittierter Hoster. **Dies ist das Worst-Case-Szenario.**

Konsequenz: Der größte Hebel ist nicht, jede einzelne Tür perfekt zu machen,
sondern dafür zu sorgen, dass hinter der Tür **möglichst wenig Wertvolles** liegt
(Datensparsamkeit) und das Verbliebene **verschlüsselt** ist.

---

## 6. Die drei Hebel — Status

### 6.1 Wahrscheinlichkeit senken (Angriffe teuer machen)
- [x] Passwörter mit **bcrypt** (gesalzen), nie im Klartext
- [x] **CSRF-Schutz** (Flask-WTF) auf allen Formularen
- [x] Durchgängiges **ORM** → keine SQL-Injection
- [x] **Login-Lockout** nach 5 Fehlversuchen (15 Min)
- [x] Jinja2-**Autoescape** an → kein Stored-XSS im Browser
- [ ] **Rate-Limiting** für Registrierung / Passwort-Reset / Login *(geplant)*
- [ ] **Generische Fehlermeldungen** gegen Konto-/E-Mail-Enumeration *(geplant)*
- [ ] Lockout zusätzlich **IP-basiert** absichern (verhindert gezielten Aussperr-DoS) *(geplant)*

### 6.2 Schaden begrenzen (Blast Radius)
- [x] **Keine Klarnamen** — nur Pseudonym-Usernames
- [~] **Keine Ortsdaten** — Stadt entfernt, nur Zeitzone bleibt *(in Umsetzung)*
- [x] **Wenige Felder** insgesamt
- [ ] **Verschlüsselung im Ruhezustand** über gemanagte Infrastruktur *(prüfen/sicherstellen)*
- [ ] Freitext-`note` gegen Ortsangaben lenken *(geplant)*

### 6.3 Erkennen & reagieren
- [~] Logging von Fehlern *(teilweise; keine Secrets/Response-Bodies loggen)*
- [ ] **Breach-Benachrichtigungsplan** — Nutzer im Ernstfall informieren können *(geplant)*
- [ ] Automatische **Backups** auf gemanagter, verschlüsselter Infrastruktur *(sicherstellen)*

---

## 7. Restrisiko (ehrlich)

Datensparsamkeit bringt uns weit, aber **nicht auf null** — denn *irgendetwas*
muss die App zum Funktionieren behalten. Die **E-Mail-Adresse** ist dieses
irreduzible Etwas: Wer Erinnerungen mailen will, braucht eine echte, zustellbare
Adresse. Man kann das Ziel eines Briefes nicht anonymisieren.

Daraus folgt das bewusst akzeptierte Restrisiko: Ein **gezielter** Angreifer, der
ein Konto übernimmt oder die Datenbank erbeutet, kann über die E-Mail eine Person
identifizieren und deren Abwesenheitszeiten ableiten. Für den **Massen**-Angreifer
ist der Datensatz durch die entfernten Ortsdaten dagegen weitgehend wertlos.

Die E-Mail wird deshalb nicht *minimiert*, sondern *bewacht*: Verschlüsselung im
Ruhezustand, minimale Zugriffsrechte, und der Grundsatz „wir gehen von einem
Breach aus".

---

## 8. Was wir ausdrücklich NICHT versprechen

- Kein „unhackbar", kein „100 % sicher".

Was wir versprechen: **so wenig wie möglich speichern**, **das Gespeicherte
schützen**, und im Ernstfall **ehrlich benachrichtigen**.

---

## 9. Offene Punkte / Roadmap

1. Rate-Limiting für `/register`, `/reset`, `/login` (E-Mail-Bombing, Kostenmissbrauch, Brute-Force)
2. Generische Fehlermeldungen + Dummy-Hash bei Login (Anti-Enumeration)
3. Lockout zusätzlich IP-basiert (gegen gezielten Aussperr-DoS)
4. Ortsdaten entfernen: `city` streichen, Zeitzone aus dem Browser (behebt zugleich einen Sommer-/Winterzeit-Bug)
5. `SESSION_COOKIE_SECURE` in Produktion hart auf `true`
6. `SECRET_KEY` beim Start erzwingen (Fail-Fast statt stillem `None`)
7. Security-Header setzen (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy)
8. `user.name` beim Mail-Versand escapen + Username-Zeichensatz beschränken
9. Freitext-`note` gegen Ortsangaben lenken
10. Abhängigkeiten aktuell halten (Supply-Chain-Risiko)
