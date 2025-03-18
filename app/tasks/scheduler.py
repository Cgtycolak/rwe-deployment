import os
import sys
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_SUBMITTED,
    EVENT_SCHEDULER_STARTED,
    EVENT_SCHEDULER_SHUTDOWN,
    JobExecutionEvent
)
from ..scripts.populate_historical_data import populate_multiple_types

def update_daily_data(app):
    """Fetch and store data for today and tomorrow"""
    with app.app_context():
        today = datetime.now(timezone('Europe/Istanbul')).date()
        tomorrow = today + timedelta(days=1)
        
        # Fetch data for both days (don't store in local DB for scheduled updates)
        for date in [today, tomorrow]:
            app.logger.info(f"Fetching data for {date}")
            populate_multiple_types(date, local_db=False)

def init_scheduler(app):
    """Initialize the scheduler with proper timezone and error handling"""
    scheduler = BackgroundScheduler(timezone=timezone('Europe/Istanbul'))
    
    # Schedule the update task to run at 13:06 every day
    scheduler.add_job(
        lambda: update_daily_data(app),
        trigger=CronTrigger(hour=13, minute=6),
        id='daily_data_update',
        name='Update heatmap data daily at 13:06',
        replace_existing=True,
        misfire_grace_time=900  # 15 minutes grace time for misfired jobs
    )
    
    # Add error listener
    def job_listener(event):
        """Handle different types of scheduler events"""
        if hasattr(event, 'code'):
            if event.code == EVENT_JOB_ERROR and isinstance(event, JobExecutionEvent):
                app.logger.error(f'Job failed: {event.job_id}')
                app.logger.error(f'Error: {str(event.exception)}')
                app.logger.error(f'Traceback: {str(event.traceback)}')
            elif event.code == EVENT_JOB_EXECUTED:
                app.logger.info(f'Job completed: {event.job_id}')
            elif event.code == EVENT_JOB_SUBMITTED:
                app.logger.info(f'Job submitted: {event.job_id}')
            elif event.code == EVENT_SCHEDULER_STARTED:
                app.logger.info('Scheduler started')
            elif event.code == EVENT_SCHEDULER_SHUTDOWN:
                app.logger.info('Scheduler shutdown')
    
    # Add listener for specific events we want to monitor
    scheduler.add_listener(
        job_listener,
        EVENT_JOB_ERROR | 
        EVENT_JOB_EXECUTED | 
        EVENT_JOB_SUBMITTED |
        EVENT_SCHEDULER_STARTED |
        EVENT_SCHEDULER_SHUTDOWN
    )
    
    try:
        scheduler.start()
        app.logger.info("Scheduler started. Daily updates scheduled for 13:06")
    except Exception as e:
        app.logger.error(f"Error starting scheduler: {str(e)}")