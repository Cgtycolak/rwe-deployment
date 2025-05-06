import os
import sys
import argparse
from datetime import datetime, timedelta
import time
import requests
import pytz
import json
from sqlalchemy import text, create_engine
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(parent_dir)

from app import create_app
from app.database.config import db
from app.models.demand import DemandData
from app.functions import get_tgt_token

def setup_session():
    """Set up a requests session with retry logic"""
    session = requests.Session()
    retries = requests.adapters.Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504, 429],
    )
    session.mount('https://', requests.adapters.HTTPAdapter(max_retries=retries))
    return session

def fetch_demand_data(start_date, end_date, session, tgt_token):
    """Fetch demand data for a specific date range"""
    url = "https://seffaflik.epias.com.tr/electricity-service/v1/consumption/data/realtime-consumption"
    
    payload = {
        "startDate": f"{start_date.strftime('%Y-%m-%d')}T00:00:00+03:00",
        "endDate": f"{end_date.strftime('%Y-%m-%d')}T23:59:59+03:00",
        "region": "TR1",
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': "application/json",
        'TGT': tgt_token
    }
    
    response = session.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    
    return response.json().get('items', [])

def fetch_missing_dates(missing_dates, check_updates=False):
    """Fetch missing demand data for specific dates and check for updates"""
    print(f"\nFetching {len(missing_dates)} missing data points")
    
    # Group dates by month to minimize API calls
    date_groups = {}
    for date_str in missing_dates:
        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
        month_key = dt.strftime('%Y-%m')
        if month_key not in date_groups:
            date_groups[month_key] = []
        date_groups[month_key].append(dt)
    
    print(f"Grouped into {len(date_groups)} months")
    
    # Create app context and session
    app = create_app()
    session = setup_session()
    
    with app.app_context():
        # Get TGT token
        tgt_token = get_tgt_token(
            app.config.get('USERNAME'),
            app.config.get('PASSWORD')
        )
        
        # Process each month
        success_count = 0
        failure_count = 0
        failed_dates = []
        updated_count = 0
        
        for month, dates in date_groups.items():
            print(f"\nProcessing {month} with {len(dates)} missing hours")
            
            # Get first and last day of the month
            first_date = min(dates)
            last_date = max(dates)
            
            # Set start and end dates for the API call
            start_date = first_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if last_date.month == 12:
                end_date = datetime(last_date.year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = datetime(last_date.year, last_date.month + 1, 1) - timedelta(days=1)
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            try:
                # Fetch data for the entire month
                print(f"Fetching data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
                items = fetch_demand_data(start_date, end_date, session, tgt_token)
                
                if not items:
                    print(f"No data returned for {month}")
                    failed_dates.extend([d.strftime('%Y-%m-%d %H:%M') for d in dates])
                    failure_count += len(dates)
                    continue
                
                # Convert to DataFrame for easier processing
                df = pd.json_normalize(items)
                df['date'] = pd.to_datetime(df['date'])
                
                # Process items in batches
                batch_data = []
                current_time = datetime.now()  # Get current time once for all records
                for _, row in df.iterrows():
                    try:
                        dt = row['date'].to_pydatetime()
                        
                        # Check if this datetime is in our missing dates
                        if any(d.date() == dt.date() and d.hour == dt.hour for d in dates):
                            record_data = {
                                'datetime': dt,
                                'consumption': float(row.get('consumption', 0)),
                                'created_at': current_time  # Add created_at timestamp
                            }
                            batch_data.append(record_data)
                    except Exception as e:
                        print(f"Error processing item: {e}")
                        continue
                
                # Insert batch data
                if batch_data:
                    try:
                        # Use bulk insert with ON CONFLICT DO UPDATE
                        insert_stmt = """
                        INSERT INTO demand_data (datetime, consumption, created_at)
                        VALUES (:datetime, :consumption, :created_at)
                        ON CONFLICT (datetime) DO UPDATE
                        SET consumption = EXCLUDED.consumption,
                            created_at = EXCLUDED.created_at
                        """
                        
                        db.session.execute(text(insert_stmt), batch_data)
                        db.session.commit()
                        
                        success_count += len(batch_data)
                        print(f"Successfully inserted/updated {len(batch_data)} records for {month}")
                        
                        # If we're checking for updates, count how many were actually updated
                        if check_updates:
                            # Get the original values for comparison
                            dt_list = [record['datetime'] for record in batch_data]
                            original_records = DemandData.query.filter(DemandData.datetime.in_(dt_list)).all()
                            original_dict = {record.datetime.strftime('%Y-%m-%d %H:%M'): record.consumption for record in original_records}
                            
                            # Count updated records
                            for record in batch_data:
                                dt_key = record['datetime'].strftime('%Y-%m-%d %H:%M')
                                if dt_key in original_dict and abs(original_dict[dt_key] - record['consumption']) > 0.01:
                                    updated_count += 1
                            
                            print(f"Updated {updated_count} records with new values")
                        
                    except Exception as e:
                        print(f"Error inserting batch data: {e}")
                        failed_dates.extend([d.strftime('%Y-%m-%d %H:%M') for d in dates])
                        failure_count += len(dates)
                else:
                    print(f"No matching data found for {month}")
                    failed_dates.extend([d.strftime('%Y-%m-%d %H:%M') for d in dates])
                    failure_count += len(dates)
            
            except Exception as e:
                print(f"Error processing {month}: {e}")
                failed_dates.extend([d.strftime('%Y-%m-%d %H:%M') for d in dates])
                failure_count += len(dates)
        
        print(f"\nSummary:")
        print(f"Successfully processed {success_count} data points")
        if check_updates:
            print(f"Updated {updated_count} records with new values")
        print(f"Failed to process {failure_count} data points")
        
        if failed_dates:
            # Save failed dates to file for later retry
            output_file = f"failed_demand_dates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump({'failed_dates': failed_dates}, f)
            print(f"Saved {len(failed_dates)} failed dates to {output_file}")

def sync_to_production():
    """Sync demand data to production database"""
    print("Syncing demand data to production database...")
    
    # Get production database URL from environment variable
    production_db_url = os.environ.get('PRODUCTION_DATABASE_URL')
    
    if not production_db_url:
        print("Production database URL not configured")
        return
    
    # Create connections to both databases
    local_engine = create_engine(os.environ.get('DATABASE_URL'))
    prod_engine = create_engine(production_db_url)
    
    # First, check if the demand_data table exists in production
    prod_conn = prod_engine.connect()
    try:
        # Check if table exists
        result = prod_conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'demand_data'
            )
        """)).scalar()
        
        if not result:
            print("demand_data table does not exist in production, creating it...")
            prod_conn.execute(text("""
            CREATE TABLE demand_data (
                id SERIAL PRIMARY KEY,
                datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                consumption FLOAT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                CONSTRAINT demand_data_datetime_key UNIQUE (datetime)
            )
            """))
            prod_conn.commit()
            print("Table created successfully!")
        
        # Check if created_at column exists
        has_created_at = False
        try:
            result = prod_conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'demand_data' AND column_name = 'created_at'
            """)).fetchone()
            
            has_created_at = result is not None
            
            if has_created_at:
                print("Production database has created_at column")
            else:
                print("Production database does not have created_at column, adding it...")
                prod_conn.execute(text("""
                ALTER TABLE demand_data 
                ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                """))
                prod_conn.commit()
                has_created_at = True
                print("created_at column added successfully!")
        except Exception as e:
            print(f"Error checking/adding created_at column: {e}")
            print("Will proceed assuming column does not exist")
            has_created_at = False
        
        # Get all records from local database
        local_conn = local_engine.connect()
        local_records = local_conn.execute(text("SELECT id, datetime, consumption, created_at FROM demand_data")).fetchall()
        
        # Get all records from production database
        try:
            prod_records = prod_conn.execute(text("SELECT datetime, consumption FROM demand_data")).fetchall()
            # Create a dictionary of production records for quick lookup
            prod_dict = {record[0].strftime('%Y-%m-%d %H:%M'): float(record[1]) for record in prod_records}
        except Exception as e:
            print(f"Error getting production records: {e}")
            print("Assuming no records exist in production")
            prod_dict = {}
        
        # Find records to add or update
        records_to_sync = []
        for record in local_records:
            dt_key = record[1].strftime('%Y-%m-%d %H:%M')
            consumption = float(record[2])
            created_at = record[3] if record[3] else datetime.now()
            
            # If record doesn't exist in production or has a different value
            if dt_key not in prod_dict or abs(prod_dict[dt_key] - consumption) > 0.01:
                records_to_sync.append({
                    'datetime': record[1],
                    'consumption': consumption,
                    'created_at': created_at
                })
        
        print(f"Found {len(records_to_sync)} records to sync to production")
        
        if not records_to_sync:
            print("No records to sync.")
            return
        
        # Sync records in batches
        batch_size = 1000
        records_added = 0
        records_updated = 0
        
        for i in range(0, len(records_to_sync), batch_size):
            batch = records_to_sync[i:i+batch_size]
            
            # Use upsert (INSERT ... ON CONFLICT DO UPDATE)
            for record in batch:
                try:
                    # Check if record exists
                    exists = False
                    try:
                        exists = prod_conn.execute(
                            text("SELECT id FROM demand_data WHERE datetime = :datetime"),
                            {'datetime': record['datetime']}
                        ).fetchone() is not None
                    except Exception:
                        # If error, assume record doesn't exist
                        exists = False
                    
                    if exists:
                        # Update existing record
                        if has_created_at:
                            update_stmt = text("""
                            UPDATE demand_data 
                            SET consumption = :consumption, created_at = :created_at
                            WHERE datetime = :datetime
                            """)
                        else:
                            update_stmt = text("""
                            UPDATE demand_data 
                            SET consumption = :consumption
                            WHERE datetime = :datetime
                            """)
                        
                        prod_conn.execute(update_stmt, record)
                        records_updated += 1
                    else:
                        # Insert new record
                        if has_created_at:
                            insert_stmt = text("""
                            INSERT INTO demand_data (datetime, consumption, created_at)
                            VALUES (:datetime, :consumption, :created_at)
                            """)
                        else:
                            insert_stmt = text("""
                            INSERT INTO demand_data (datetime, consumption)
                            VALUES (:datetime, :consumption)
                            """)
                        
                        prod_conn.execute(insert_stmt, record)
                        records_added += 1
                except Exception as e:
                    print(f"Error syncing record {record['datetime']}: {e}")
                    continue
            
            # Commit after each batch
            try:
                prod_conn.commit()
                print(f"Synced batch {i//batch_size + 1}/{(len(records_to_sync)-1)//batch_size + 1}")
            except Exception as e:
                print(f"Error committing batch: {e}")
                prod_conn.rollback()
        
        print(f"Sync complete. Added {records_added} new records, updated {records_updated} existing records.")
        
        # Verify final counts
        try:
            local_count = local_conn.execute(text("SELECT COUNT(*) FROM demand_data")).scalar()
            prod_count = prod_conn.execute(text("SELECT COUNT(*) FROM demand_data")).scalar()
            
            print(f"Local database has {local_count} records")
            print(f"Production database now has {prod_count} records")
        except Exception as e:
            print(f"Error getting record counts: {e}")
        
        local_conn.close()
    except Exception as e:
        print(f"Error in sync_to_production: {e}")
    finally:
        prod_conn.close()

