# Shiftmates
 
**Live:** https://www.shiftmates.org
 
Email reminders for your work shifts
You save your shifts once; the app sends you a mail the day before and again a few minutes before your shift begins. 

You can set the reminder time the day before individually. 
At the reminder a few minute before your shifts, you can choose between 30–180 minutes, shipping this week for the worker. 

I built it because I worked rotating shifts and kept checking the plan on my phone at 11pm. 

## Features
 
- Sign up with an email address, confirmed through a verification link, tokens expire
- Passwords hashed with bcrypt; login locks for 15 minutes after 5 failed attempts
- Password reset via a token that expires after one hour
- Add shifts with a start and end time, or mark a date as a day off
- Add shifttypes or note to each shifts if you want
- Set your city and the two times your reminders should arrive
- A background worker sends the reminders in each user's own timezone
- Weather forecast pulled from OpenWeather for the city on your profile
- Turn reminders off at any time, from the app or from a link in every email

## Tech
 
| Layer | Choice |
|---|---|
| Web | Flask, Jinja2, gunicorn |
| Data | PostgreSQL in production, SQLite locally, SQLAlchemy + Alembic |
| Auth | bcrypt, Flask-WTF (CSRF), server-side sessions |
| Jobs | APScheduler in a separate worker process |
| Email | Resend API, hand-written table-based HTML |
| Hosting | Railway, custom domain with SPF, DKIM and DMARC |

## Architecture
 
Two processes run side by side, defined in the `Procfile`:
 
- **web** — the Flask app. Applies migrations on boot, then serves requests.
- **worker** — a blocking scheduler that wakes every minute, finds users whose
  reminder time has passed in their own timezone, and sends
  any mail not yet sent today.
After a complete mail that is send the worker marks the reminer with sent_at. 
I chose to make the time stamp after the mail was send. Not before the mail was send because here you have in the worst case 2 mails send. 
They share the database but never call each other. The worker runs without a request context, so everything it needs is passed in explicitly rather than read from `request` — an early version read `request.form` inside a helper the worker
called, which meant no reminder was ever sent.
 
The two reminders are scheduled against a window rather than a threshold. 

## Running it locally
 
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
 
cp example.env .env      # then fill in your own values
flask db upgrade         # creates the local SQLite database
python app.py            # http://localhost:5555
```
 
To send reminders, run the worker in a second terminal:
 
```bash
python worker.py
```
 
## Environment variables
 
| Variable | Purpose |
|---|---|
| `secret_key` | Signs the session cookie. Any long random string. |
| `resend_api_key` | API key from resend.com |
| `openweather_key` | API key from openweathermap.org |
| `DATABASE_URL` | Postgres URL. Falls back to local SQLite if unset. |
| `SESSION_COOKIE_SECURE` | `true` when serving over HTTPS |
| `FLASK_DEBUG` | `true` during development only |
 
## What I would change next
 
- Include weather description for the next day
- Building teams with leader who each have different rights in the process of setting shifts


## Notes
 
Built as a personal side project while working full-time, before starting a
Business Informatics degree in September 2026.
 
## License
 
MIT