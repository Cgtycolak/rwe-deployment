import argparse
import sys
import os
import pandas as pd
import requests
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from tqdm import tqdm

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from app import create_app
from app.database.config import db
from app.models.demand import DemandData
from app.functions import get_tgt_token

def parse_args():
    parser = argparse.ArgumentParser(description='Populate demand data from EPIAS API')
    parser.add_argument('--start-date', type=str, required=True, help='Start date in YYYY-MM-DD format')
    parser.add_argument('--end-date', type=str, required=True, help='End date in YYYY-MM-DD format')
    parser.add_argument('--force', action='store_true', help='Force update even if data exists')
    parser.add_argument('--chunk-size', type=int, default=90, help='Days per API request')
    return parser.parse_args()

def parse_datetime(date_str):
    """Parse datetime from EPIAS API response format for demand data"""
    try:
        # Remove timezone info as SQLite doesn't support it
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        # Convert to naive datetime by removing timezone
        return dt.replace(tzinfo=None)
    except Exception as e:
        print(f"Error parsing datetime: {date_str} - {str(e)}")
        return None

def fetch_demand_data(start_date, end_date, tgt_token):
    """Fetch demand data from EPIAS API"""
    url = "https://seffaflik.epias.com.tr/electricity-service/v1/consumption/data/realtime-consumption"
    
    payload = {
        "startDate": f"{start_date}T00:00:00+03:00",
        "endDate": f"{end_date}T23:59:59+03:00",
        "region": "TR1",
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': "application/json",
        'TGT': tgt_token
    }
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json().get('items', [])

def main():
    args = parse_args()
    app = create_app()
    
    with app.app_context():
        # Parse dates
        try:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        except ValueError as e:
            print(f"Date error: {str(e)}")
            sys.exit(1)
        
        print(f"Populating demand data for period {args.start_date} to {args.end_date}")
        
        # Split into chunks to avoid API limitations
        current_date = start_date
        chunks = []
        
        while current_date <= end_date:
            chunk_end = min(current_date + timedelta(days=args.chunk_size-1), end_date)
            chunks.append((current_date.strftime('%Y-%m-%d'), chunk_end.strftime('%Y-%m-%d')))
            current_date = chunk_end + timedelta(days=1)
        
        print(f"Split into {len(chunks)} chunks")
        
        # Get TGT token
        tgt_token = get_tgt_token(
            app.config.get('USERNAME'),
            app.config.get('PASSWORD')
        )
        
        total_records_added = 0
        
        # Process each chunk
        for chunk_start, chunk_end in chunks:
            print(f"\nProcessing chunk {chunk_start} to {chunk_end}")
            
            # Delete existing records if force flag is set
            if args.force:
                deleted = DemandData.query.filter(
                    DemandData.datetime >= datetime.strptime(chunk_start, '%Y-%m-%d'),
                    DemandData.datetime <= datetime.strptime(chunk_end, '%Y-%m-%d') + timedelta(days=1)
                ).delete()
                db.session.commit()
                print(f"Deleted {deleted} existing records for period {chunk_start} to {chunk_end}")
            
            # Fetch data from API
            items = fetch_demand_data(chunk_start, chunk_end, tgt_token)
            
            if not items:
                print(f"No data found for period {chunk_start} to {chunk_end}")
                continue
            
            # Convert to DataFrame for easier processing
            df = pd.json_normalize(items)
            
            # Add records to database
            records_added = 0
            
            for _, row in tqdm(df.iterrows(), total=len(df), desc="Adding records"):
                try:
                    # Parse the ISO format date directly
                    date_str = row.get('date')
                    
                    if not date_str:
                        print(f"Missing date in row: {row}")
                        continue
                    
                    # Parse datetime
                    dt = parse_datetime(date_str)
                    if dt is None:
                        continue
                    
                    # Check if record already exists
                    existing = DemandData.query.filter_by(datetime=dt).first()
                    
                    if existing and not args.force:
                        continue
                    
                    # Get consumption value
                    consumption = row.get('consumption')
                    if consumption is None:
                        print(f"Missing consumption value in row: {row}")
                        continue
                    
                    # Create new record
                    record = DemandData(
                        datetime=dt,
                        consumption=float(consumption)
                    )
                    
                    db.session.add(record)
                    db.session.commit()
                    records_added += 1
                    
                except IntegrityError:
                    db.session.rollback()
                    # Record already exists, skip
                    continue
                except Exception as e:
                    db.session.rollback()
                    print(f"Error adding record: {str(e)}")
                    print(f"Row data: {row}")
            
            print(f"Added {records_added} records for period {chunk_start} to {chunk_end}")
            total_records_added += records_added
        
        print(f"\nTotal records added: {total_records_added}")

if __name__ == "__main__":
    main() 