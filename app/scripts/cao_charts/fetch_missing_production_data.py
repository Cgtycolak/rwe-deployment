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
from app.models.production import ProductionData
from app.functions import get_tgt_token
from app.scripts.cao_charts.populate_production_data import parse_datetime

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

def parse_datetime_improved(date_str, hour_str):
    """Enhanced datetime parsing with better timezone handling"""
    try:
        # First try to parse the date string
        if 'T' in date_str:
            date = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
        else:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Parse hour from the hour string (format: "HH:00")
        hour = int(hour_str.split(':')[0])
        
        # Create datetime without timezone first
        dt = datetime.combine(date, datetime.min.time().replace(hour=hour))
        
        # Handle timezone
        tz = pytz.timezone('Europe/Istanbul')
        try:
            # Try to localize the datetime
            localized_dt = tz.localize(dt, is_dst=None)
            return [localized_dt]
        except pytz.exceptions.AmbiguousTimeError:
            # During DST transitions, return both possible interpretations
            return [
                tz.localize(dt, is_dst=True),
                tz.localize(dt, is_dst=False)
            ]
        except pytz.exceptions.NonExistentTimeError:
            # For skipped hours during DST transitions
            # Return the same time in the next UTC offset
            return [tz.localize(dt + timedelta(hours=1))]
            
    except Exception as e:
        print(f"Error parsing datetime: {date_str}, {hour_str} - {str(e)}")
        return None

