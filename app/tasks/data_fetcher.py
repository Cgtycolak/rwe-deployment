from datetime import datetime, timedelta
from ..models.heatmap import HydroHeatmapData, NaturalGasHeatmapData, ImportedCoalHeatmapData
from ..database.config import db
from ..functions import get_tgt_token, fetch_plant_data
from ..mappings import hydro_mapping, plant_mapping, import_coal_mapping
from flask import current_app
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pytz import timezone

def get_plant_config(plant_type):
    """Helper function to get plant configuration based on type"""
    configs = {
        'hydro': (hydro_mapping, HydroHeatmapData),
        'natural_gas': (plant_mapping, NaturalGasHeatmapData),
        'imported_coal': (import_coal_mapping, ImportedCoalHeatmapData)
    }
    if plant_type not in configs:
        raise ValueError(f"Invalid plant type: {plant_type}")
    return configs[plant_type]

def fetch_and_store_data_chunk(start_date, end_date, plant_type='hydro'):
    """
    Fetch and store data for a date range in a single request
    
    Args:
        start_date: datetime.date - Start date for data collection
        end_date: datetime.date - End date for data collection
        plant_type: str - Type of plants ('hydro', 'natural_gas', or 'imported_coal')
    """
    mapping, model = get_plant_config(plant_type)
    
    # Get authentication token
    tgt_token = get_tgt_token(
        current_app.config['USERNAME'],
        current_app.config['PASSWORD']
    )
    
    for version in ['first', 'current']:
        dpp_url = (current_app.config['DPP_FIRST_VERSION_URL'] 
                  if version == 'first' 
                  else current_app.config['DPP_URL'])
        
        batch_data = []
        
        # Fetch data for each plant
        for idx, (o_id, pl_id, plant_name) in enumerate(zip(
            mapping['o_ids'],
            mapping['uevcb_ids'],
            mapping['plant_names']
        )):
            try:
                print(f"Fetching {plant_type} data for plant {plant_name} ({idx + 1}/{len(mapping['plant_names'])})")
                plant_data = fetch_plant_data(start_date, end_date, o_id, pl_id, dpp_url, tgt_token)
                
                if plant_data:
                    current_date = start_date
                    while current_date <= end_date:
                        date_str = current_date.strftime('%Y-%m-%d')
                        if date_str in plant_data:
                            daily_data = plant_data[date_str]
                            batch_data.extend([{
                                'date': current_date,
                                'hour': hour,
                                'plant_name': plant_name,
                                'value': value,
                                'version': version
                            } for hour, value in enumerate(daily_data)])
                        current_date += timedelta(days=1)
                
                time.sleep(0.5)  # Small delay between plants
                    
            except Exception as e:
                current_app.logger.error(f"Error fetching {plant_type} data for {plant_name}: {str(e)}")
                time.sleep(1)
                continue
        
        # Bulk insert data
        if batch_data:
            try:
                model.query.filter(
                    model.date.between(start_date, end_date),
                    model.version == version
                ).delete()
                db.session.bulk_insert_mappings(model, batch_data)
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Error storing {plant_type} data: {str(e)}")
                db.session.rollback()

def fetch_and_store_data(date, plant_type='hydro'):
    """Fetch and store data for a single date"""
    return fetch_and_store_data_chunk(date, date, plant_type)

# Convenience functions for each plant type
def fetch_and_store_hydro_data(date):
    """Fetch and store hydro plant data for a specific date"""
    try:
        # Get authentication token
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        if not tgt_token:
            current_app.logger.error("Failed to get authentication token")
            return
        
        # Create session with retry strategy
        session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504, 406, 408, 429],
            allowed_methods=["POST"]
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=1, pool_maxsize=1)
        session.mount('https://', adapter)
        
        # Process plants in smaller batches
        batch_size = 3
        for i in range(0, len(hydro_mapping['plant_names']), batch_size):
            batch_plants = list(zip(
                hydro_mapping['plant_names'][i:i+batch_size],
                hydro_mapping['o_ids'][i:i+batch_size],
                hydro_mapping['uevcb_ids'][i:i+batch_size]
            ))
            
            for plant_name, o_id, pl_id in batch_plants:
                try:
                    data = fetch_plant_data(
                        start_date=date,
                        end_date=date,
                        org_id=o_id,
                        plant_id=pl_id,
                        url=current_app.config['DPP_FIRST_VERSION_URL'],
                        token=tgt_token
                    )
                    
                    if data and 'items' in data:
                        # Store data in database
                        for item in data['items']:
                            hour = int(item.get('time', '00:00').split(':')[0])
                            value = float(item.get('barajli', 0) or item.get('toplam', 0))
                            
                            heatmap_data = HydroHeatmapData(
                                date=date,
                                hour=hour,
                                plant_name=plant_name,
                                value=value,
                                version='first'
                            )
                            db.session.add(heatmap_data)
                    
                    time.sleep(1)  # Delay between requests
                    
                except Exception as e:
                    current_app.logger.error(f"Error processing {plant_name}: {str(e)}")
                    continue
            
            time.sleep(2)  # Delay between batches
            
        db.session.commit()
        session.close()
        
    except Exception as e:
        current_app.logger.error(f"Error in fetch_and_store_hydro_data: {str(e)}")
        db.session.rollback()

def fetch_and_store_natural_gas_data(date):
    return fetch_and_store_data(date, 'natural_gas')

def fetch_and_store_imported_coal_data(date):
    return fetch_and_store_data(date, 'imported_coal')

def update_daily_data(app, fetch_next_day=False):
    """Update daily data for all plant types"""
    with app.app_context():
        try:
            # Get the target date (tomorrow if fetch_next_day is True)
            target_date = datetime.now(timezone('Europe/Istanbul')).date()
            if fetch_next_day:
                target_date += timedelta(days=1)
            
            app.logger.info(f"Starting daily data update for date: {target_date}")
            
            # Fetch and store data for each plant type
            fetch_and_store_hydro_data(target_date)
            fetch_and_store_natural_gas_data(target_date)
            fetch_and_store_imported_coal_data(target_date)
            
            app.logger.info(f"Completed daily data update for date: {target_date}")
            
        except Exception as e:
            app.logger.error(f"Error in daily data update: {str(e)}")