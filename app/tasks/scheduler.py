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
        # Get the application instance
        app = current_app._get_current_object()
        
        with app.app_context():
            today = datetime.now(timezone('Europe/Istanbul')).date()
            tomorrow = today + timedelta(days=1)
            
            app.logger.info("Starting daily update job")
            
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
    scheduler = BackgroundScheduler(timezone=timezone('Europe/Istanbul'))
    
    # Schedule the update task to run at 13:36 every day
    scheduler.add_job(
        update_daily_data,  # Remove the lambda and app parameter
        trigger=CronTrigger(hour=13, minute=36),
        id='daily_data_update',
        name='Update heatmap data daily at 13:36',
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
    
    # Add a test job
    scheduler.add_job(
        lambda: app.logger.info("Test job executed"),
        trigger=CronTrigger(second='*/30'),  # Runs every 30 seconds
        id='test_job',
        name='Test job every 30 seconds',
        replace_existing=True
    )
    
    try:
        scheduler.start()
        app.logger.info("Scheduler started. Daily updates scheduled for 13:36")
    except Exception as e:
        app.logger.error(f"Error starting scheduler: {str(e)}")