import os
import sys
import argparse
from datetime import datetime, timedelta
import time
import requests
import pytz
import math

# Fix the path - go up 3 levels to reach the root directory
current_dir = os.path.dirname(os.path.abspath(__file__))
# Go up 3 levels: cao_charts -> scripts -> app -> rwe-deployment (root)
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(parent_dir)

from app.factory import create_app
from app.database.config import db
from app.models.production import ProductionData
from app.functions import get_tgt_token
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Global configuration
CHUNK_SIZE = 90  # Days per chunk

def get_local_session():
    """Create a session for the local database"""
    local_db_url = "postgresql://rwe_user:123Cagatay123@localhost:5432/rwe_data"
    engine = create_engine(local_db_url)
    Session = sessionmaker(bind=engine)
    return Session()

def parse_datetime(date_str, hour_str):
    """Parse datetime from EPIAS API response format"""
    try:
        # First try to parse the date string
        date = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
        
        # Parse hour from the hour string (format: "HH:00")
        hour = int(hour_str.split(':')[0])
        
        # Create datetime with timezone info
        dt = datetime.combine(date, datetime.min.time().replace(hour=hour))
        return dt.replace(tzinfo=pytz.timezone('Europe/Istanbul'))
    except Exception as e:
        print(f"Error parsing datetime: {date_str}, {hour_str} - {str(e)}")
        return None