def main():
    # Load environment variables
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='Fetch missing demand data')
    parser.add_argument('--input-file', type=str, default=None,
                      help='JSON file containing missing dates')
    parser.add_argument('--check-first', action='store_true',
                      help='Check for missing dates before fetching')
    parser.add_argument('--sync-to-production', action='store_true',
                      help='Sync the local database to production after fetching')
    parser.add_argument('--check-updates', action='store_true',
                      help='Check for updated values in existing records')
    parser.add_argument('--days', type=int, default=15,
                      help='Number of days to check for updates (default: 15)')
    
    args = parser.parse_args()
    
    missing_dates = []
    
    if args.check_first:
        # Create app context to check for missing dates
        app = create_app()
        with app.app_context():
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
                missing_dates = data.get('failed_dates', [])
        except Exception as e:
            print(f"Error reading input file: {e}")
            sys.exit(1)
    
    # If checking for updates, add recent dates to the list
    if args.check_updates:
        app = create_app()
        with app.app_context():
            # Get dates from the last N days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=args.days)
            
            query = text("""
                SELECT DISTINCT date_trunc('day', datetime)::date
                FROM demand_data
                WHERE datetime >= :start_date AND datetime <= :end_date
                ORDER BY date_trunc('day', datetime)::date
            """)
            
            result = db.session.execute(query, {
                'start_date': start_date,
                'end_date': end_date
            }).fetchall()
            
            # Add all hours for these days
            for day in result:
                for hour in range(24):
                    dt = datetime.combine(day[0], datetime.min.time()) + timedelta(hours=hour)
                    missing_dates.append(dt.strftime('%Y-%m-%d %H:%M'))
            
            print(f"Added {len(missing_dates)} recent dates to check for updates")
    
    if missing_dates:
        fetch_missing_dates(missing_dates, check_updates=args.check_updates)
    else:
        print("No missing dates to fetch")

    if args.sync_to_production:
        sync_to_production()

if __name__ == "__main__":
    main() 