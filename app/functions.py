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
import dns.resolver
import urllib3
from cachetools import TTLCache
from threading import Lock

# Global session and cache
_session = None
_session_lock = Lock()
_token_cache = TTLCache(maxsize=100, ttl=3600)  # 1 hour TTL
_dns_cache = TTLCache(maxsize=100, ttl=300)  # 5 minutes TTL

def get_session():
    """Get or create a persistent session"""
    global _session
    
    with _session_lock:
        if _session is None:
            _session = requests.Session()
            
            # Configure retries
            retries = Retry(
                total=5,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504, 406, 408, 429],
                allowed_methods=["POST", "GET"],
                raise_on_redirect=False,
                raise_on_status=False
            )
            
            # Configure adapter with longer timeouts
            adapter = HTTPAdapter(
                max_retries=retries,
                pool_connections=25,
                pool_maxsize=25,
                pool_block=True
            )
            
            # Mount for both http and https
            _session.mount('http://', adapter)
            _session.mount('https://', adapter)
            
            # Set default timeouts
            _session.timeout = (30, 90)  # (connect, read)
            
        return _session

def resolve_dns(hostname):
    """Resolve DNS with caching"""
    if hostname in _dns_cache:
        return _dns_cache[hostname]
    
    try:
        answers = dns.resolver.resolve(hostname, 'A')
        ip = str(answers[0])
        _dns_cache[hostname] = ip
        return ip
    except Exception as e:
        current_app.logger.error(f"DNS resolution failed for {hostname}: {str(e)}")
        return hostname

def get_tgt_token(username, password, max_retries=5):
    """Get TGT token with improved connection handling"""
    # Check cache first
    cache_key = f"{username}:{password}"
    if cache_key in _token_cache:
        return _token_cache[cache_key]
    
    tgt_url = "https://giris.epias.com.tr/cas/v1/tickets"
    session = get_session()
    
    # Resolve DNS
    hostname = "giris.epias.com.tr"
    ip = resolve_dns(hostname)
    if ip != hostname:
        tgt_url = tgt_url.replace(hostname, ip)
    
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            # Get TGT
            response = session.post(
                tgt_url,
                data={
                    'username': username,
                    'password': password
                },
                headers={
                    'Host': hostname,
                    'Connection': 'keep-alive'
                },
                verify=True
            )
            
            if response.status_code == 201:
                tgt = response.text
                # Get service ticket
                st_response = session.post(
                    f"{tgt_url}/{tgt}",
                    data={'service': 'https://seffaflik.epias.com.tr'},
                    headers={
                        'Host': hostname,
                        'Connection': 'keep-alive'
                    }
                )
                
                if st_response.status_code == 200:
                    token = st_response.text
                    _token_cache[cache_key] = token
                    return token
            
            retry_count += 1
            current_app.logger.warning(f"Failed to get token (attempt {retry_count}/{max_retries})")
            time.sleep(min(2 ** retry_count + random.uniform(0, 1), 60))
            
        except Exception as e:
            last_error = str(e)
            retry_count += 1
            if retry_count == max_retries:
                current_app.logger.error(f"Failed to get token after {max_retries} retries: {last_error}")
                return None
            current_app.logger.warning(f"Connection error (attempt {retry_count}/{max_retries}): {last_error}")
            time.sleep(min(2 ** retry_count + random.uniform(0, 1), 60))
    
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
    session = get_session()
    
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
    
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            response = session.post(
                url,
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'TGT': token,
                    'Connection': 'keep-alive'
                },
                json=data,
                verify=True
            )
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            last_error = str(e)
            retry_count += 1
            if retry_count == max_retries:
                current_app.logger.error(f"Failed to fetch data after {max_retries} retries: {last_error}")
                return None
            current_app.logger.warning(f"Connection error (attempt {retry_count}/{max_retries}): {last_error}")
            time.sleep(min(2 ** retry_count + random.uniform(0, 1), 60))
    
    return None