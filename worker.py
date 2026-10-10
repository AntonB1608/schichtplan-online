
from app import app, db, User, Shift, timedelta, send_email, build_action_mail, build_shift_rows, to_user_time
from datetime import datetime, timezone, time
from time import sleep


DRY_RUN = False # Set to True to test without sending emails


def tomorrow_window(now_user):
    """Fenster für 'morgen' in der LOKALEN Zeit des Nutzers – nicht in UTC.
    Sonst listet die Mail nachts die falschen Schichten (z.B. Erinnerung 00:30)."""
    start = datetime.combine(now_user.date() + timedelta(days=1), time(0, 0))
    return start, start + timedelta(days=1)


def run_once():

    with app.app_context():

        now_utc = datetime.now(timezone.utc)
        now = now_utc.replace(tzinfo=None)

        users = User.query.filter_by(shift_reminder_enabled=True).all()
        for user in users:
            now_user = to_user_time(now_utc, user.time_zone)

            shifts = Shift.query.filter(
                Shift.user_id == user.id,
                Shift.shift_reminder_sent_at == None,
                Shift.shift_type != "off",   # freie Tage lösen keine "Schicht beginnt"-Mail aus
                Shift.start > now_user,
                Shift.start <= now_user + timedelta(minutes=user.shift_reminder_lead_minutes),
            ).all()
            for shift in shifts:

                try:

                    subject = f"Erinnerung: deine Schicht beginnt um {shift.start.strftime('%H:%M')} Uhr"

                    html = build_action_mail(
                        subject=subject,
                        headline="Deine Schicht beginnt bald",
                        intro=f"Hallo {user.name}, deine Schicht beginnt um {shift.start.strftime('%H:%M')} Uhr.",
                        button_label="Meine Schichten ansehen",
                        link="https://www.shiftmates.org/shifts",
                        note="Erinnerungen kannst du in deinem Profil jederzeit abschalten.",
                        shifts_html=build_shift_rows([shift]),
                    )
                    if DRY_RUN:

                        print(f"WOULD SEND to {user.mail}: {subject}")
                        shift.shift_reminder_sent_at = now
                        db.session.commit()

                    else:

                        if send_email(user.mail, subject, html):
                            shift.shift_reminder_sent_at = now
                            db.session.commit()

                except Exception:
                    db.session.rollback()
                    continue


def run_daily():
    with app.app_context():

        now_utc = datetime.now(timezone.utc)
        users = User.query.filter_by(daily_reminder_enabled=True).all()
        for user in users:
            now_user = to_user_time(now_utc, user.time_zone)
            soll = datetime.combine(now_user.date(), user.daily_reminder_time.time())
            if now_user < soll or (user.daily_reminder_sent_at and user.daily_reminder_sent_at >= soll):                continue

            tomorrow, tomorrow_end = tomorrow_window(now_user)
            shifts = Shift.query.filter(
                Shift.user_id == user.id,
                Shift.shift_type != "off",   # freie Tage: keine Mail – Ruhe am freien Tag
                Shift.start >= tomorrow,
                Shift.start < tomorrow_end,
            ).order_by(Shift.start).all()

            if not shifts:
                continue  # morgen nichts zu tun -> keine Mail

            try:
                subject = "Erinnerung: deine Schichten für morgen"

                html = build_action_mail(
                    subject=subject,
                    headline="Deine Schichten für morgen",
                    intro=f"Hallo {user.name}, so sieht dein Tag morgen aus.",
                    button_label="Meine Schichten ansehen",
                    link="https://www.shiftmates.org/shifts",
                    note="Erinnerungen kannst du in deinem Profil jederzeit abschalten.",
                    shifts_html=build_shift_rows(shifts),
                )

                if DRY_RUN:

                    print(f"WOULD SEND to {user.mail}: {subject}")
                    user.daily_reminder_sent_at = now_user
                    db.session.commit()

                else:

                    if send_email(user.mail, subject, html):
                        user.daily_reminder_sent_at = now_user
                        db.session.commit()

            except Exception:
                db.session.rollback()
                continue


if __name__ == "__main__":
    while True:
        try:
            run_once()
            run_daily()
        except Exception as e:
            print(f"Worker error: {e}", flush=True)
        sleep(60)