
from app import app, db, User, Shift
def run_once():
    with app.app_context():
        users = User.query.filter_by(shift_reminder_enabled=True).all()
        for user in users:
            shifts = Shift.query.filter(
            Shift.user_id == user.id,
            Shift.shift_reminder_sent_at == None,
            Shift.start > now,
            Shift.start <= now + timedelta(minutes=user.shift_reminder_lead_minutes)
        ).all()
if __name__ == "__main__":
    run_once()
    