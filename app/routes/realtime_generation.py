from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timedelta
import requests
from dateutil.relativedelta import relativedelta
import logging
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3 import Retry
from ..functions import get_tgt_token, asutc, invalidates_or_none
import pandas as pd

realtime_generation_bp = Blueprint('realtime_generation', __name__)

def fetch_realtime_data(start_date, end_date):
    """Fetch realtime generation data from EPIAS API"""
    try:
        # Set up session with retries (matching main.py pattern)
        session = Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        
        # Get TGT token (matching main.py pattern)
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        
        payload = {
            "startDate": asutc(start_date),
            "endDate": asutc(end_date)
        }
        
        # Make request (matching main.py pattern)
        res = session.post(
            current_app.config['REALTIME_URL'],
            json=payload,
            headers={"TGT": tgt_token},
            timeout=30
        )
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logging.error(f"Error From fetch_realtime_data: {str(e)}")
        return None

def fetch_dpp_data(start_date, end_date):
    """Fetch DPP data from EPIAS API"""
    try:
        # Set up session with retries (matching main.py pattern)
        session = Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        
        # Get TGT token (matching main.py pattern)
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        
        payload = {
            "startDate": asutc(start_date),
            "endDate": asutc(end_date),
            "region": "TR1"
        }
        
        # Make request (matching main.py pattern)
        res = session.post(
            current_app.config['DPP_URL'],
            json=payload,
            headers={"TGT": tgt_token},
            timeout=30
        )
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logging.error(f"Error From fetch_dpp_data: {str(e)}")
        return None

def calculate_period_averages(data, period='daily'):
    """
    Calculate averages based on the specified period
    period: 'daily', 'weekly', 'monthly', 'yearly'
    """
    # Convert data items to DataFrame for easier manipulation
    df = pd.DataFrame(data['items'])
    df['date'] = pd.to_datetime(df['date'])
    
    # Identify numeric columns (exclude 'date' and 'hour')
    numeric_columns = df.select_dtypes(include=['float64', 'int64']).columns
    
    # Set date as index
    df.set_index('date', inplace=True)
    
    # Define grouping based on period
    if period == 'daily':
        return data  # Return original data for daily view
    elif period == 'weekly':
        grouped = df[numeric_columns].resample('W').mean()
    elif period == 'monthly':
        grouped = df[numeric_columns].resample('ME').mean()
    elif period == 'yearly':
        grouped = df[numeric_columns].resample('Y').mean()
    else:
        return data
    
    # Convert back to the original format
    items = []
    for date, row in grouped.iterrows():
        item = {
            'date': date.strftime('%Y-%m-%dT%H:%M:%S+03:00'),
            'hour': '00:00',  # For averaged data, we use 00:00
        }
        # Add all numeric columns
        for col in numeric_columns:
            item[col] = float(row[col])
        items.append(item)
    
    # Return data in original format with averaged items
    return {
        'items': items,
        'totals': data['totals']  # Keep original totals
    }

def fetch_data_in_chunks(start_date, end_date, fetch_func):
    """
    Fetch data in 3-month chunks to handle EPIAS restrictions
    """
    all_data = None
    current_start = start_date
    
    while current_start < end_date:
        # Calculate chunk end date (3 months or end_date, whichever is earlier)
        chunk_end = min(
            current_start + relativedelta(months=3),
            end_date
        )
        
        # Fetch chunk data
        chunk_data = fetch_func(current_start, chunk_end)
        if not chunk_data:
            return None
            
        # Initialize all_data with first chunk
        if all_data is None:
            all_data = {
                'items': chunk_data['items'],
                'totals': {k: 0 for k in chunk_data['totals'].keys()}  # Initialize totals with zeros
            }
        else:
            # Append items from chunk
            all_data['items'].extend(chunk_data['items'])
        
        # Update totals (ensure values are numeric)
        for key in chunk_data['totals']:
            try:
                value = float(chunk_data['totals'][key])
                if key in all_data['totals']:
                    all_data['totals'][key] += value
                else:
                    all_data['totals'][key] = value
            except (TypeError, ValueError) as e:
                logging.warning(f"Could not process total for key {key}: {str(e)}")
                all_data['totals'][key] = 0
        
        # Move to next chunk
        current_start = chunk_end
    
    return all_data

