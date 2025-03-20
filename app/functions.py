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
import logging

# Function to get the TGT token
def get_tgt_token(username, password, max_retries=5, retry_delay=10):
    """
    Get a TGT token for authentication with the EPIAS API
    
    Args:
        username: EPIAS username
        password: EPIAS password
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        TGT token string
    """
    logger = logging.getLogger(__name__)
    
    # Create a session with retry capability
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    
    # Increase timeout for the authentication request
    timeout = 60  # 60 seconds timeout
    
    for attempt in range(max_retries):
        try:
            # Get TGT
            tgt_response = session.post(
                'https://giris.epias.com.tr/cas/v1/tickets',
                data={'username': username, 'password': password},
                timeout=timeout
            )
            tgt_response.raise_for_status()
            
            # Extract TGT from response
            tgt = tgt_response.text
            
            # Get service ticket
            st_response = session.post(
                f'https://giris.epias.com.tr/cas/v1/tickets/{tgt}',
                data={'service': 'https://seffaflik.epias.com.tr'},
                timeout=timeout
            )
            st_response.raise_for_status()
            
            # Return the service ticket
            return st_response.text
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Authentication attempt {attempt+1}/{max_retries} failed: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Authentication failed after {max_retries} attempts")
                raise

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
    """Fetch plant data with improved error handling and retries"""
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'TGT': token
    }
    
    # Format dates
    try:
        start_str = start_date.strftime('%Y-%m-%d') if isinstance(start_date, (date, datetime)) else datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d') if isinstance(end_date, (date, datetime)) else datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d')
    except (ValueError, TypeError) as e:
        current_app.logger.error(f"Invalid date format: {e}")
        return None
    
    data = {
        'startDate': f"{start_str}T00:00:00+03:00",
        'endDate': f"{end_str}T00:00:00+03:00",
        'region': 'TR1',
        'organizationId': int(org_id),
        'uevcbId': int(plant_id)
    }
    
    session = requests.Session()
    retries = Retry(
        total=max_retries,
        backoff_factor=0.5,  # Reduced backoff factor for faster retries
        status_forcelist=[500, 502, 503, 504, 406],
        allowed_methods=["POST"]
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))
    
    for retry_count in range(max_retries):
        try:
            response = session.post(
                url, 
                headers=headers, 
                json=data,
                timeout=15  # Reduced timeout for faster failure detection
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if retry_count == max_retries - 1:
                current_app.logger.error(f"Error in fetch_plant_data after {max_retries} retries: {str(e)}")
                return None
            time.sleep(0.5 * (2 ** retry_count))  # Faster exponential backoff