import os
import sys
import argparse
from datetime import datetime, timedelta
import time
import requests
import pytz
import json
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import text
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from sqlalchemy import create_engine

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(parent_dir)

from app.factory import create_app
from app.database.config import db
from app.models.demand import DemandData
from app.functions import get_tgt_token
from app.scripts.cao_charts.populate_demand_data import parse_datetime

def setup_session():
    """Set up a requests session with retry logic"""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504, 429],
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def fetch_missing_dates(missing_dates):
    """Fetch data for missing dates"""
    app = create_app()
    with app.app_context():
        # Get TGT token
        tgt_token = get_tgt_token(
            app.config.get('USERNAME'),
            app.config.get('PASSWORD')
        )
        
        # Set up session
        session = setup_session()
        
        # Group dates by day
        days = {}
        for date_str in missing_dates:
            dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
            day = dt.strftime('%Y-%m-%d')
            if day not in days:
                days[day] = []
            days[day].append(dt)
        
        print(f"Grouped {len(missing_dates)} missing dates into {len(days)} days")
        
        # Process each day
        success_count = 0
        failure_count = 0
        failed_dates = []
        
        for day, dates in days.items():
            print(f"Processing {day} with {len(dates)} missing hours")
            
            try:
                # Fetch data for the entire day
                request_data = {
                    "startDate": f"{day}T00:00:00+03:00",
                    "endDate": f"{day}T23:59:59+03:00",
                    "region": "TR1"
                }
                
                response = session.post(
                    "https://seffaflik.epias.com.tr/electricity-service/v1/consumption/data/realtime-consumption",
                    json=request_data,
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': "application/json",
                        'TGT': tgt_token
                    },
                    timeout=30
                )
                
                if response.status_code != 200:
                    print(f"Error fetching data: {response.status_code}")
                    failure_count += len(dates)
                    failed_dates.extend([dt.strftime('%Y-%m-%d %H:%M') for dt in dates])
                    continue
                
                items = response.json().get('items', [])
                
                # Prepare batch data
                batch_data = []
                
                # Process each item in the response
                for item in items:
                    try:
                        # Get date and hour from the response
                        date_str = item.get('date', '')
                        hour_str = item.get('hour', '00:00')
                        
                        # Parse datetime
                        dts = [parse_datetime(date_str, hour_str)]
                        if not dts or dts[0] is None:
                            continue
                        
                        # Try each possible datetime
                        for dt in dts:
                            if dt.hour in [d.hour for d in dates]:
                                record_data = {
                                    'datetime': dt,
                                    'consumption': float(item.get('consumption', 0))
                                }
                                batch_data.append(record_data)
                                break
                    except Exception as e:
                        print(f"Error processing item: {e}")
                        continue
                
                # Insert batch data using upsert
                if batch_data:
                    try:
                        stmt = insert(DemandData).values(batch_data)
                        stmt = stmt.on_conflict_do_update(
                            constraint='demand_data_datetime_key',
                            set_={
                                'consumption': stmt.excluded.consumption
                            }
                        )
                        
                        db.session.execute(stmt)
                        db.session.commit()
                        
                        print(f"Successfully stored {len(batch_data)} records for {day}")
                        success_count += len(batch_data)
                    except Exception as e:
                        db.session.rollback()
                        print(f"Error committing data: {e}")
                        failure_count += len(dates)
                        failed_dates.extend([dt.strftime('%Y-%m-%d %H:%M') for dt in dates])
                else:
                    print(f"No matching data found for {day}")
                    failure_count += len(dates)
                    failed_dates.extend([dt.strftime('%Y-%m-%d %H:%M') for dt in dates])
            
            except Exception as e:
                print(f"Error processing day {day}: {e}")
                failure_count += len(dates)
                failed_dates.extend([dt.strftime('%Y-%m-%d %H:%M') for dt in dates])
            
            # Sleep to avoid rate limiting
            time.sleep(1)
        
        print(f"\nFetching complete: {success_count} successes, {failure_count} failures")
        if failed_dates:
            print(f"Failed dates: {failed_dates[:10]}...")

