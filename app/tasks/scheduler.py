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
from flask import current_app

def update_daily_data():
    """Fetch and store data for today and tomorrow"""
    try:
        # Use the app context
        with current_app.app_context():
            app = current_app._get_current_object()
            tz = timezone('Europe/Istanbul')
            current_time = datetime.now(tz)
            
            app.logger.info(f"Update daily data triggered at {current_time}")
            
            today = current_time.date()
            tomorrow = today + timedelta(days=1)
            
            app.logger.info(f"Starting daily update job for dates: {today} and {tomorrow}")
            
            # Fetch data for both days (don't store in local DB for scheduled updates)
            for date in [today, tomorrow]:
                app.logger.info(f"Fetching data for {date}")
                try:
                    populate_multiple_types(date, local_db=False)
                    app.logger.info(f"Successfully fetched data for {date}")
                except Exception as e:
                    app.logger.error(f"Error fetching data for {date}: {str(e)}")
                    raise
            
            app.logger.info("Daily update job completed successfully")
            
    except Exception as e:
        current_app.logger.error(f"Error in update_daily_data: {str(e)}")
        raise

def init_scheduler(app):
    """Initialize the scheduler with proper timezone and error handling"""
    tz = timezone('Europe/Istanbul')
    scheduler = BackgroundScheduler(timezone=tz)
    
    # Log current time in both UTC and Istanbul time
    current_utc = datetime.utcnow()
    current_ist = datetime.now(tz)
    app.logger.info(f"Initializing scheduler at UTC: {current_utc}, Istanbul: {current_ist}")
    
    # Schedule test job to run every minute to verify scheduler is working
    scheduler.add_job(
        lambda: app.logger.info(f"Test job executed at {datetime.now(tz)}"),
        trigger=CronTrigger(second='*/30', timezone=tz),
        id='test_job',
        name='Test job every 30 seconds',
        replace_existing=True
    )
    
    # Schedule the main update task
    next_run = CronTrigger(hour=14, minute=27, timezone=tz)
    scheduler.add_job(
        update_daily_data,
        trigger=next_run,
        id='daily_data_update',
        name='Update heatmap data daily at 14:27',
        replace_existing=True,
        misfire_grace_time=900  # 15 minutes grace time for misfired jobs
    )
    
    # Add error listener
    def job_listener(event):
        """Handle different types of scheduler events"""
        if hasattr(event, 'code'):
            current_time = datetime.now(tz)
            if event.code == EVENT_JOB_ERROR and isinstance(event, JobExecutionEvent):
                app.logger.error(f'Job failed at {current_time}: {event.job_id}')
                app.logger.error(f'Error: {str(event.exception)}')
                app.logger.error(f'Traceback: {str(event.traceback)}')
            elif event.code == EVENT_JOB_EXECUTED:
                app.logger.info(f'Job completed at {current_time}: {event.job_id}')
            elif event.code == EVENT_JOB_SUBMITTED:
                app.logger.info(f'Job submitted at {current_time}: {event.job_id}')
            elif event.code == EVENT_SCHEDULER_STARTED:
                app.logger.info(f'Scheduler started at {current_time}')
                for job in scheduler.get_jobs():
                    app.logger.info(f"Next run for job '{job.name}': {job.next_run_time}")
            elif event.code == EVENT_SCHEDULER_SHUTDOWN:
                app.logger.info(f'Scheduler shutdown at {current_time}')
    
    # Add listener for specific events
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
        app.logger.info(f"Scheduler started at {datetime.now(tz)}. Daily updates scheduled for 14:27 Istanbul time")
    except Exception as e:
        app.logger.error(f"Error starting scheduler: {str(e)}")