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

# Function to get the TGT token
def get_tgt_token(username, password, max_retries=5):
    """Get TGT token with improved retry handling and timeouts"""
    tgt_url = "https://giris.epias.com.tr/cas/v1/tickets"
    headers = {"Accept": "text/plain"}
    
    retry_count = 0
    while retry_count < max_retries:
        try:
            session = requests.Session()
            # Configure retry strategy with longer timeouts
            retries = Retry(
                total=5,
                backoff_factor=2,  # Increased backoff
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
                connect=5,  # Maximum number of connect retries
                read=5,     # Maximum number of read retries
                backoff_jitter=1  # Add jitter to avoid thundering herd
            )
            adapter = HTTPAdapter(
                max_retries=retries,
                pool_connections=3,
                pool_maxsize=3,
                pool_block=True
            )
            session.mount('https://', adapter)
            
            # Make request with increased timeouts
            response = session.post(
                tgt_url, 
                data={"username": username, "password": password}, 
                headers=headers,
                timeout=(30, 90)  # (connect timeout, read timeout)
            )
            response.raise_for_status()
            return response.text.strip()
            
        except requests.exceptions.RequestException as e:
            retry_count += 1
            if retry_count == max_retries:
                raise Exception(f"Failed to obtain TGT token after {max_retries} retries: {str(e)}")
            
            # Calculate sleep time with exponential backoff and maximum cap
            sleep_time = min(300, 2 ** (retry_count + 2))  # Cap at 5 minutes
            print(f"Token request failed, retrying in {sleep_time} seconds... ({retry_count}/{max_retries})")
            time.sleep(sleep_time)
        finally:
            session.close()

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