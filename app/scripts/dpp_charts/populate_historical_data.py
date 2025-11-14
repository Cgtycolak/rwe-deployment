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
from app.models.heatmap import HydroHeatmapData, NaturalGasHeatmapData, ImportedCoalHeatmapData, LigniteHeatmapData
from app.functions import get_tgt_token, fetch_plant_data
from app.mappings import hydro_mapping, plant_mapping, import_coal_mapping, lignite_mapping
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Global configuration
CHUNK_SIZE = 90  # Days per chunk
TYPE_MAPPINGS = {
    'hydro': (HydroHeatmapData, hydro_mapping),
    'natural_gas': (NaturalGasHeatmapData, plant_mapping),
    'imported_coal': (ImportedCoalHeatmapData, import_coal_mapping),
    'lignite': (LigniteHeatmapData, lignite_mapping)
}

def get_local_session():
    """Create a session for the local database"""
    local_db_url = "postgresql://rwe_user:123Cagatay123@localhost:5432/rwe_data"
    engine = create_engine(local_db_url)
    Session = sessionmaker(bind=engine)
    return Session()

def populate_heatmap_data(plant_type: str, start_date: datetime.date, end_date: datetime.date, local_db=False):
    """
    Populate heatmap data for a specific type and date range
    
    Args:
        plant_type: Type of plant data to fetch
        start_date: Start date for data collection
        end_date: End date for data collection
        local_db: Whether to also store data in local database
    """
    app = create_app()
    model, mapping = TYPE_MAPPINGS[plant_type]
    
    print(f"\nPopulating {plant_type} data for period {start_date} to {end_date}")
    
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
            # Process each version (first and current)
            versions = ['first', 'current']
            for version in versions:
                print(f"\nProcessing {version} version data...")
                
                url = (app.config['DPP_FIRST_VERSION_URL'] if version == 'first' 
                      else app.config['DPP_URL'])
                
                for chunk_start, chunk_end in chunks:
                    print(f"\nProcessing chunk {chunk_start} to {chunk_end}")
                    
                    # Delete existing data in both databases
                    try:
                        # Delete from deployed database
                        model.query.filter(
                            model.date.between(chunk_start, chunk_end),
                            model.version == version
                        ).delete()
                        db.session.commit()
                        
                        # Delete from local database
                        if local_db:
                            local_session.query(model).filter(
                                model.date.between(chunk_start, chunk_end),
                                model.version == version
                            ).delete()
                            local_session.commit()
                    except Exception as e:
                        print(f"Error clearing existing data: {str(e)}")
                        db.session.rollback()
                        if local_db:
                            local_session.rollback()
                    
                    tgt_token = get_tgt_token(
                        app.config.get('USERNAME'),
                        app.config.get('PASSWORD')
                    )
                    
                    # Fetch and store data for each plant
                    for plant_name, o_id, pl_id in zip(
                        mapping['plant_names'],
                        mapping['o_ids'],
                        mapping['uevcb_ids']
                    ):
                        print(f"Fetching {version} data for {plant_name}")
                        
                        try:
                            response = fetch_plant_data(
                                start_date=chunk_start,
                                end_date=chunk_end,
                                org_id=o_id,
                                plant_id=pl_id,
                                url=url,
                                token=tgt_token
                            )
                            
                            if response and 'items' in response and response['items']:
                                # Store new data in both databases
                                for item in response['items']:
                                    try:
                                        date_str = item.get('date', '').split('T')[0]
                                        date = datetime.strptime(date_str, '%Y-%m-%d').date()
                                        hour = int(item.get('time', '00:00').split(':')[0])
                                        value = float(item.get('toplam', 0))
                                        
                                        # Create record for deployed database
                                        deployed_record = model(
                                            date=date,
                                            hour=hour,
                                            plant_name=plant_name,
                                            value=value,
                                            version=version
                                        )
                                        db.session.add(deployed_record)
                                        
                                        # Create record for local database
                                        if local_db:
                                            local_record = model(
                                                date=date,
                                                hour=hour,
                                                plant_name=plant_name,
                                                value=value,
                                                version=version
                                            )
                                            local_session.add(local_record)
                                        
                                    except (ValueError, TypeError, AttributeError) as e:
                                        print(f"Error processing item for {plant_name}: {str(e)}")
                                        continue
                                
                                # Commit to both databases
                                try:
                                    db.session.commit()
                                    if local_db:
                                        local_session.commit()
                                except Exception as e:
                                    print(f"Error committing data: {str(e)}")
                                    db.session.rollback()
                                    if local_db:
                                        local_session.rollback()
                                    
                            else:
                                print(f"No data returned for {plant_name}")
                                
                        except Exception as e:
                            print(f"Error fetching data for {plant_name}: {str(e)}")
                            db.session.rollback()
                            if local_db:
                                local_session.rollback()
                            with open('error.log', 'a') as f:
                                f.write(f"{chunk_start},{chunk_end},{plant_type},{plant_name},{str(e)}\n")
                        
                        time.sleep(0.1)  # Delay between requests
        
        # Only store in local db if requested
        if local_session:
            try:
                local_session.commit()
            except Exception as e:
                print(f"Error committing to local database: {str(e)}")
                local_session.rollback()
    
    finally:
        if local_session:
            local_session.close()

