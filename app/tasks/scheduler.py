import os
import sys
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from ..tasks.data_fetcher import update_daily_data

def update_daily_data(app):
    """Update data for yesterday"""
    from app.scripts.populate_historical_data import populate_heatmap_data  # Import here to avoid circular import
    
    # Get yesterday's date
    yesterday = datetime.now().date() - timedelta(days=1)
    
    # Update each type of data
    plant_types = ['hydro', 'natural_gas', 'imported_coal']
    
    with app.app_context():
        for plant_type in plant_types:
            try:
                print(f"Updating {plant_type} data for {yesterday}")
                populate_heatmap_data(plant_type, yesterday, yesterday)
            except Exception as e:
                print(f"Error updating {plant_type} data: {str(e)}")
                with open('scheduler_error.log', 'a') as f:
                    f.write(f"{datetime.now()},{plant_type},{str(e)}\n")

def init_scheduler(app):
    """Initialize the scheduler with the daily update task"""
    scheduler = BackgroundScheduler(timezone=timezone('Europe/Istanbul'))
    
    # Schedule the update task to run at 16:05 every day
    # to fetch next day's data
    scheduler.add_job(
        lambda: update_daily_data(app, fetch_next_day=True),  # Added parameter
        trigger=CronTrigger(hour=16, minute=5),
        id='daily_data_update',
        name='Update heatmap data daily at 16:05 for next day',
        replace_existing=True
    )
    
    def job_listener(event):
        if event.code == EVENT_JOB_ERROR:
            print(f'Job failed: {event.job_id}')
            print(f'Exception: {event.exception}')
            print(f'Traceback: {event.traceback}')
            
            with open('scheduler_error.log', 'a') as f:
                f.write(f"{datetime.now()},JOB_FAILED,{event.job_id},{str(event.exception)}\n")
        elif event.code == EVENT_JOB_EXECUTED:
            print(f'Job completed: {event.job_id}')
    
    scheduler.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)
    
    try:
        scheduler.start()
        print("Scheduler started. Daily updates scheduled for 16:05 (fetching next day's data)")
    except Exception as e:
        print(f"Error starting scheduler: {str(e)}")
        with open('scheduler_error.log', 'a') as f:
            f.write(f"{datetime.now()},SCHEDULER_START_ERROR,{str(e)}\n")