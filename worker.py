
from app import app, db, User, Shift, timedelta, send_email, build_action_mail
from datetime import datetime, timezone


DRY_RUN = True


def run_once():

    with app.app_context():

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        users = User.query.filter_by(shift_reminder_enabled=True).all()
        for user in users:
            shifts = Shift.query.filter(
                Shift.user_id == user.id,
                Shift.shift_reminder_sent_at == None,
                Shift.start > now,
                Shift.start <= now + timedelta(minutes=user.shift_reminder_lead_minutes),
            ).all()
            for shift in shifts:

                try:

                    subject = f"Reminder: your shift starts at {shift.start.strftime('%H:%M')}"
                    
                    html = build_action_mail(

                        subject=subject
                        ,
                        headline="Your shift starts soon"
                        ,
                        intro=f"Hi {user.name}, your {shift.shift_type} shift starts at {shift.start.strftime('%H:%M')}."
                        ,
                        button_label="View my shifts"
                        ,
                        link="https://www.shiftmates.org/shifts"
                        ,
                        note="You can turn reminders off in your profile settings."
                        ,

                    )
                    if DRY_RUN:

                        print(f"WOULD SEND to {user.mail}: {subject}")

                    else:

                        send_email(user.mail, subject, html)

                    shift.shift_reminder_sent_at = now
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    continue

        
if __name__ == "__main__":
    run_once()
    