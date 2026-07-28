
# Shiftmates

Email reminders for your work shifts, with the weather for the city you
commute to. You save your shifts once; the app sends you a mail the evening
before and again on the morning of the shift.

I built it because I work rotating shifts and kept checking the plan on my
phone at 11pm.

**Live:** <https://shiftmates.org>

![Evening reminder](screenshots/evening-mail.png)

## Features
 
- Sign up with an email address, confirmed through a verification link
- Passwords hashed with bcrypt; login locks for 15 minutes after 5 failed attempts
- Password reset via a token that expires after one hour
- Add shifts with a start and end time, or mark a date as a day off
- Set your city and the time your reminders should arrive
- A background worker sends two reminders per shift, in your own timezone
- Weather forecast pulled from OpenWeather for the city on your profile

## Tech

| Layer | Choice |

|---|---|
| Web | Flask, Jinja2, gunicorn |
| Data | PostgreSQL in production, SQLite locally, SQLAlchemy + Alembic |
| Auth | bcrypt, Flask-WTF (CSRF), server-side sessions |
| Jobs | APScheduler in a separate worker process |
| Email | Resend API |
| Weather | OpenWeather API |
| Hosting | Railway |

## Architecture

Two processes run side by side, defined in the `Procfile`:

- **web** — the Flask app. Applies migrations on boot, then serves requests.
- **worker** — a blocking scheduler that wakes every minute, finds users whose
  reminder time has passed in their own timezone, and sends any mail not yet
  sent today.
They share the database but never call each other. The worker has no request
context, so everything it needs is passed in explicitly rather than read from
`request`.

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

- Store `Date.date` as a real `DATE` column instead of a formatted string, so
  shifts can be sorted and range-queried
- Retry failed sends instead of skipping the day
- Add tests around the reminder scheduling logic

## License

MIT