@realtime_generation_bp.route('/api/generation-comparison', methods=['POST'])
def get_generation_comparison():
    try:
        args = request.get_json()
        start = args.get('start')
        end = args.get('end')
        period = request.args.get('range', 'daily')  # Get period from query params
        
        valid_dates = invalidates_or_none(start, end)
        if valid_dates['code'] != 200:
            return jsonify(valid_dates), 400
            
        start_date = valid_dates['start_date']
        end_date = valid_dates['end_date']

        # # For yearly data, use chunked fetching
        # if period == 'yearly':
        #     realtime_data = fetch_data_in_chunks(start_date, end_date, fetch_realtime_data)
        #     if not realtime_data:
        #         return jsonify({
        #             'code': 500,
        #             'message': 'unknown error unable to load realtime data.'
        #         }), 500

        #     dpp_data = fetch_data_in_chunks(start_date, end_date, fetch_dpp_data)
        #     if not dpp_data:
        #         return jsonify({
        #             'code': 500,
        #             'message': 'unknown error unable to load DPP data.'
        #         }), 500
        # else:
        # Regular fetching for other periods
        realtime_data = fetch_realtime_data(start_date, end_date)
        if not realtime_data:
            return jsonify({
                'code': 500,
                'message': 'unknown error unable to load realtime data.'
            }), 500

        dpp_data = fetch_dpp_data(start_date, end_date)
        if not dpp_data:
            return jsonify({
                'code': 500,
                'message': 'unknown error unable to load DPP data.'
            }), 500

        # Calculate averages based on period
        realtime_data = calculate_period_averages(realtime_data, period)
        dpp_data = calculate_period_averages(dpp_data, period)

        # Process and combine the data
        processed_data = {
            'realtime': realtime_data,
            'dpp': dpp_data,
            'differences': calculate_differences(realtime_data, dpp_data),
            'metadata': {
                'start_date': asutc(start_date),
                'end_date': asutc(end_date),
                'period': period
            }
        }
        
        return jsonify({'code': 200, 'data': processed_data})
        
    except Exception as e:
        print('Error From get_generation_comparison:{}.'.format(str(e)))
        return jsonify({
            'code': 500,
            'message': 'unknown error unable to load comparison data.'
        }), 500

def calculate_differences(realtime_data, dpp_data):
    """Calculate differences between realtime and DPP data"""
    differences = {
        'items': [],
        'totals': {}
    }
    
    field_mapping = {
        'naturalGas': 'dogalgaz',
        'wind': 'ruzgar',
        'lignite': 'linyit',
        'importCoal': 'ithalKomur',
        'fueloil': 'fuelOil',
        'geothermal': 'jeotermal',
        'dammedHydro': 'barajli',
        'naphta': 'nafta',
        'biomass': 'biokutle',
        'river': 'akarsu'
    }
    
    # Process items
    realtime_dict = {item['date']: item for item in realtime_data['items']}
    dpp_dict = {item['date']: item for item in dpp_data['items']}
    
    all_dates = sorted(set(realtime_dict.keys()) | set(dpp_dict.keys()))
    
    for date in all_dates:
        if date in realtime_dict and date in dpp_dict:
            rt_item = realtime_dict[date]
            dpp_item = dpp_dict[date]
            
            diff_item = {
                'date': date,
                'hour': rt_item['hour'],
                'total': rt_item['total'] - dpp_item['toplam']
            }
            
            for rt_field, dpp_field in field_mapping.items():
                if rt_field in rt_item and dpp_field in dpp_item:
                    diff_item[rt_field] = rt_item[rt_field] - dpp_item[dpp_field]
            
            differences['items'].append(diff_item)
    
    # Calculate total differences
    rt_totals = realtime_data['totals']
    dpp_totals = dpp_data['totals']
    
    differences['totals'] = {
        'total': rt_totals['totalTotal'] - dpp_totals['toplamTotal']
    }
    
    for rt_field, dpp_field in field_mapping.items():
        rt_total_field = f'{rt_field}Total'
        dpp_total_field = f'{dpp_field}Total'
        
        if rt_total_field in rt_totals and dpp_total_field in dpp_totals:
            differences['totals'][rt_field] = rt_totals[rt_total_field] - dpp_totals[dpp_total_field]
    
    return differences 