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
import logging

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

def create_session():
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def fetch_data_from_api(url, params=None, timeout=60):
    session = create_session()
    try:
        response = session.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logging.error(f"Timeout while fetching data from {url}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data from {url}: {str(e)}")
        return None
    finally:
        session.close()

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
    return fetch_and_store_data(date, 'hydro')

def fetch_and_store_natural_gas_data(date):
    return fetch_and_store_data(date, 'natural_gas')

def fetch_and_store_imported_coal_data(date):
    return fetch_and_store_data(date, 'imported_coal')

def fetch_and_store_hydro_data():
    # Use the new fetch_data_from_api function
    data = fetch_data_from_api("https://giris.epias.com.tr/...", timeout=60)
    if data:
        # Process and store data
        pass
    else:
        logging.error("Failed to fetch hydro data from API")

def fetch_and_store_natural_gas_data():
    # Use the new fetch_data_from_api function
    data = fetch_data_from_api("https://giris.epias.com.tr/...", timeout=60)
    if data:
        # Process and store data
        pass
    else:
        logging.error("Failed to fetch natural gas data from API")

def fetch_and_store_imported_coal_data():
    # Use the new fetch_data_from_api function
    data = fetch_data_from_api("https://giris.epias.com.tr/...", timeout=60)
    if data:
        # Process and store data
        pass
    else:
        logging.error("Failed to fetch imported coal data from API")