def try_smaller_chunks(start_date, end_date, app, tgt_token, db_session, local_session=None, local_db=True):
    """Try to fetch data with smaller chunks when a large chunk fails"""
    print(f"\nRetrying with smaller chunks for period {start_date} to {end_date}")
    
    # Split into monthly chunks
    current = start_date
    success = True
    while current <= end_date:
        # Get end of current month
        if current.month == 12:
            month_end = current.replace(year=current.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = current.replace(month=current.month + 1, day=1) - timedelta(days=1)
            
        chunk_end = min(month_end, end_date)
        
        try:
            request_data = {
                "startDate": f"{current}T00:00:00+03:00",
                "endDate": f"{chunk_end}T23:59:59+03:00"
            }
            
            response = requests.post(
                app.config['REALTIME_URL'],
                json=request_data,
                headers={'TGT': tgt_token},
                timeout=30  # Add timeout
            )
            response.raise_for_status()
            
            items = response.json().get('items', [])
            batch_data = []
            
            for item in items:
                try:
                    date_str = item.get('date', '')
                    hour_str = item.get('hour', '00:00')
                    
                    dt = parse_datetime(date_str, hour_str)
                    if dt is None:
                        continue
                    
                    record_data = {
                        'datetime': dt,
                        'fueloil': float(item.get('fueloil', 0)),
                        'gasoil': float(item.get('gasoil', 0)),
                        'blackcoal': float(item.get('blackcoal', 0)),
                        'lignite': float(item.get('lignite', 0)),
                        'geothermal': float(item.get('geothermal', 0)),
                        'naturalgas': float(item.get('naturalgas', 0)),
                        'river': float(item.get('river', 0)),
                        'dammedhydro': float(item.get('dammedhydro', 0)),
                        'lng': float(item.get('lng', 0)),
                        'biomass': float(item.get('biomass', 0)),
                        'naphta': float(item.get('naphta', 0)),
                        'importcoal': float(item.get('importcoal', 0)),
                        'asphaltitecoal': float(item.get('asphaltitecoal', 0)),
                        'wind': float(item.get('wind', 0)),
                        'nuclear': float(item.get('nuclear', 0)),
                        'sun': float(item.get('sun', 0)),
                        'importexport': float(item.get('importexport', 0)),
                        'total': float(item.get('total', 0)),
                        'wasteheat': float(item.get('wasteheat', 0))
                    }
                    batch_data.append(record_data)
                    
                except (ValueError, TypeError, AttributeError) as e:
                    print(f"Error processing item: {str(e)}")
                    continue
            
            if batch_data:
                try:
                    db_session.bulk_insert_mappings(ProductionData, batch_data)
                    db_session.commit()
                    
                    if local_db and local_session:
                        local_session.bulk_insert_mappings(ProductionData, batch_data)
                        local_session.commit()
                        
                    print(f"Successfully stored {len(batch_data)} records for period {current} to {chunk_end}")
                except Exception as e:
                    print(f"Error committing data: {str(e)}")
                    db_session.rollback()
                    if local_db and local_session:
                        local_session.rollback()
                    success = False
            
        except Exception as e:
            print(f"Error fetching data for period {current} to {chunk_end}: {str(e)}")
            with open('production_error.log', 'a') as f:
                f.write(f"{current},{chunk_end},{str(e)}\n")
            success = False
        
        time.sleep(1)  # Increased delay between requests
        current = chunk_end + timedelta(days=1)
    
    return success

def populate_production_data(start_date: datetime.date, end_date: datetime.date, local_db=True):
    """
    Populate production data for a given date range
    """
    print(f"\nPopulating production data for period {start_date} to {end_date}")
    
    # Calculate number of days
    days = (end_date - start_date).days + 1
    
    # Split into chunks of 90 days
    chunk_size = 90
    num_chunks = math.ceil(days / chunk_size)
    
    print(f"Split into {num_chunks} chunks\n")
    
    # Create app context
    app = create_app()
    with app.app_context():
        # Get TGT token
        tgt_token = get_tgt_token(
            app.config.get('USERNAME'),
            app.config.get('PASSWORD')
        )
        
        # Create local session if needed
        local_session = None
        if not local_db:
            local_session = get_local_session()
        
        # Process each chunk
        current_date = start_date
        for i in range(num_chunks):
            # Calculate chunk end date
            chunk_end_date = min(current_date + timedelta(days=chunk_size-1), end_date)
            
            print(f"Processing chunk {current_date} to {chunk_end_date}")
            
            try:
                # First, delete any existing data for this date range
                if local_db:
                    # Delete from PostgreSQL database
                    deleted_count = db.session.query(ProductionData).filter(
                        ProductionData.datetime >= datetime.combine(current_date, datetime.min.time()),
                        ProductionData.datetime <= datetime.combine(chunk_end_date, datetime.max.time())
                    ).delete()
                    db.session.commit()
                    print(f"Deleted {deleted_count} existing records for period {current_date} to {chunk_end_date}")
                else:
                    # Delete from SQLite database
                    deleted_count = local_session.query(ProductionData).filter(
                        ProductionData.datetime >= datetime.combine(current_date, datetime.min.time()),
                        ProductionData.datetime <= datetime.combine(chunk_end_date, datetime.max.time())
                    ).delete()
                    local_session.commit()
                    print(f"Deleted {deleted_count} existing records for period {current_date} to {chunk_end_date}")
                
                # Fetch data from API
                chunk_start = current_date.strftime('%Y-%m-%d')
                chunk_end = chunk_end_date.strftime('%Y-%m-%d')
                
                request_data = {
                    "startDate": f"{chunk_start}T00:00:00+03:00",
                    "endDate": f"{chunk_end}T23:59:59+03:00"
                }
                
                response = requests.post(
                    app.config['REALTIME_URL'],
                    json=request_data,
                    headers={'TGT': tgt_token},
                    timeout=30
                )
                
                if response.status_code != 200:
                    print(f"Error fetching data: {response.status_code}")
                    time.sleep(2)  # Wait before next request
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
                        dt = parse_datetime(date_str, hour_str)
                        if dt is None:
                            continue
                        
                        # Skip data outside our requested range
                        dt_date = dt.date()
                        if dt_date < current_date or dt_date > chunk_end_date:
                            continue
                        
                        # Prepare record data
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
                    except Exception as e:
                        print(f"Error processing item: {e}")
                        continue
                
                # Insert batch data
                if batch_data:
                    try:
                        if local_db:
                            # Insert into PostgreSQL database
                            db.session.bulk_insert_mappings(ProductionData, batch_data)
                            db.session.commit()
                        else:
                            # Insert into SQLite database
                            local_session.bulk_insert_mappings(ProductionData, batch_data)
                            local_session.commit()
                        
                        print(f"Successfully stored {len(batch_data)} records for chunk {chunk_start} to {chunk_end}\n")
                    except Exception as e:
                        if local_db:
                            db.session.rollback()
                        else:
                            local_session.rollback()
                        print(f"Error committing data: {e}")
                else:
                    print(f"No data found for chunk {chunk_start} to {chunk_end}\n")
            
            except Exception as e:
                print(f"Error processing chunk {current_date} to {chunk_end_date}: {e}")
            
            # Move to next chunk
            current_date = chunk_end_date + timedelta(days=1)

def main():
    parser = argparse.ArgumentParser(description='Populate production data')
    parser.add_argument('--start-date', type=str, required=True,
                      help='Start date in YYYY-MM-DD format')
    parser.add_argument('--end-date', type=str, required=True,
                      help='End date in YYYY-MM-DD format')
    parser.add_argument('--no-local-db', action='store_true',
                      help='Do not store data in local database')
    
    args = parser.parse_args()
    
    try:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
        
        if start_date > end_date:
            raise ValueError("End date must be after start date")
        
        populate_production_data(start_date, end_date, not args.no_local_db)
                    
    except ValueError as e:
        print(f"Date error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 