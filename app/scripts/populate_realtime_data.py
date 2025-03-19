import os
import sys
import argparse
from datetime import datetime, timedelta
import time

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(parent_dir)

from app.factory import create_app
from app.database.config import db
from app.models.realtime import HydroRealtimeData, NaturalGasRealtimeData
from app.functions import get_tgt_token
from app.mappings import hydro_mapping, plant_mapping
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import requests

# Global configuration
CHUNK_SIZE = 90  # Days per chunk
TYPE_MAPPINGS = {
    'hydro': (HydroRealtimeData, hydro_mapping),
    'natural_gas': (NaturalGasRealtimeData, plant_mapping)
}

def get_local_session():
    """Create a session for the local database"""
    local_db_url = "postgresql://rwe_user:123Cagatay123@localhost:5432/rwe_data"
    engine = create_engine(local_db_url)
    Session = sessionmaker(bind=engine)
    return Session()

def populate_realtime_data(plant_type: str, start_date: datetime.date, end_date: datetime.date, local_db=True):
    """
    Populate realtime data for a specific type and date range
    
    Args:
        plant_type: Type of plant data to fetch (hydro or natural_gas)
        start_date: Start date for data collection
        end_date: End date for data collection
        local_db: Whether to also store data in local database
    """
    app = create_app()
    model, mapping = TYPE_MAPPINGS[plant_type]
    
    print(f"\nPopulating {plant_type} realtime data for period {start_date} to {end_date}")
    
    # Split date range into chunks
    current = start_date
    chunks = []
    while current <= end_date:
        chunk_end = min(current + timedelta(days=CHUNK_SIZE-1), end_date)
        chunks.append((current, chunk_end))
        current = chunk_end + timedelta(days=1)
    
    print(f"Split into {len(chunks)} chunks")
    
    # Only create local session if needed
    local_session = get_local_session() if local_db else None
    
    try:
        with app.app_context():
            for chunk_start, chunk_end in chunks:
                print(f"\nProcessing chunk {chunk_start} to {chunk_end}")
                
                # Delete existing data for this chunk
                try:
                    # Delete from deployed database
                    model.query.filter(
                        model.date.between(chunk_start, chunk_end)
                    ).delete()
                    db.session.commit()
                    
                    # Delete from local database
                    if local_db:
                        local_session.query(model).filter(
                            model.date.between(chunk_start, chunk_end)
                        ).delete()
                        local_session.commit()
                except Exception as e:
                    print(f"Error clearing existing data: {str(e)}")
                    db.session.rollback()
                    if local_db:
                        local_session.rollback()
                
                # Create mappings for plant IDs
                p_id_count = {}
                for p_id in mapping['p_ids']:
                    p_id_count[p_id] = mapping['p_ids'].count(p_id)

                p_id_indices = {}
                for idx, p_id in enumerate(mapping['p_ids']):
                    if p_id not in p_id_indices:
                        p_id_indices[p_id] = []
                    p_id_indices[p_id].append(idx)

                # Get authentication token
                tgt_token = get_tgt_token(
                    app.config.get('USERNAME'),
                    app.config.get('PASSWORD')
                )
                
                # Fetch realtime data for each unique powerplant
                batch_data = []
                unique_p_ids = set(mapping['p_ids'])
                for p_id in unique_p_ids:
                    try:
                        print(f"Fetching realtime data for {plant_type} plant ID: {p_id}")
                        
                        request_data = {
                            "startDate": f"{chunk_start}T00:00:00+03:00",
                            "endDate": f"{chunk_end}T23:59:59+03:00",
                            "powerPlantId": str(p_id)
                        }

                        # Make API request
                        response = requests.post(
                            app.config['REALTIME_URL'],
                            json=request_data,
                            headers={'TGT': tgt_token}
                        )
                        response.raise_for_status()
                        
                        items = response.json().get('items', [])
                        
                        # Process each item in the response
                        for item in items:
                            try:
                                date_str = item.get('date', '').split('T')[0]
                                item_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                                hour = int(item.get('hour', '00:00').split(':')[0])
                                total = item.get('total', 0)

                                # Distribute value among plant instances
                                count = p_id_count[p_id]
                                distributed_value = total / count
                                
                                for idx in p_id_indices[p_id]:
                                    plant_name = mapping['plant_names'][idx]
                                    record_data = {
                                        'date': item_date,
                                        'hour': hour,
                                        'plant_name': plant_name,
                                        'value': distributed_value
                                    }
                                    batch_data.append(record_data)
                            except (ValueError, TypeError, AttributeError) as e:
                                print(f"Error processing item for plant {p_id}: {str(e)}")
                                continue
                        
                        time.sleep(0.5)  # Small delay between requests
                        
                    except Exception as e:
                        print(f"Error fetching data for plant {p_id}: {str(e)}")
                        continue

                # Store the fetched data in databases
                try:
                    if batch_data:
                        # Store in deployed database
                        db.session.bulk_insert_mappings(model, batch_data)
                        db.session.commit()
                        
                        # Store in local database
                        if local_db:
                            local_session.bulk_insert_mappings(model, batch_data)
                            local_session.commit()
                except Exception as e:
                    print(f"Error storing data: {str(e)}")
                    db.session.rollback()
                    if local_db:
                        local_session.rollback()
    
    except Exception as e:
        print(f"Error in populate_realtime_data: {str(e)}")
        if local_db:
            local_session.rollback()
    
    finally:
        # Close local session if it exists
        if local_db and local_session:
            local_session.close()

def main():
    parser = argparse.ArgumentParser(description='Populate historical realtime data')
    parser.add_argument('--start-date', type=str, required=True,
                      help='Start date in YYYY-MM-DD format')
    parser.add_argument('--end-date', type=str, required=True,
                      help='End date in YYYY-MM-DD format')
    parser.add_argument('--types', nargs='+', choices=list(TYPE_MAPPINGS.keys()),
                      default=list(TYPE_MAPPINGS.keys()),
                      help='Plant types to populate (default: all types)')
    parser.add_argument('--no-local-db', action='store_true',
                      help='Do not store data in local database')
    
    args = parser.parse_args()
    
    try:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
        
        if start_date > end_date:
            raise ValueError("End date must be after start date")
        
        # Populate each type
        for plant_type in args.types:
            try:
                populate_realtime_data(plant_type, start_date, end_date, not args.no_local_db)
            except Exception as e:
                print(f"Error processing {plant_type}: {str(e)}")
                with open('realtime_error.log', 'a') as f:
                    f.write(f"FATAL,{plant_type},{str(e)}\n")
                    
    except ValueError as e:
        print(f"Date error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 