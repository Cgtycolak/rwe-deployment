import os
import sys
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
from .data_fetcher import fetch_and_store_hydro_data, fetch_and_store_natural_gas_data, fetch_and_store_imported_coal_data

def update_daily_data(app):
    """Fetch and store data for today and tomorrow"""
    with app.app_context():
        today = datetime.now(timezone('Europe/Istanbul')).date()
        tomorrow = today + timedelta(days=1)
        
        # Fetch today's data
        app.logger.info(f"Fetching data for {today}")
        fetch_and_store_hydro_data(today)
        fetch_and_store_natural_gas_data(today)
        fetch_and_store_imported_coal_data(today)
        
        # Fetch tomorrow's data
        app.logger.info(f"Fetching data for {tomorrow}")
        fetch_and_store_hydro_data(tomorrow)
        fetch_and_store_natural_gas_data(tomorrow)
        fetch_and_store_imported_coal_data(tomorrow)

def init_scheduler(app):
    """Initialize the scheduler with proper timezone and error handling"""
    # Use a file lock to ensure only one scheduler instance runs
    try:
        scheduler = BackgroundScheduler(
            timezone=timezone('Europe/Istanbul'),
            job_defaults={
                'coalesce': True,  # Combine multiple missed runs into one
                'max_instances': 1  # Only allow one instance of each job to run
            }
        )
        
        # Schedule the update task to run at 16:45 every day
        scheduler.add_job(
            lambda: update_daily_data(app),
            trigger=CronTrigger(hour=16, minute=45),
            id='daily_data_update',
            name='Update heatmap data daily at 16:45',
            replace_existing=True,
            misfire_grace_time=900  # 15 minutes grace time for misfired jobs
        )
        
        # Add error listener
        def job_listener(event):
            if hasattr(event, 'code'):
                if event.code == EVENT_JOB_ERROR:
                    app.logger.error(f'Job failed: {event.job_id}')
                    if hasattr(event, 'traceback'):
                        app.logger.error(f'Error traceback: {event.traceback}')
                elif event.code == EVENT_JOB_EXECUTED:
                    app.logger.info(f'Job completed successfully: {event.job_id}')
                elif event.code == EVENT_JOB_MISSED:
                    app.logger.warning(f'Job missed scheduled run: {event.job_id}')
        
        scheduler.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED | EVENT_JOB_MISSED)
        
        scheduler.start()
        app.logger.info("Scheduler started. Daily updates scheduled for 16:45")
        
    except Exception as e:
        app.logger.error(f"Error starting scheduler: {str(e)}")