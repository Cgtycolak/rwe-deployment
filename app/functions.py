import pytz
from requests import post
from flask import current_app
from datetime import datetime, date
from datetime import datetime
import time
from requests import Session
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import requests
import random

# Function to get the TGT token
def get_tgt_token(username, password, max_retries=5):
    """Get TGT token with improved connection handling"""
    tgt_url = "https://giris.epias.com.tr/cas/v1/tickets"
    headers = {"Accept": "text/plain"}
    
    # Create session with retry strategy
    session = requests.Session()
    retries = Retry(
        total=max_retries,
        backoff_factor=2,  # Increased backoff
        status_forcelist=[500, 502, 503, 504, 406, 408, 429],
        allowed_methods=["POST", "GET"]
    )
    
    # Configure connection pooling and timeouts
    adapter = HTTPAdapter(
        max_retries=retries,
        pool_connections=10,
        pool_maxsize=10,
        pool_block=False
    )
    session.mount('https://', adapter)
    
    retry_count = 0
    while retry_count < max_retries:
        try:
            # Get TGT
            response = session.post(
                tgt_url,
                headers=headers,
                data={
                    "username": username,
                    "password": password
                },
                timeout=(10, 30)  # (connect timeout, read timeout)
            )
            response.raise_for_status()
            tgt = response.text
            
            # Get service ticket
            st_response = session.post(
                f"{tgt_url}/{tgt}",
                headers=headers,
                data={"service": "https://seffaflik.epias.com.tr"},
                timeout=(10, 30)
            )
            st_response.raise_for_status()
            
            return st_response.text
            
        except requests.exceptions.RequestException as e:
            retry_count += 1
            if retry_count == max_retries:
                current_app.logger.error(f"Failed to get TGT token after {max_retries} retries: {str(e)}")
                return None
            
            # Exponential backoff with jitter
            sleep_time = (2 ** retry_count) + random.uniform(0, 1)
            time.sleep(sleep_time)
            continue
    
    return None

def asutc(date_str):
    """Convert date string to UTC format required by the API"""
    if isinstance(date_str, str):
        # If it's already in the format we want, return it
        if 'T' in date_str and '+' in date_str:
            return date_str
        # Otherwise, format it properly
        return f"{date_str}T00:00:00+03:00"
    return date_str.strftime("%Y-%m-%dT00:00:00+03:00")

# return dates inputs or invalid response object to return jsonifined
def invalidates_or_none(start, end):
    if not start or not end:
        return {'code': 400, 'message': 'missing start or end data.'}

    # Parse dates
    try:
        start_date = datetime.fromisoformat(start)
        end_date = datetime.fromisoformat(end)
    except ValueError as ve:
        return {'code': 400, 'message': 'Invalid date format.'}

    # validate date range
    if start_date > end_date:
        return {'code': 400, 'message': 'End Date must be bigger than Start Date.'}
    
    res = {'code': 200, 'start_date': start_date, 'end_date': end_date}

    if not start_date or not end_date:
        return {'code': 500, 'message': 'system error.'}

    return {'code': 200, 'start_date': start_date, 'end_date': end_date}

def fetch_plant_data(start_date, end_date, org_id, plant_id, url, token, max_retries=5):
    """Fetch plant data with improved connection handling"""
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'TGT': token
    }
    
    # Format dates
    if isinstance(start_date, (date, datetime)):
        start_str = start_date.strftime('%Y-%m-%d')
    else:
        try:
            start_str = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            current_app.logger.error(f"Invalid start_date format: {start_date}")
            return None
    
    if isinstance(end_date, (date, datetime)):
        end_str = end_date.strftime('%Y-%m-%d')
    else:
        try:
            end_str = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            current_app.logger.error(f"Invalid end_date format: {end_date}")
            return None
    
    data = {
        'startDate': f"{start_str}T00:00:00+03:00",
        'endDate': f"{end_str}T00:00:00+03:00",
        'region': 'TR1',
        'organizationId': int(org_id),
        'uevcbId': int(plant_id)
    }
    
    # Create session with retry strategy
    session = requests.Session()
    retries = Retry(
        total=max_retries,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504, 406, 408, 429],
        allowed_methods=["POST"]
    )
    
    # Configure connection pooling and timeouts
    adapter = HTTPAdapter(
        max_retries=retries,
        pool_connections=10,
        pool_maxsize=10,
        pool_block=False
    )
    session.mount('https://', adapter)
    
    retry_count = 0
    while retry_count < max_retries:
        try:
            response = session.post(
                url,
                headers=headers,
                json=data,
                timeout=(10, 30)  # (connect timeout, read timeout)
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            retry_count += 1
            if retry_count == max_retries:
                current_app.logger.error(f"Error in fetch_plant_data after {max_retries} retries: {str(e)}")
                return None
            
            # Exponential backoff with jitter
            sleep_time = (2 ** retry_count) + random.uniform(0, 1)
            time.sleep(sleep_time)
            continue
    
    return None