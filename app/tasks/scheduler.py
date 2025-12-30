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
from ..scripts.dpp_charts.populate_historical_data import populate_multiple_types
from flask import current_app

def update_daily_data(app):
    """Fetch and store data for today and attempt tomorrow if available"""
    try:
        with app.app_context():
            tz = timezone('Europe/Istanbul')
            current_time = datetime.now(tz)
            
            app.logger.info(f"Daily update job triggered at {current_time}")
            
            today = current_time.date()
            tomorrow = today + timedelta(days=1)
            
            app.logger.info(f"Starting daily update job for date: {today}")
            
            # # Fetch data for today (don't store in local DB for scheduled updates)
            # app.logger.info(f"Fetching data for {today} (all versions)")
            # try:
            #     populate_multiple_types(today, local_db=False, versions=['first', 'current'])
            #     app.logger.info(f"Successfully fetched all version data for {today}")
            # except Exception as e:
            #     app.logger.error(f"Error fetching data for {today}: {str(e)}")
            #     # Don't raise here, so we can still try tomorrow's data
            
            # Try to fetch tomorrow's data, but don't fail the job if it's not available
            app.logger.info(f"Attempting to fetch data for {tomorrow} (all versions)")
            try:
                populate_multiple_types(tomorrow, local_db=False, versions=['first', 'current'])
                app.logger.info(f"Successfully fetched all version data for {tomorrow}")
            except Exception as e:
                app.logger.warning(f"Could not fetch data for {tomorrow}: {str(e)}")
                app.logger.info("This is expected if tomorrow's data is not yet available")
                # Don't raise here, it's okay if tomorrow's data isn't available yet
            
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

def update_realtime_data(app):
    """Fetch and store realtime data for yesterday"""
    try:
        with app.app_context():
            tz = timezone('Europe/Istanbul')
            current_time = datetime.now(tz)
            yesterday = (current_time - timedelta(days=1)).date()
            
            app.logger.info(f"Realtime update job triggered at {current_time}")
            app.logger.info(f"Fetching realtime data for {yesterday}")
            
            # Import here to avoid circular imports
            from ..scripts.dpp_charts.populate_realtime_data import populate_realtime_data
            
            for plant_type in ['hydro', 'natural_gas', 'lignite']:
                try:
                    populate_realtime_data(plant_type, yesterday, yesterday, local_db=False)
                    app.logger.info(f"Successfully updated realtime data for {plant_type}")
                except Exception as e:
                    app.logger.error(f"Error updating realtime data for {plant_type}: {str(e)}")
            
            app.logger.info(f"Realtime update completed for {yesterday}")
            
    except Exception as e:
        app.logger.error(f"Error in update_realtime_data: {str(e)}")
        raise

def send_daily_email_report(app):
    """Send daily heatmap email report"""
    try:
        with app.app_context():
            tz = timezone('Europe/Istanbul')
            current_time = datetime.now(tz)
            tomorrow = (current_time + timedelta(days=1)).date()  # CHANGED: Send tomorrow's data
            
            app.logger.info(f"Email report job triggered at {current_time}")
            app.logger.info(f"Sending heatmap report for {tomorrow}")
            
            # Check which email service to use
            email_service_type = os.environ.get('EMAIL_SERVICE', 'smtp')
            
            if email_service_type == 'sendgrid':
                # Use SendGrid (no personal email needed)
                app.logger.info("Using SendGrid email service")
                from ..services.sendgrid_email_service import SendGridEmailService
                email_service = SendGridEmailService(app)
            else:
                # Use SMTP (Gmail or other)
                app.logger.info("Using SMTP email service")
                from ..services.email_service import EmailService
                email_service = EmailService(app)
            
            success = email_service.send_daily_heatmap_report(tomorrow)  # CHANGED: Send tomorrow's data
            
            if success:
                app.logger.info(f"Successfully sent daily email report for {tomorrow}")
            else:
                app.logger.error(f"Failed to send daily email report for {tomorrow}")
            
    except Exception as e:
        app.logger.error(f"Error in send_daily_email_report: {str(e)}")
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
        misfire_grace_time=900  # 15 minutes grace time
    )
    
    # Schedule retry update task for data that might not be available at 16:05
    daily_retry = CronTrigger(hour=16, minute=45, timezone=tz)
    scheduler.add_job(
        update_daily_data,
        trigger=daily_retry,
        id='daily_data_retry',
        name='Retry heatmap data update at 16:45',
        args=[app],
        replace_existing=True,
        misfire_grace_time=900  # 15 minutes grace time
    )
    
    # Schedule the hourly update task (runs every hour)
    hourly_run = CronTrigger(minute=30, timezone=tz)  # Run at 30 minutes past every hour
    scheduler.add_job(
        update_hourly_data,
        trigger=hourly_run,
        id='hourly_data_update',
        name='Update current version data hourly at :30',
        args=[app],
        replace_existing=True,
        misfire_grace_time=300  # 5 minutes grace time
    )
    
    # Schedule realtime update task (runs twice a day)
    realtime_morning = CronTrigger(hour=5, minute=0, timezone=tz)  # Run at 05:00
    realtime_noon = CronTrigger(hour=12, minute=0, timezone=tz)    # Run at 12:00
    
    # Add morning job
    scheduler.add_job(
        update_realtime_data,
        trigger=realtime_morning,
        id='realtime_data_update_morning',
        name='Update realtime data at 05:00',
        args=[app],
        replace_existing=True,
        misfire_grace_time=900  # 15 minutes grace time
    )
    
    # Add noon job
    scheduler.add_job(
        update_realtime_data,
        trigger=realtime_noon,
        id='realtime_data_update_noon',
        name='Update realtime data at 12:00',
        args=[app],
        replace_existing=True,
        misfire_grace_time=900  # 15 minutes grace time
    )
    
    # Schedule daily email report (runs at 16:10 every day)
    email_report = CronTrigger(hour=16, minute=10, timezone=tz)
    scheduler.add_job(
        send_daily_email_report,
        trigger=email_report,
        id='daily_email_report',
        name='Send daily heatmap email at 16:10',
        args=[app],
        replace_existing=True,
        misfire_grace_time=900  # 15 minutes grace time
    )
    
    # Schedule daily email report retry update task for data that might not be available at 16:10
    email_report_retry = CronTrigger(hour=16, minute=50, timezone=tz)
    scheduler.add_job(
        send_daily_email_report,
        trigger=email_report_retry,
        id='daily_email_report_retry',
        name='Retry send daily heatmap email at 16:40',
        args=[app],
        replace_existing=True,
        misfire_grace_time=900  # 15 minutes grace time
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
        app.logger.info(f"Scheduler started at {datetime.now(tz)}. Daily updates at 16:05 (retry at 16:45), hourly updates at :30, realtime updates at 05:00 and 12:00, email report at 16:10")
    except Exception as e:
        app.logger.error(f"Error starting scheduler: {str(e)}")