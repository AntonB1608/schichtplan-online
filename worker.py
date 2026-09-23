
from app import app, db, User, Shift, timedelta, send_email, build_action_mail, build_shift_rows
from datetime import datetime, timezone, time


DRY_RUN = False # Set to True to test without sending emails


def run_once():

    with app.app_context():

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        users = User.query.filter_by(shift_reminder_enabled=True).all()
        for user in users:
            now_local = now + timedelta(seconds=int(user.time_zone or 0))
            shifts = Shift.query.filter(
                Shift.user_id == user.id,
                Shift.shift_reminder_sent_at == None,
                Shift.start > now_local,
                Shift.start <= now_local + timedelta(minutes=user.shift_reminder_lead_minutes),
            ).all()
            for shift in shifts:

                try:

                    subject = f"Reminder: your shift starts at {shift.start.strftime('%H:%M')}"

                    html = build_action_mail(
                        subject=subject,
                        headline="Your shift starts soon",
                        intro=f"Hi {user.name}, your shift starts at {shift.start.strftime('%H:%M')}.",
                        button_label="View my shifts",
                        link="https://www.shiftmates.org/shifts",
                        note="You can turn reminders off in your profile settings.",
                        shifts_html=build_shift_rows([shift]),
                    )
                    if DRY_RUN:

                        print(f"WOULD SEND to {user.mail}: {subject}")

                    else:

                        if send_email(user.mail, subject, html):
                            shift.shift_reminder_sent_at = now
                            db.session.commit()

                except Exception:
                    db.session.rollback()
                    continue


def run_daily():
    with app.app_context():

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        users = User.query.filter_by(daily_reminder_enabled=True).all()
        for user in users:

            soll = datetime.combine(now.date(), user.daily_reminder_time.time())
            if now< soll:
                continue

            tomorrow = datetime.combine(now.date() + timedelta(days=1), time(0, 0))
            shifts = Shift.query.filter(
                Shift.user_id == user.id,
                Shift.daily_reminder_sent_at == None,
                Shift.start >= tomorrow,
                Shift.start < tomorrow + timedelta(days=1),
            ).order_by(Shift.start).all()

            if not shifts:
                continue

            try:
                if all(shift.shift_type == "off" for shift in shifts):
                    subject = "Reminder: you are free tomorrow"

                    html = build_action_mail(
                        subject=subject,
                        headline="You are free tomorrow",
                        intro=f"Hi {user.name}, nothing planned for tomorrow. Enjoy your day off!",
                        button_label="View my shifts",
                        link="https://www.shiftmates.org/shifts",
                        note="You can turn reminders off in your profile settings.",
                    )
                else:
                    subject = "Reminder: your shifts for tomorrow"

                    html = build_action_mail(
                        subject=subject,
                        headline="Your shifts for tomorrow",
                        intro=f"Hi {user.name}, here is what tomorrow looks like.",
                        button_label="View my shifts",
                        link="https://www.shiftmates.org/shifts",
                        note="You can turn reminders off in your profile settings.",
                        shifts_html=build_shift_rows(shifts),
                    )

                if DRY_RUN:

                    print(f"WOULD SEND to {user.mail}: {subject}")

                else:

                    if send_email(user.mail, subject, html):
                        for shift in shifts:
                            shift.daily_reminder_sent_at = now
                        db.session.commit()

            except Exception:
                db.session.rollback()
                continue


if __name__ == "__main__":
    run_once()
    run_daily()