def sync_to_production():
    """Sync local database to production"""
    app = create_app()
    with app.app_context():
        # Create a connection to the production database
        prod_db_uri = "postgresql://rwe_user:yzxKIZVU8y32aMMF2vK5OXPXlWxOxWKC@dpg-cv7v6p5umphs73fu4ijg-a.oregon-postgres.render.com/rwe_data"
        prod_engine = create_engine(prod_db_uri)
        
        # Create a connection to the local database
        local_engine = db.engine
        
        with local_engine.connect() as local_conn, prod_engine.connect() as prod_conn:
            # Get all records from local database
            local_records = local_conn.execute(text("SELECT * FROM demand_data ORDER BY datetime")).fetchall()
            
            print(f"Found {len(local_records)} records in local database")
            
            # Get the latest record from production database
            latest_record = prod_conn.execute(text("SELECT MAX(datetime) FROM demand_data")).scalar()
            
            if latest_record:
                print(f"Latest record in production database: {latest_record}")
                
                # Filter records newer than the latest in production
                missing_records = [r for r in local_records if r[1] > latest_record]
                print(f"Found {len(missing_records)} new records to sync")
            else:
                print("No records in production database, syncing all records")
                missing_records = local_records
            
            # Add records to production database
            records_added = 0
            
            if missing_records:
                for record in missing_records:
                    # Create upsert statement using ON CONFLICT
                    upsert_stmt = f"""
                    INSERT INTO demand_data (
                        datetime, consumption, created_at
                    ) VALUES (
                        '{record[1]}', {record[2]}, '{record[3] or datetime.now()}'
                    )
                    ON CONFLICT (datetime) DO NOTHING
                    """
                    
                    try:
                        prod_conn.execute(text(upsert_stmt))
                        records_added += 1
                        
                        if records_added % 10 == 0:
                            print(f"Added {records_added} records so far...")
                    except Exception as e:
                        print(f"Error adding record for {record[1]}: {str(e)}")
                
                # Commit all changes
                prod_conn.commit()
                
                print(f"Successfully synced {records_added} records to production")
                
                # Verify final counts
                local_count = local_conn.execute(text("SELECT COUNT(*) FROM demand_data")).scalar()
                prod_count = prod_conn.execute(text("SELECT COUNT(*) FROM demand_data")).scalar()
                
                print(f"Local database has {local_count} records")
                print(f"Production database now has {prod_count} records")

def main():
    parser = argparse.ArgumentParser(description='Fetch missing demand data')
    parser.add_argument('--input-file', type=str, default=None,
                      help='JSON file containing missing dates')
    parser.add_argument('--check-first', action='store_true',
                      help='Check for missing dates before fetching')
    parser.add_argument('--sync-to-production', action='store_true',
                      help='Sync the local database to production after fetching')
    
    args = parser.parse_args()
    
    missing_dates = []
    
    if args.check_first:
        # Create app context to check for missing dates
        app = create_app()
        with app.app_context():
            from sqlalchemy import text
            
            # Find gaps in data
            query = text("""
                WITH dates AS (
                    SELECT generate_series(
                        date_trunc('hour', min(datetime)),
                        date_trunc('hour', max(datetime)),
                        '1 hour'::interval
                    ) as expected_datetime
                    FROM demand_data
                )
                SELECT expected_datetime::timestamp
                FROM dates
                LEFT JOIN demand_data ON dates.expected_datetime = date_trunc('hour', demand_data.datetime)
                WHERE demand_data.id IS NULL
                ORDER BY expected_datetime;
            """)
            
            result = db.session.execute(query).fetchall()
            missing_dates = [d[0].strftime('%Y-%m-%d %H:%M') for d in result]
            
            print(f"Found {len(missing_dates)} missing data points")
    
    elif args.input_file:
        # Read missing dates from file
        try:
            with open(args.input_file, 'r') as f:
                data = json.load(f)
                missing_dates = data.get('missing_dates', [])
                
                # If we only have a sample, get the full list
                if data.get('total_missing_dates', 0) > len(missing_dates):
                    app = create_app()
                    with app.app_context():
                        from sqlalchemy import text
                        
                        # Find gaps in data
                        query = text("""
                            WITH dates AS (
                                SELECT generate_series(
                                    date_trunc('hour', min(datetime)),
                                    date_trunc('hour', max(datetime)),
                                    '1 hour'::interval
                                ) as expected_datetime
                                FROM demand_data
                            )
                            SELECT expected_datetime::timestamp
                            FROM dates
                            LEFT JOIN demand_data ON dates.expected_datetime = date_trunc('hour', demand_data.datetime)
                            WHERE demand_data.id IS NULL
                            ORDER BY expected_datetime;
                        """)
                        
                        result = db.session.execute(query).fetchall()
                        missing_dates = [d[0].strftime('%Y-%m-%d %H:%M') for d in result]
        except Exception as e:
            print(f"Error reading input file: {e}")
            sys.exit(1)
    
    if missing_dates:
        fetch_missing_dates(missing_dates)
    else:
        print("No missing dates to fetch")

    if args.sync_to_production:
        sync_to_production()

if __name__ == "__main__":
    main() 