def try_alternative_endpoints(date, session, tgt_token, app_config):
    """Try different API endpoints to get the data"""
    endpoints = [
        (app_config['REALTIME_URL'], "realtime"),
        ('https://seffaflik.epias.com.tr/electricity-service/v1/generation/data/dpp', "dpp"),
        ('https://seffaflik.epias.com.tr/electricity-service/v1/generation/data/aic', "aic")
    ]
    
    for url, endpoint_type in endpoints:
        try:
            request_data = {
                "startDate": f"{date.strftime('%Y-%m-%d')}T00:00:00+03:00",
                "endDate": f"{date.strftime('%Y-%m-%d')}T23:59:59+03:00"
            }
            
            if endpoint_type in ["dpp", "aic"]:
                request_data["region"] = "TR1"
            
            response = session.post(
                url,
                json=request_data,
                headers={'TGT': tgt_token},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get('items', []), endpoint_type
                
        except Exception as e:
            print(f"Error with {endpoint_type} endpoint: {e}")
            continue
    
    return None, None

def fetch_missing_dates(missing_dates, local_db=True):
    """
    Fetch missing production data for specific dates with improved error handling
    """
    print(f"\nFetching {len(missing_dates)} missing data points")
    
    # Group dates by day to minimize API calls
    date_groups = {}
    for date_str in missing_dates:
        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
        day_key = dt.strftime('%Y-%m-%d')
        if day_key not in date_groups:
            date_groups[day_key] = []
        date_groups[day_key].append(dt)
    
    print(f"Grouped into {len(date_groups)} days")
    
    # Create app context and session
    app = create_app()
    session = setup_session()
    
    with app.app_context():
        # Get TGT token
        tgt_token = get_tgt_token(
            app.config.get('USERNAME'),
            app.config.get('PASSWORD')
        )
        
        # Process each day
        success_count = 0
        failure_count = 0
        failed_dates = []
        
        for day, dates in date_groups.items():
            print(f"\nProcessing {day} with {len(dates)} missing hours")
            day_date = datetime.strptime(day, '%Y-%m-%d').date()
            
            try:
                # Try different endpoints
                items, endpoint_type = try_alternative_endpoints(day_date, session, tgt_token, app.config)
                
                if not items:
                    print(f"No data found for {day} from any endpoint")
                    failure_count += len(dates)
                    failed_dates.extend([dt.strftime('%Y-%m-%d %H:%M') for dt in dates])
                    continue
                
                print(f"Got data from {endpoint_type} endpoint")
                
                # Process items
                batch_data = []
                for item in items:
                    try:
                        date_str = item.get('date', '')
                        hour_str = item.get('hour', '00:00')
                        
                        # Get possible datetime interpretations
                        dts = parse_datetime_improved(date_str, hour_str)
                        if not dts:
                            continue
                        
                        # Try each possible datetime
                        for dt in dts:
                            if dt.hour in [d.hour for d in dates]:
                                record_data = {
                                    'datetime': dt,
                                    'fueloil': float(item.get('fueloil', 0)),
                                    'gasoil': float(item.get('gasoil', 0)),
                                    'blackcoal': float(item.get('blackCoal', 0)),
                                    'lignite': float(item.get('lignite', 0)),
                                    'geothermal': float(item.get('geothermal', 0)),
                                    'naturalgas': float(item.get('naturalGas', 0)),
                                    'river': float(item.get('river', 0)),
                                    'dammedhydro': float(item.get('dammedHydro', 0)),
                                    'lng': float(item.get('lng', 0)),
                                    'biomass': float(item.get('biomass', 0)),
                                    'naphta': float(item.get('naphta', 0)),
                                    'importcoal': float(item.get('importCoal', 0)),
                                    'asphaltitecoal': float(item.get('asphaltiteCoal', 0)),
                                    'wind': float(item.get('wind', 0)),
                                    'nuclear': float(item.get('nuclear', 0)),
                                    'sun': float(item.get('sun', 0)),
                                    'importexport': float(item.get('importExport', 0)),
                                    'total': float(item.get('total', 0)),
                                    'wasteheat': float(item.get('wasteheat', 0))
                                }
                                batch_data.append(record_data)
                                break
                    except Exception as e:
                        print(f"Error processing item: {e}")
                        continue
                
                # Insert batch data using upsert
                if batch_data:
                    try:
                        stmt = insert(ProductionData).values(batch_data)
                        stmt = stmt.on_conflict_do_update(
                            constraint='production_data_datetime_key',
                            set_={
                                'fueloil': stmt.excluded.fueloil,
                                'gasoil': stmt.excluded.gasoil,
                                'blackcoal': stmt.excluded.blackcoal,
                                'lignite': stmt.excluded.lignite,
                                'geothermal': stmt.excluded.geothermal,
                                'naturalgas': stmt.excluded.naturalgas,
                                'river': stmt.excluded.river,
                                'dammedhydro': stmt.excluded.dammedhydro,
                                'lng': stmt.excluded.lng,
                                'biomass': stmt.excluded.biomass,
                                'naphta': stmt.excluded.naphta,
                                'importcoal': stmt.excluded.importcoal,
                                'asphaltitecoal': stmt.excluded.asphaltitecoal,
                                'wind': stmt.excluded.wind,
                                'nuclear': stmt.excluded.nuclear,
                                'sun': stmt.excluded.sun,
                                'importexport': stmt.excluded.importexport,
                                'total': stmt.excluded.total,
                                'wasteheat': stmt.excluded.wasteheat
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
                print(f"Error processing {day}: {e}")
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
            with open('failed_dates.json', 'w') as f:
                json.dump({'failed_dates': failed_dates}, f)
            print("\nFailed dates have been saved to failed_dates.json")

def sync_to_production():
    """Sync the local database to production after filling missing data"""
    print("\nSyncing to production database...")
    
    # Create app context
    app = create_app()
    
    with app.app_context():
        # Create a connection to the production database
        
        # Use SQLAlchemy to connect and transfer the data
        from sqlalchemy import text
        local_engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        prod_db_url = os.environ.get('PRODUCTION_DATABASE_URL')
        if not prod_db_url:
            print("Error: PRODUCTION_DATABASE_URL environment variable not set")
            return
        prod_engine = create_engine(prod_db_url)
        
        # Get all records from local that don't exist in production
        with local_engine.connect() as local_conn:
            with prod_engine.connect() as prod_conn:
                # Get all datetimes from production
                prod_datetimes = prod_conn.execute(text("SELECT datetime FROM production_data")).fetchall()
                prod_dt_set = set(dt[0].strftime('%Y-%m-%d %H:%M:%S') for dt in prod_datetimes)
                
                # Get records from local that don't exist in production
                local_records = local_conn.execute(text("""
                    SELECT datetime, fueloil, gasoil, blackcoal, lignite, geothermal, 
                           naturalgas, river, dammedhydro, lng, biomass, naphta, 
                           importcoal, asphaltitecoal, wind, nuclear, sun, 
                           importexport, total, wasteheat
                    FROM production_data
                """)).fetchall()
                
                # Filter for records not in production
                missing_records = [r for r in local_records if r[0].strftime('%Y-%m-%d %H:%M:%S') not in prod_dt_set]
                
                print(f"Found {len(missing_records)} records to sync to production")
                
                if not missing_records:
                    print("No records to sync.")
                    return
                
                # Insert missing records using upsert
                records_added = 0
                for record in missing_records:
                    # Create upsert statement using ON CONFLICT
                    upsert_stmt = f"""
                    INSERT INTO production_data (
                        datetime, fueloil, gasoil, blackcoal, lignite, geothermal, 
                        naturalgas, river, dammedhydro, lng, biomass, naphta, 
                        importcoal, asphaltitecoal, wind, nuclear, sun, 
                        importexport, total, wasteheat
                    ) VALUES (
                        '{record[0]}', {record[1]}, {record[2]}, 
                        {record[3]}, {record[4]}, {record[5]}, 
                        {record[6]}, {record[7]}, {record[8]}, 
                        {record[9]}, {record[10]}, {record[11]}, 
                        {record[12]}, {record[13]}, {record[14]}, 
                        {record[15]}, {record[16]}, {record[17]}, 
                        {record[18]}, {record[19]}
                    )
                    ON CONFLICT (datetime) DO NOTHING
                    """
                    
                    try:
                        prod_conn.execute(text(upsert_stmt))
                        records_added += 1
                        
                        if records_added % 10 == 0:
                            print(f"Added {records_added} records so far...")
                    except Exception as e:
                        print(f"Error adding record for {record[0]}: {str(e)}")
                
                # Commit all changes
                prod_conn.commit()
                
                print(f"Successfully synced {records_added} records to production")
                
                # Verify final counts
                local_count = local_conn.execute(text("SELECT COUNT(*) FROM production_data")).scalar()
                prod_count = prod_conn.execute(text("SELECT COUNT(*) FROM production_data")).scalar()
                
                print(f"Local database has {local_count} records")
                print(f"Production database now has {prod_count} records")

def main():
    parser = argparse.ArgumentParser(description='Fetch missing production data')
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
                    FROM production_data
                )
                SELECT expected_datetime::timestamp
                FROM dates
                LEFT JOIN production_data ON dates.expected_datetime = date_trunc('hour', production_data.datetime)
                WHERE production_data.id IS NULL
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
                                FROM production_data
                            )
                            SELECT expected_datetime::timestamp
                            FROM dates
                            LEFT JOIN production_data ON dates.expected_datetime = date_trunc('hour', production_data.datetime)
                            WHERE production_data.id IS NULL
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