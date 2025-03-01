import pytz
from requests import post
from flask import current_app
from datetime import datetime

# Function to get the TGT token
def get_tgt_token(username, password):
    tgt_url = "https://giris.epias.com.tr/cas/v1/tickets"
    headers = {
        "Accept": "text/plain"
    }
    response = post(tgt_url, data={"username": username, "password": password}, headers=headers)
    
    if response.status_code == 201:
        return response.text.strip()
    raise Exception("Failed to obtain TGT token.")

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