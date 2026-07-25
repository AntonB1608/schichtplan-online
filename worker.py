from apscheduler.schedulers.blocking import BlockingScheduler
from app import app, send_daily_emails

def job():
    with app.app_context():
        send_daily_emails()

scheduler = BlockingScheduler()
scheduler.add_job(job, "interval", minutes=1)
scheduler.start()