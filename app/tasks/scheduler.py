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

def update_daily_data(app):
    """Fetch and store data for today and tomorrow (both first and current versions)"""
    try:
        with app.app_context():
            tz = timezone('Europe/Istanbul')
            current_time = datetime.now(tz)
            
            app.logger.info(f"Daily update job triggered at {current_time}")
            
            today = current_time.date()
            
            app.logger.info(f"Starting daily update job for date: {today}")
            
            # Fetch data for today (don't store in local DB for scheduled updates)
            app.logger.info(f"Fetching data for {today} (all versions)")
            try:
                populate_multiple_types(today, local_db=False, versions=['first', 'current'])
                app.logger.info(f"Successfully fetched all version data for {today}")
            except Exception as e:
                app.logger.error(f"Error fetching data for {today}: {str(e)}")
                raise
            
            app.logger.info("Daily update job completed successfully")
            
    except Exception as e:
        app.logger.error(f"Error in update_daily_data: {str(e)}")
        raise

def update_hourly_data(app):
    """Fetch and store current version data for today only"""
    try:
        with app.app_context():
            tz = timezone('Europe/Istanbul')
            current_time = datetime.now(tz)
            
            app.logger.info(f"Hourly update job triggered at {current_time}")
            
            today = current_time.date()
            
            app.logger.info(f"Starting hourly update job for date: {today}")
            
            # Fetch only current version data for today
            app.logger.info(f"Fetching current version data for {today}")
            try:
                populate_multiple_types(today, local_db=False, versions=['current'])
                app.logger.info(f"Successfully fetched current version data for {today}")
            except Exception as e:
                app.logger.error(f"Error fetching current data for {today}: {str(e)}")
                raise
            
            app.logger.info("Hourly update job completed successfully")
            
    except Exception as e:
        app.logger.error(f"Error in update_hourly_data: {str(e)}")
        raise

def init_scheduler(app):
    """Initialize the scheduler with proper timezone and error handling"""
    tz = timezone('Europe/Istanbul')
    scheduler = BackgroundScheduler(timezone=tz)
    
    # Log current time in both UTC and Istanbul time
    current_utc = datetime.utcnow()
    current_ist = datetime.now(tz)
    app.logger.info(f"Initializing scheduler at UTC: {current_utc}, Istanbul: {current_ist}")
    
    # Schedule the daily update task (runs once a day)
    daily_run = CronTrigger(hour=16, minute=5, timezone=tz)
    scheduler.add_job(
        update_daily_data,
        trigger=daily_run,
        id='daily_data_update',
        name='Update heatmap data daily at 16:05',
        args=[app],
        replace_existing=True,
        misfire_grace_time=900  # 15 minutes grace time for misfired jobs
    )
    
    # Schedule the hourly update task (runs every hour)
    hourly_run = CronTrigger(minute=33, timezone=tz)  # Run at 33 minutes past every hour
    scheduler.add_job(
        update_hourly_data,
        trigger=hourly_run,
        id='hourly_data_update',
        name='Update current version data hourly at :33',
        args=[app],
        replace_existing=True,
        misfire_grace_time=300  # 5 minutes grace time for misfired jobs
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
        app.logger.info(f"Scheduler started at {datetime.now(tz)}. Daily updates at 16:05, hourly updates at :30 past each hour")
    except Exception as e:
        app.logger.error(f"Error starting scheduler: {str(e)}")