# Add convenience functions for single-date operations
def populate_single_day(date: datetime.date, plant_type: str, local_db=True):
    """Populate data for a single date"""
    return populate_heatmap_data(plant_type, date, date, local_db)

def populate_multiple_types(date, local_db=True, versions=['first', 'current']):
    """Populate data for multiple plant types for a specific date"""
    app = create_app()
    local_session = get_local_session() if local_db else None
    
    try:
        with app.app_context():
            # Process each plant type
            for plant_type, (model, mapping) in TYPE_MAPPINGS.items():
                print(f"\nProcessing plant type: {plant_type}")
                
                # Process each version (first and current)
                for version in versions:
                    print(f"Processing {version} version data...")
                    
                    url = (app.config['DPP_FIRST_VERSION_URL'] if version == 'first' 
                          else app.config['DPP_URL'])
                    
                    # Delete existing data for this date and version
                    try:
                        # Delete from deployed database
                        model.query.filter(
                            model.date == date,
                            model.version == version
                        ).delete()
                        db.session.commit()
                        
                        # Delete from local database
                        if local_db:
                            local_session.query(model).filter(
                                model.date == date,
                                model.version == version
                            ).delete()
                            local_session.commit()
                    except Exception as e:
                        print(f"Error clearing existing data: {str(e)}")
                        db.session.rollback()
                        if local_db:
                            local_session.rollback()
                    
                    tgt_token = get_tgt_token(
                        app.config.get('USERNAME'),
                        app.config.get('PASSWORD')
                    )
                    
                    # Fetch and store data for each plant
                    for plant_name, o_id, pl_id in zip(
                        mapping['plant_names'],
                        mapping['o_ids'],
                        mapping['uevcb_ids']
                    ):
                        print(f"Fetching {version} data for {plant_name}")
                        
                        try:
                            response = fetch_plant_data(
                                start_date=date,
                                end_date=date,
                                org_id=o_id,
                                plant_id=pl_id,
                                url=url,
                                token=tgt_token
                            )
                            
                            if response and 'items' in response and response['items']:
                                # Store new data in both databases
                                for item in response['items']:
                                    try:
                                        date_str = item.get('date', '').split('T')[0]
                                        item_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                                        hour = int(item.get('time', '00:00').split(':')[0])
                                        value = float(item.get('toplam', 0))
                                        
                                        # Create record for deployed database
                                        deployed_record = model(
                                            date=item_date,
                                            hour=hour,
                                            plant_name=plant_name,
                                            value=value,
                                            version=version
                                        )
                                        db.session.add(deployed_record)
                                        
                                        # Create record for local database
                                        if local_db:
                                            local_record = model(
                                                date=item_date,
                                                hour=hour,
                                                plant_name=plant_name,
                                                value=value,
                                                version=version
                                            )
                                            local_session.add(local_record)
                                        
                                    except (ValueError, TypeError, AttributeError) as e:
                                        print(f"Error processing item for {plant_name}: {str(e)}")
                                        continue
                                
                                # Commit to both databases
                                try:
                                    db.session.commit()
                                    if local_db:
                                        local_session.commit()
                                except Exception as e:
                                    print(f"Error committing data: {str(e)}")
                                    db.session.rollback()
                                    if local_db:
                                        local_session.rollback()
                                    
                            else:
                                print(f"No data returned for {plant_name}")
                                
                        except Exception as e:
                            print(f"Error fetching data for {plant_name}: {str(e)}")
                            db.session.rollback()
                            if local_db:
                                local_session.rollback()
                            with open('error.log', 'a') as f:
                                f.write(f"{date},{date},{plant_type},{plant_name},{str(e)}\n")
                        
                        time.sleep(0.1)  # Delay between requests
    
    except Exception as e:
        print(f"Error in populate_multiple_types: {str(e)}")
        if local_db:
            local_session.rollback()
    
    finally:
        # Close local session if it exists
        if local_db and local_session:
            local_session.close()

def main():
    parser = argparse.ArgumentParser(description='Populate historical heatmap data')
    parser.add_argument('--start-date', type=str, required=True,
                      help='Start date in YYYY-MM-DD format')
    parser.add_argument('--end-date', type=str, required=True,
                      help='End date in YYYY-MM-DD format')
    parser.add_argument('--types', nargs='+', choices=list(TYPE_MAPPINGS.keys()),
                      default=list(TYPE_MAPPINGS.keys()),
                      help='Plant types to populate (default: all types)')
    parser.add_argument('--no-local-db', action='store_true',
                      help='Skip updating local database (only update deployed database)')
    
    args = parser.parse_args()
    
    try:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
        
        if start_date > end_date:
            raise ValueError("End date must be after start date")
        
        # Determine if we should update local DB
        local_db = not args.no_local_db
        
        # Populate each type
        for plant_type in args.types:
            try:
                populate_heatmap_data(plant_type, start_date, end_date, local_db=local_db)
            except Exception as e:
                print(f"Error processing {plant_type}: {str(e)}")
                with open('error.log', 'a') as f:
                    f.write(f"FATAL,{plant_type},{str(e)}\n")
                    
    except ValueError as e:
        print(f"Date error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()