import os
import sys
import argparse
from datetime import datetime, timedelta
import time

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(parent_dir)

from app import create_app
from app.database.config import db
from app.models.heatmap import HydroHeatmapData, NaturalGasHeatmapData, ImportedCoalHeatmapData
from app.functions import get_tgt_token, fetch_plant_data
from app.mappings import hydro_mapping, plant_mapping, import_coal_mapping

# Global configuration
CHUNK_SIZE = 90  # Days per chunk
TYPE_MAPPINGS = {
    'hydro': (HydroHeatmapData, hydro_mapping),
    'natural_gas': (NaturalGasHeatmapData, plant_mapping),
    'imported_coal': (ImportedCoalHeatmapData, import_coal_mapping)
}

def populate_heatmap_data(plant_type: str, start_date: datetime.date, end_date: datetime.date):
    """Populate heatmap data for a specific type and date range"""
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
    
    with app.app_context():
        # Process each version (first and current)
        versions = ['first', 'current']
        for version in versions:
            print(f"\nProcessing {version} version data...")
            
            # Select appropriate URL based on version
            url = (app.config['DPP_FIRST_VERSION_URL'] if version == 'first' 
                  else app.config['DPP_URL'])
            
            for chunk_start, chunk_end in chunks:
                print(f"\nProcessing chunk {chunk_start} to {chunk_end}")
                
                # Delete existing data for this chunk and version
                model.query.filter(
                    model.date.between(chunk_start, chunk_end),
                    model.version == version
                ).delete()
                db.session.commit()
                
                # Get fresh token for each chunk
                tgt_token = get_tgt_token(
                    app.config.get('USERNAME'),
                    app.config.get('PASSWORD')
                )
                
                # Fetch data for each plant
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
                            # Store new data
                            for item in response['items']:
                                try:
                                    date_str = item.get('date', '').split('T')[0]
                                    date = datetime.strptime(date_str, '%Y-%m-%d').date()
                                    hour = int(item.get('time', '00:00').split(':')[0])
                                    value = float(item.get('toplam', 0))
                                    
                                    record = model(
                                        date=date,
                                        hour=hour,
                                        plant_name=plant_name,
                                        value=value,
                                        version=version
                                    )
                                    db.session.add(record)
                                except (ValueError, TypeError, AttributeError) as e:
                                    print(f"Error processing item for {plant_name}: {str(e)}")
                                    continue
                            
                            db.session.commit()
                        else:
                            print(f"No data returned for {plant_name}")
                            
                    except Exception as e:
                        print(f"Error fetching data for {plant_name}: {str(e)}")
                        db.session.rollback()
                        with open('error.log', 'a') as f:
                            f.write(f"{chunk_start},{chunk_end},{plant_type},{plant_name},{str(e)}\n")
                    
                    time.sleep(0.5)  # Delay between requests

def main():
    parser = argparse.ArgumentParser(description='Populate historical heatmap data')
    parser.add_argument('--start-date', type=str, required=True,
                      help='Start date in YYYY-MM-DD format')
    parser.add_argument('--end-date', type=str, required=True,
                      help='End date in YYYY-MM-DD format')
    parser.add_argument('--types', nargs='+', choices=list(TYPE_MAPPINGS.keys()),
                      default=list(TYPE_MAPPINGS.keys()),
                      help='Plant types to populate (default: all types)')
    
    args = parser.parse_args()
    
    try:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
        
        if start_date > end_date:
            raise ValueError("End date must be after start date")
        
        # Populate each type
        for plant_type in args.types:
            try:
                populate_heatmap_data(plant_type, start_date, end_date)
            except Exception as e:
                print(f"Error processing {plant_type}: {str(e)}")
                with open('error.log', 'a') as f:
                    f.write(f"FATAL,{plant_type},{str(e)}\n")
                    
    except ValueError as e:
        print(f"Date error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()