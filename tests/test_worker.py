"""Tests für den Reminder-Worker.

Decken genau die zwei Fehler ab, die in der Review gefunden wurden:
- freie Tage dürfen keine "Schicht beginnt"-Mail auslösen (run_once)
- "morgen" wird in der lokalen Zeit des Nutzers berechnet, nicht in UTC
"""
import os
import tempfile

# DB/Secrets setzen, BEVOR app importiert wird (app liest die Config beim Import).
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ.setdefault("secret_key", "test-secret")
os.environ.setdefault("resend_api_key", "test")

from datetime import datetime, timedelta, timezone

import pytest

import worker
from app import app, db, User, Shift, to_user_time


@pytest.fixture(autouse=True)
def fresh_db():
    with app.app_context():
        db.create_all()
    yield
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_tomorrow_window_uses_local_date():
    # Kurz nach Mitternacht: "morgen" muss der nächste LOKALE Tag sein.
    now_user = datetime(2026, 1, 15, 0, 30)
    start, end = worker.tomorrow_window(now_user)
    assert start.date() == datetime(2026, 1, 16).date()
    assert end - start == timedelta(days=1)


def test_run_once_skips_off_shifts(monkeypatch):
    recorded = []
    monkeypatch.setattr(worker, "send_email",
                        lambda to, subject, html, **kw: recorded.append((to, subject)) or True)

    with app.app_context():
        u = User(name="tester", mail="tester@example.de", mail_verified=True,
                 registration_completed=True, shift_reminder_enabled=True,
                 shift_reminder_lead_minutes=60, time_zone="Europe/Berlin")
        db.session.add(u)
        db.session.commit()

        now_user = to_user_time(datetime.now(timezone.utc), "Europe/Berlin")
        start = now_user + timedelta(minutes=30)  # liegt im Erinnerungsfenster

        off = Shift(user_id=u.id, start=start, end=start, shift_type="off")
        real = Shift(user_id=u.id, start=start, end=start + timedelta(hours=8), shift_type="early")
        db.session.add_all([off, real])
        db.session.commit()
        off_id, real_id = off.id, real.id

    worker.run_once()

    with app.app_context():
        # Echte Schicht: erinnert. Freier Tag: KEINE Mail, kein Zeitstempel.
        assert db.session.get(Shift, real_id).shift_reminder_sent_at is not None
        assert db.session.get(Shift, off_id).shift_reminder_sent_at is None

    assert recorded == [("tester@example.de", recorded[0][1])]
    assert len(recorded) == 1


def _daily_user():
    # Erinnerungszeit 00:00, damit das Zeit-Tor in run_daily immer offen ist.
    u = User(name="daily", mail="daily@example.de", mail_verified=True,
             registration_completed=True, daily_reminder_enabled=True,
             daily_reminder_time=datetime(2020, 1, 1, 0, 0), time_zone="Europe/Berlin")
    db.session.add(u)
    db.session.commit()
    return u


def test_run_daily_silent_on_day_off(monkeypatch):
    recorded = []
    monkeypatch.setattr(worker, "send_email",
                        lambda to, subject, html, **kw: recorded.append(to) or True)
    with app.app_context():
        u = _daily_user()
        now_user = to_user_time(datetime.now(timezone.utc), "Europe/Berlin")
        tmrw = now_user.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
        db.session.add(Shift(user_id=u.id, start=tmrw, end=tmrw, shift_type="off"))
        db.session.commit()

    worker.run_daily()
    assert recorded == []  # freier Tag -> keine Mail, Ruhe


def test_run_daily_sends_for_real_shift(monkeypatch):
    recorded = []
    monkeypatch.setattr(worker, "send_email",
                        lambda to, subject, html, **kw: recorded.append(to) or True)
    with app.app_context():
        u = _daily_user()
        now_user = to_user_time(datetime.now(timezone.utc), "Europe/Berlin")
        tmrw = now_user.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
        db.session.add(Shift(user_id=u.id, start=tmrw, end=tmrw + timedelta(hours=8), shift_type="early"))
        db.session.commit()

    worker.run_daily()
    assert recorded == ["daily@example.de"]  # echte Schicht -> genau eine Mail
