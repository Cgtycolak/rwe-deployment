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
from apscheduler.triggers.date import DateTrigger
from ..scripts.dpp_charts.populate_historical_data import populate_multiple_types
from flask import current_app

# Delays (minutes from the previous attempt) used when the email job finds the
# DPP data incomplete. EPIAS sometimes publishes rows full of zeros before the
# real values land, which is how empty reports used to go out at 16:10.
# Attempts land at 16:10, 16:20, 16:40, 17:20 and 18:20 — the last delay is 60
# rather than a doubled 80 so the window closes exactly at 18:20.
EMAIL_RETRY_DELAYS_MINUTES = [10, 20, 40, 60]

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

def check_heatmap_completeness(date):
    """
    Check whether the first-version DPP data backing the email report is usable.

    Must be called inside an app context. A type counts as incomplete when it is
    missing rows (EPIAS returned nothing for some plants) or when every value is
    zero (EPIAS published placeholder rows). Only the 'first' version is checked
    because that is the only version the email renders.

    Returns:
        list[str]: human-readable descriptions of incomplete types, empty if all good
    """
    from sqlalchemy import func
    from ..database.config import db
    from ..models.heatmap import (
        HydroHeatmapData,
        NaturalGasHeatmapData,
        ImportedCoalHeatmapData,
        LigniteHeatmapData
    )
    from ..mappings import hydro_mapping, plant_mapping, import_coal_mapping, lignite_mapping

    type_specs = [
        ('Natural Gas', NaturalGasHeatmapData, plant_mapping),
        ('Import Coal', ImportedCoalHeatmapData, import_coal_mapping),
        ('Hydro', HydroHeatmapData, hydro_mapping),
        ('Lignite', LigniteHeatmapData, lignite_mapping)
    ]

    problems = []
    for label, model, mapping in type_specs:
        expected_rows = len(mapping['plant_names']) * 24
        rows, total = db.session.query(
            func.count(),
            func.coalesce(func.sum(model.value), 0)
        ).filter(
            model.date == date,
            model.version == 'first'
        ).one()

        if rows < expected_rows:
            problems.append(f"{label}: {rows}/{expected_rows} rows present")
        elif total == 0:
            problems.append(f"{label}: all {rows} values are zero")

    return problems


def send_daily_email_report(app, attempt=1):
    """
    Send the daily heatmap email report, retrying with backoff on incomplete data.

    EPIAS does not always have tomorrow's DPP ready when the 16:05 population job
    runs, and populate_multiple_types stores whatever it gets — so the data can be
    missing or all zeros at 16:10. Rather than mail out an empty report, refetch and
    reschedule on the EMAIL_RETRY_DELAYS_MINUTES backoff. On the final attempt the
    report goes out regardless, flagged with whatever is still incomplete, so a bad
    day is visible to recipients instead of silently skipped.

    Args:
        app: Flask app
        attempt: 1-based attempt number; drives the backoff schedule
    """
    try:
        with app.app_context():
            tz = timezone('Europe/Istanbul')
            current_time = datetime.now(tz)
            tomorrow = (current_time + timedelta(days=1)).date()
            max_attempts = len(EMAIL_RETRY_DELAYS_MINUTES) + 1

            app.logger.info(
                f"Email report job triggered at {current_time} "
                f"(attempt {attempt}/{max_attempts})"
            )

            # Retries refetch first — the whole point is to pick up data that
            # EPIAS published after the previous attempt.
            if attempt > 1:
                app.logger.info(f"Refetching DPP data for {tomorrow} before retrying")
                try:
                    populate_multiple_types(tomorrow, local_db=False, versions=['first', 'current'])
                except Exception as e:
                    app.logger.warning(f"Refetch failed for {tomorrow}: {str(e)}")

            problems = check_heatmap_completeness(tomorrow)

            if problems and attempt < max_attempts:
                delay = EMAIL_RETRY_DELAYS_MINUTES[attempt - 1]
                next_run = current_time + timedelta(minutes=delay)
                app.logger.warning(
                    f"DPP data for {tomorrow} incomplete ({'; '.join(problems)}). "
                    f"Retrying at {next_run.strftime('%H:%M')} "
                    f"(attempt {attempt + 1}/{max_attempts})"
                )

                scheduler = app.config.get('SCHEDULER')
                if scheduler is None:
                    app.logger.error("No scheduler available to retry; sending report as-is")
                else:
                    scheduler.add_job(
                        send_daily_email_report,
                        trigger=DateTrigger(run_date=next_run, timezone=tz),
                        id=f'daily_email_report_retry_{tomorrow}_{attempt + 1}',
                        name=f'Retry heatmap email for {tomorrow} (attempt {attempt + 1})',
                        args=[app, attempt + 1],
                        replace_existing=True,
                        max_instances=1,
                        misfire_grace_time=900
                    )
                    return

            if problems:
                app.logger.error(
                    f"DPP data for {tomorrow} still incomplete after {attempt} attempts "
                    f"({'; '.join(problems)}). Sending report with a warning."
                )
            else:
                app.logger.info(f"DPP data for {tomorrow} complete; sending heatmap report")

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

            success = email_service.send_daily_heatmap_report(tomorrow, data_warnings=problems)

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

    # send_daily_email_report queues its own backoff retries through this
    app.config['SCHEDULER'] = scheduler

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
        max_instances=1,
        misfire_grace_time=900  # 15 minutes grace time
    )

    # The old 16:45 'daily_data_retry' job was removed: send_daily_email_report
    # now refetches tomorrow's data itself before each backoff retry, so a second
    # unconditional population job only risked racing it on the same rows.

    # Schedule the hourly update task (runs every hour)
    hourly_run = CronTrigger(minute=30, timezone=tz)  # Run at 30 minutes past every hour
    scheduler.add_job(
        update_hourly_data,
        trigger=hourly_run,
        id='hourly_data_update',
        name='Update current version data hourly at :30',
        args=[app],
        replace_existing=True,
        max_instances=1,
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
        max_instances=1,
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
        max_instances=1,
        misfire_grace_time=900  # 15 minutes grace time
    )

    # Schedule daily email report (runs at 16:10 every day)
    email_report = CronTrigger(hour=16, minute=10, timezone=tz)
    scheduler.add_job(
        send_daily_email_report,
        trigger=email_report,
        id='daily_email_report',
        name='Send daily heatmap email at 16:10 (retries on incomplete data)',
        args=[app, 1],
        replace_existing=True,
        max_instances=1,
        coalesce=True,          # collapse multiple missed fires into one run
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
        app.logger.info(f"Scheduler started at {datetime.now(tz)}. Daily updates at 16:05, hourly updates at :30, realtime updates at 05:00 and 12:00, email report at 16:10 (retries with refetch until 18:20 if data is incomplete)")
    except Exception as e:
        app.logger.error(f"Error starting scheduler: {str(e)}")