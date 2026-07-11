# Shift Planner

A small Flask web app I built to keep track of my work shifts and get an
email reminder before each one, together with the next day's weather so I
know what to expect on the way to work.

## What it does

- Register with an email address and confirm it through a verification link
- Set a password (the form requires a minimum length and a special character)
- Add shifts with a start and end time, or mark a day as off
- List your saved shifts and delete the ones you no longer need
- Choose a city and a time of day in your profile
- At that time you get an email with your upcoming shift and the weather
  forecast for your city

Login is rate limited: after five wrong passwords the account is locked for
15 minutes.

## Tech stack

- Python and Flask
- Flask-SQLAlchemy (SQLite while developing, Postgres in production)
- Flask-Mail for the reminder emails
- Flask-WTF for CSRF protection
- bcrypt for password hashing
- APScheduler running in a separate worker that checks every minute whether a
  reminder is due
- OpenWeather API for the forecast

## Running it locally

Create a virtual environment and install the dependencies:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `example.env` to `.env` and fill in your own values (see below), then
start the app:

```
python app.py
```

It serves on http://localhost:5555. To actually send the reminder emails,
run the worker in a second terminal:

```
python worker.py
```

## Environment variables

The app reads these from a `.env` file:

- `gmail_email` – the Gmail address the reminders are sent from
- `gmail_password` – a Gmail app password for that address
- `openweather_key` – an API key from OpenWeather
- `secret_key` – a random string used to sign the sessions
- `DATABASE_URL` – optional Postgres URL; without it the app falls back to a
  local SQLite database
- `SESSION_COOKIE_SECURE` – set to `true` when serving over HTTPS

## Deployment

The `Procfile` runs the app under gunicorn as the web process and `worker.py`
as a background worker. That is the setup I use to deploy it on Railway with a
Postgres database.

## Screenshots

The `screenshots/` folder has two example reminder emails, one sent the
evening before a shift and one on the morning of it.
