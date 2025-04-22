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

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(parent_dir)

from app.factory import create_app
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

def fetch_missing_dates(missing_dates):
    """Fetch missing demand data for specific dates"""
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
                items = fetch_demand_data(start_date, end_date, session, tgt_token)
                
                if not items:
                    print(f"No data found for {month}")
                    failure_count += len(dates)
                    failed_dates.extend([dt.strftime('%Y-%m-%d %H:%M') for dt in dates])
                    continue
                
                print(f"Got {len(items)} records for {month}")
                
                # Convert to DataFrame for easier processing
                df = pd.json_normalize(items)
                df['date'] = pd.to_datetime(df['date'])
                
                # Process items in batches
                batch_data = []
                for _, row in df.iterrows():
                    try:
                        dt = row['date'].to_pydatetime()
                        
                        # Check if this datetime is in our missing dates
                        if any(d.date() == dt.date() and d.hour == dt.hour for d in dates):
                            record_data = {
                                'datetime': dt,
                                'consumption': float(row.get('consumption', 0))
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
                        INSERT INTO demand_data (datetime, consumption)
                        VALUES (:datetime, :consumption)
                        ON CONFLICT (datetime) DO UPDATE
                        SET consumption = EXCLUDED.consumption
                        """
                        
                        db.session.execute(text(insert_stmt), batch_data)
                        db.session.commit()
                        
                        print(f"Successfully stored {len(batch_data)} records for {month}")
                        success_count += len(batch_data)
                    except Exception as e:
                        db.session.rollback()
                        print(f"Error committing data: {e}")
                        failure_count += len(dates)
                        failed_dates.extend([dt.strftime('%Y-%m-%d %H:%M') for dt in dates])
                else:
                    print(f"No matching data found for {month}")
                    failure_count += len(dates)
                    failed_dates.extend([dt.strftime('%Y-%m-%d %H:%M') for dt in dates])
            
            except Exception as e:
                print(f"Error processing {month}: {e}")
                failure_count += len(dates)
                failed_dates.extend([dt.strftime('%Y-%m-%d %H:%M') for dt in dates])
            
            time.sleep(1)  # Wait between requests
        
        print(f"\nSummary:")
        print(f"Successfully fetched {success_count} records")
        print(f"Failed to fetch {failure_count} records")
        if failed_dates:
            print("\nFailed dates:")
            for date in failed_dates:
                print(date)
            
            # Save failed dates to file
            with open('failed_demand_dates.json', 'w') as f:
                json.dump({'failed_dates': failed_dates}, f)
            print("\nFailed dates have been saved to failed_demand_dates.json")

def sync_to_production():
    """Sync local demand data to production database"""
    print("Syncing demand data to production database...")
    
    # Get production database connection string from environment variable
    prod_db_url = os.environ.get('PRODUCTION_DATABASE_URL')
    
    # Create app context
    app = create_app()
    
    with app.app_context():
        # Create engine for production database
        local_engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        prod_engine = create_engine(prod_db_url)
        
        # Create demand_data table if it doesn't exist
        with prod_engine.connect() as prod_conn:
            # Check if table exists
            table_exists = prod_conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'demand_data')"
            )).scalar()
            
            if not table_exists:
                print("Creating demand_data table in production database...")
                prod_conn.execute(text("""
                    CREATE TABLE demand_data (
                        id SERIAL PRIMARY KEY,
                        datetime TIMESTAMP NOT NULL,
                        consumption FLOAT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(datetime)
                    )
                """))
                prod_conn.commit()
                print("Table created successfully")
        
        # Get all records from local that don't exist in production
        with local_engine.connect() as local_conn:
            with prod_engine.connect() as prod_conn:
                # Get all datetimes from production
                prod_datetimes = prod_conn.execute(text("SELECT datetime FROM demand_data")).fetchall()
                prod_dt_set = set(dt[0].strftime('%Y-%m-%d %H:%M:%S') for dt in prod_datetimes)
                
                # Get records from local that don't exist in production
                local_records = local_conn.execute(text("""
                    SELECT datetime, consumption
                    FROM demand_data
                """)).fetchall()
                
                # Filter for records not in production
                missing_records = [r for r in local_records if r[0].strftime('%Y-%m-%d %H:%M:%S') not in prod_dt_set]
                
                print(f"Found {len(missing_records)} records to sync to production")
                
                if not missing_records:
                    print("No records to sync.")
                    return
                
                # Insert missing records in batches
                batch_size = 500
                total_batches = (len(missing_records) + batch_size - 1) // batch_size
                records_added = 0
                
                for batch_num in range(total_batches):
                    start_idx = batch_num * batch_size
                    end_idx = min((batch_num + 1) * batch_size, len(missing_records))
                    batch = missing_records[start_idx:end_idx]
                    
                    # Create batch insert statement
                    values_str = ",".join([
                        f"('{r[0]}', {r[1]})" for r in batch
                    ])
                    
                    insert_stmt = f"""
                    INSERT INTO demand_data (datetime, consumption)
                    VALUES {values_str}
                    ON CONFLICT (datetime) DO NOTHING
                    """
                    
                    try:
                        prod_conn.execute(text(insert_stmt))
                        records_added += len(batch)
                        print(f"Processed batch {batch_num + 1}/{total_batches} ({records_added}/{len(missing_records)} records)")
                    except Exception as e:
                        print(f"Error adding batch {batch_num + 1}: {str(e)}")
                
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
    
    if missing_dates:
        fetch_missing_dates(missing_dates)
    else:
        print("No missing dates to fetch")

    if args.sync_to_production:
        sync_to_production()

if __name__ == "__main__":
    main() 