import sys
import time
from datetime import datetime, timedelta, timezone
from flask import abort, app, Blueprint, session, render_template, redirect, url_for, Response, request, jsonify, Request, Response, current_app, flash
from requests import post, Session
from .functions import get_tgt_token, asutc, invalidates_or_none, fetch_plant_data
from requests.adapters import HTTPAdapter
from urllib3 import Retry
import pandas as pd
import numpy as np
import pytz
from .mappings import hydro_mapping, plant_mapping, import_coal_mapping
from .models.heatmap import HydroHeatmapData, NaturalGasHeatmapData, ImportedCoalHeatmapData
from .models.realtime import HydroRealtimeData, NaturalGasRealtimeData
from .database.config import db
import requests
import json
from .models.production import ProductionData
import plotly.graph_objects as go
from sqlalchemy import text
import os
from app.models.demand import DemandData
from sqlalchemy import extract
from app.models.unlicensed_solar import UnlicensedSolarData
from app.models.licensed_solar import LicensedSolarData
import zipfile
import tempfile
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine
from darts.metrics import wmape, rmse, r2_score
from darts import TimeSeries
from functools import wraps

# Conditionally set pandas option if it exists (available in pandas 2.1.0+)
try:
    pd.set_option('future.no_silent_downcasting', True)
except pd._config.config.OptionError:
    # Option doesn't exist in this pandas version, skip it
    pass

main = Blueprint('main', __name__)

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Get credentials from config
        correct_username = current_app.config.get('DASHBOARD_USERNAME', 'admin')
        correct_password = current_app.config.get('DASHBOARD_PASSWORD', 'admin')
        
        if username == correct_username and password == correct_password:
            session['authenticated'] = True
            session['username'] = username
            session.permanent = True
            return redirect(url_for('main.index'))
        else:
            return render_template('login.html', error='Invalid username or password')
    
    # If already authenticated, redirect to dashboard
    if session.get('authenticated'):
        return redirect(url_for('main.index'))
    
    return render_template('login.html')

@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))

@main.route('/', methods=['GET'])
@login_required
def index():
    urls = {
        'getOrgs': url_for('main.get_orgs'),
        'getUevcbids': url_for('main.get_orgs_uevcbids'),
        'getDPPTable': url_for('main.get_dpp_data'),
        'getPowerPlants': url_for('main.get_powerplants'),
        'getRealtimeData': url_for('main.get_realtime_data')
    }
    return render_template('index.html', urls=urls)

@main.route('/get_orgs', methods=['POST'])
def get_orgs():
    try:
        args = request.get_json()
        start = args.get('start')
        end = args.get('end')
        valid_dates = invalidates_or_none(start, end)
        if valid_dates['code'] == 200:
            # send post request to api and load the organizations
            tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
            res = post(
                current_app.config['ORGANIZATION_LIST_URL'],
                json={
                    "startDate": asutc(valid_dates['start_date']),
                    "endDate":  asutc(valid_dates['end_date'])
                }, headers={'TGT': tgt_token})
            res.raise_for_status()
            data = res.json().get('items', [])
            return jsonify({'code': 200, 'data': data})
        else:
            # return the invalid date valdation res to client with message related
            return jsonify(valid_dates), 400
    except:
        print('Error From get_orgs:{}.'.format(sys.exc_info()))
        return jsonify({'code': 500, 'message': 'unknown error unable to load organizations, please check connection and try again.'}), 500

@main.route('/get_orgs_uevcbids', methods=['POST'])
def get_orgs_uevcbids():
    try:
        args = request.get_json()
        orgIds = args.get('orgIds')

        if not orgIds or not isinstance(orgIds, list):
            return {'code': 400, 'message': 'Unable to load UEVCB options please select organizations'}

        system_orgs = dict([(org, []) for org in orgIds])

        start = args.get('start')
        end = args.get('end')
        valid_dates = invalidates_or_none(start, end)

        if valid_dates['code'] != 200:
            # return the invalid date valdation res to client with message related
            return jsonify(valid_dates), 400
        

        # get orgs uevcbid and remember which uevcbids belong to which org
        # Set up session with retries
        session = Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 502, 503, 504])  # Add 429 to retry on rate limit
        session.mount('https://', HTTPAdapter(max_retries=retries))
        print(session)

        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        uevcb_list_url = current_app.config.get('UEVCB_URL')
        for org_id, _ in system_orgs.items():
            res = session.post(uevcb_list_url, json={
                            "startDate": asutc(valid_dates['start_date']),
                            "endDate": asutc(valid_dates['end_date']),
                            "organizationId": org_id
                        }, headers={"TGT": tgt_token}, timeout=30)
            res.raise_for_status()
            system_orgs[org_id] = res.json().get('items', [])
            time.sleep(0.2)
            
        return jsonify({'code': 200, 'data': system_orgs})

    except:
        print('Error From get_orgs:{}.'.format(sys.exc_info()))
        return jsonify({'code': 500, 'message': 'unknown error unable to load uevcbids.'}), 500



@main.route('/dpp_table', methods=['POST'])
def get_dpp_data():
    try:
        args = request.get_json()
        # use same payload data obj as resp to async with js
        orgsData = args.get('orgsData')

        if not orgsData or not isinstance(orgsData, dict):
            return {'code': 400, 'message': 'Unable to load UEVCB options please select organizations'}
        
        #print(orgsData)
        

        start = args.get('start')
        end = args.get('end')
        valid_dates = invalidates_or_none(start, end)

        if valid_dates['code'] != 200:
            # return the invalid date valdation res to client with message related
            return jsonify(valid_dates), 400
        
        session = Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 502, 503, 504])  # Add 429 to retry on rate limit
        session.mount('https://', HTTPAdapter(max_retries=retries))

        dpp_url = current_app.config.get('DPP_URL')
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        headers={"TGT": tgt_token}

        cols = None
        for org_id, org in orgsData.items():
            for i in range(len(org['uevcbids'])):
                # org['uevcbids'][ui] (update global)  org['uevcbids'][ui]['rows']
                # send server
                data3 = {
                    "startDate": asutc(valid_dates['start_date']),
                    "endDate": asutc(valid_dates['end_date']),
                    "region": "TR1",                    
                    "organizationId": str(org_id),
                    "uevcbId": str(org['uevcbids'][i]['id']),
                }
                res = session.post(dpp_url, json=data3, headers=headers, timeout=30)
                res.raise_for_status()
                data = res.json()
                items = data.get('items', [])
                df3 = pd.DataFrame.from_records(items)

                # df3['date'] = pd.to_datetime(df3['date']) db

                # pd updates
                df3.rename(columns={
                    "time": "HOUR",
                    "toplam": "TOTAL", 
                    "dogalgaz": "NG",
                    "ruzgar": "WIND", 
                    "linyit": "LIGNITE",
                    "tasKomur": "HARDCOAL",
                    "ithalKomur": "IMPORTCOAL", 
                    "fuelOil": "FUELOIL",
                    "barajli": "HEPP",
                    "akarsu": "ROR",
                    "nafta": "NAPHTHA",
                    "biokutle": "BIO",
                    "jeotermal": "GEOTHERMAL",
                    "diger": "OTHER"
                }, inplace=True)

                # add 4 columns 2 with speacifed index and reamning automtic with pandas
                total_rows = len(df3)
                df3.insert(0, 'Organization', [org['organizationName']]*total_rows)
                df3.insert(1, 'UEVCB', [org['uevcbids'][i]['name']]*total_rows)

                df3['ETSO_Code'] = org['organizationEtsoCode']
                df3['UEVCB_EIC'] = org['uevcbids'][i]['eic']

                #df3['Index'] = df3.index
                print(df3.head())

                data_arr = pd.DataFrame.to_records(df3,index=False).tolist()
                
                cols = tuple(df3.columns) if cols is None else cols
                # create array of objects row each object (columns and value of cell)
                orgsData[org_id]['uevcbids'][i]['rows'] = [dict(zip(cols, row)) for row in data_arr]

                time.sleep(0.5)
        return jsonify({
            'code': 200, 
            'data': {'orgsData': orgsData, 'columns': cols}
        })

    except Exception as e:
        print('Error From get_orgs:{}.'.format(sys.exc_info()))
        return jsonify({'code': 500, 'message': 'unknown error unable to load uevcbids.'}), 500

@main.route('/powerplants', methods=['GET'])
def get_powerplants():
    try:
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        session = Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        
        res = session.get(
            current_app.config['POWERPLANT_URL'],
            headers={'TGT': tgt_token}
        )
        res.raise_for_status()
        
        return jsonify({
            'code': 200, 
            'data': res.json().get('items', [])
        })
    except Exception as e:
        print('Error From get_powerplants:', str(e))
        return jsonify({
            'code': 500, 
            'message': 'Unable to load power plants list.'
        }), 500

@main.route('/realtime_data', methods=['POST'])
def get_realtime_data():
    try:
        args = request.get_json()
        powerplant_id = args.get('powerPlantId')
        start = args.get('start')
        end = args.get('end')

        if not powerplant_id:
            return jsonify({'code': 400, 'message': 'Power plant ID is required'}), 400

        # Get powerplant name first
        session = Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))

        # Get powerplant details
        plant_res = session.get(
            current_app.config['POWERPLANT_URL'],
            headers={'TGT': tgt_token}
        )
        plant_res.raise_for_status()
        plants = plant_res.json().get('items', [])
        plant_name = next((p['name'] for p in plants if str(p['id']) == str(powerplant_id)), 'Unknown Plant')

        # Validate dates
        valid_dates = invalidates_or_none(start, end)
        if valid_dates['code'] != 200:
            return jsonify(valid_dates), 400

        # Convert date strings to datetime objects
        if isinstance(valid_dates['start_date'], str):
            start_date = datetime.strptime(valid_dates['start_date'], '%Y-%m-%d')
        else:
            start_date = valid_dates['start_date']
            
        if isinstance(valid_dates['end_date'], str):
            end_date = datetime.strptime(valid_dates['end_date'], '%Y-%m-%d')
        else:
            end_date = valid_dates['end_date']

        # Check if end date is today or tomorrow
        today = datetime.now().date()
        if end_date.date() >= today:
            return jsonify({
                'code': 400, 
                'message': 'Only data up to one day before the current date can be viewed for realtime data.'
            }), 400

        all_data = []
        current_date = start_date
        while current_date <= end_date:
            try:
                request_data = {
                    "startDate": f"{current_date.strftime('%Y-%m-%d')}T00:00:00+03:00",
                    "endDate": f"{current_date.strftime('%Y-%m-%d')}T23:59:59+03:00",
                    "powerPlantId": str(powerplant_id)
                }
                res = session.post(
                    current_app.config['REALTIME_URL'],
                    json=request_data,
                    headers={'TGT': tgt_token}
                )
                res.raise_for_status()
                day_data = res.json().get('items', [])
                all_data.extend(day_data)
                
            except Exception as e:
                print(f"Error fetching data for {current_date.date()}: {str(e)}")
            
            current_date += timedelta(days=1)

        # Process all collected data
        processed_data = []
        for row in all_data:
            processed_row = {
                'PowerPlant': plant_name,
                'DATE': row['date'].split('T')[0],
                'HOUR': row['hour'],
                'TOTAL': row.get('total', 0),
                'NG': row.get('naturalGas', 0),
                'WIND': row.get('wind', 0),
                'LIGNITE': row.get('lignite', 0),
                'HARDCOAL': row.get('blackCoal', 0),
                'IMPORTCOAL': row.get('importCoal', 0),
                'FUELOIL': row.get('fueloil', 0),
                'HEPP': row.get('dammedHydro', 0),
                'ROR': row.get('river', 0),
                'NAPHTHA': row.get('naphta', 0),
                'BIO': row.get('biomass', 0),
                'GEOTHERMAL': row.get('geothermal', 0)
            }
            processed_data.append(processed_row)

        # Sort data by date and hour
        processed_data.sort(key=lambda x: (x['DATE'], x['HOUR']))

        columns = ['PowerPlant', 'DATE', 'HOUR', 'TOTAL', 'NG', 'WIND', 'LIGNITE', 'HARDCOAL',
                  'IMPORTCOAL', 'FUELOIL', 'HEPP', 'ROR', 'NAPHTHA', 'BIO', 'GEOTHERMAL']

        return jsonify({
            'code': 200,
            'data': processed_data,
            'columns': columns
        })

    except Exception as e:
        print('Error From get_realtime_data:', str(e))
        error_message = str(e)
        if 'En son bir gün öncesine' in error_message:
            return jsonify({
                'code': 400,
                'message': 'Only data up to one day before the current date can be viewed for realtime data.'
            }), 400
        return jsonify({'code': 500, 'message': 'Unable to load realtime data.'}), 500

@main.route('/get_aic_data', methods=['GET'])
def get_aic_data():
    try:
        range_type = request.args.get('range', 'week')
        print(f'Getting generation data for range: {range_type}')
        
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        
        # Calculate date range based on selection
        end_date = datetime.now()
        if range_type == 'week':
            start_date = end_date - timedelta(days=7)
        elif range_type == 'month':
            start_date = end_date - timedelta(days=30)
        elif range_type == 'year':
            start_date = end_date - timedelta(days=365)
        elif range_type == '5year':
            start_date = end_date - timedelta(days=1825)
        else:
            start_date = end_date - timedelta(days=7)
        
        start_str = start_date.strftime("%Y-%m-%dT00:00:00+03:00")
        end_str = end_date.strftime("%Y-%m-%dT23:00:00+03:00")
        
        print(f'Date range: {start_str} to {end_str}')

        # Set up session with retries
        session = Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        
        # Fetch data sequentially
        all_data = {}
        
        # Fetch AIC data
        aic_response = session.post(
            'https://seffaflik.epias.com.tr/electricity-service/v1/generation/data/aic',
            json={"startDate": start_str, "endDate": end_str, "region": "TR1"},
            headers={'TGT': tgt_token}
        )
        aic_response.raise_for_status()
        all_data['aic'] = aic_response.json().get('items', [])
        
        # Fetch realtime data
        realtime_response = session.post(
            'https://seffaflik.epias.com.tr/electricity-service/v1/generation/data/realtime-generation',
            json={"startDate": start_str, "endDate": end_str},
            headers={'TGT': tgt_token}
        )
        realtime_response.raise_for_status()
        all_data['realtime'] = realtime_response.json().get('items', [])
        
        # Fetch DPP data
        dpp_response = session.post(
            'https://seffaflik.epias.com.tr/electricity-service/v1/generation/data/dpp',
            json={"startDate": start_str, "endDate": end_str, "region": "TR1"},
            headers={'TGT': tgt_token}
        )
        dpp_response.raise_for_status()
        all_data['dpp'] = dpp_response.json().get('items', [])

        # Check if all data sources returned data
        if not all(all_data.values()):
            return jsonify({
                'code': 400,
                'message': 'Some data sources returned no data'
            }), 400
        
        return jsonify({
            'code': 200,
            'data': all_data
        })

    except Exception as e:
        print('Error From get_aic_data:', str(e))
        return jsonify({
            'code': 500,
            'message': f'Unable to load generation data: {str(e)}'
        }), 500


@main.route('/heatmap_data', methods=['POST'])
def heatmap_data():
    try:
        data = request.json
        date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        version = data.get('version', 'first')
        
        # First try to get data from database
        heatmap_data = NaturalGasHeatmapData.query.filter_by(
            date=date,
            version=version
        ).all()
        
        if not heatmap_data:
            current_app.logger.info(f"No natural gas data in DB for {date}, fetching from API...")
            
            # Get authentication token and URL
            dpp_url = current_app.config['DPP_FIRST_VERSION_URL'] if version == 'first' else current_app.config['DPP_URL']
            tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
            
            # Initialize DataFrame with hours and fill with 0
            hours = [f"{str(i).zfill(2)}:00" for i in range(24)]
            df = pd.DataFrame(0, index=hours, columns=plant_mapping['plant_names'])
            
            # Create session with retry strategy
            session = requests.Session()
            retries = Retry(
                total=5,
                backoff_factor=1,
                status_forcelist=[500, 502, 503, 504, 406],
                allowed_methods=["POST"]
            )
            session.mount('https://', HTTPAdapter(max_retries=retries))
            
            # Iterate through all plants with their IDs
            for plant_name, o_id, pl_id in zip(
                plant_mapping['plant_names'],
                plant_mapping['o_ids'],
                plant_mapping['uevcb_ids']
            ):
                try:
                    response_data = fetch_plant_data(
                        start_date=date,
                        end_date=date,
                        org_id=o_id,
                        plant_id=pl_id,
                        url=dpp_url,
                        token=tgt_token
                    )
                    
                    if response_data and isinstance(response_data, dict):
                        current_app.logger.info(f"Got response for {plant_name}: {str(response_data)[:200]}...")
                        
                        if 'items' in response_data:
                            for item in response_data['items']:
                                try:
                                    hour = item.get('time', '00:00').split(':')[0]
                                    toplam = item.get('toplam')
                                    
                                    # Skip if toplam is None or not convertible to float
                                    if toplam is not None:
                                        try:
                                            value = float(toplam)
                                            df.at[f"{hour.zfill(2)}:00", plant_name] = value
                                        except (ValueError, TypeError):
                                            current_app.logger.warning(f"Invalid value for {plant_name} at hour {hour}: {toplam}")
                                            continue
                                except (KeyError, AttributeError) as e:
                                    current_app.logger.error(f"Error processing data point for {plant_name}: {str(e)}")
                                    continue
                        else:
                            current_app.logger.warning(f"No items in response for {plant_name}")
                    else:
                        current_app.logger.error(f"Invalid response for {plant_name}: {response_data}")
                    
                    time.sleep(0.5)  # Small delay between API calls
                    
                except Exception as e:
                    current_app.logger.error(f"Error fetching data for {plant_name}: {str(e)}")
                    continue
            
            # Process the dataframe
            result = {
                "code": 200,
                "data": {
                    "hours": df.index.tolist(),
                    "plants": [f"{name}--{capacity} Mw" for name, capacity in zip(
                        plant_mapping['plant_names'],
                        plant_mapping['capacities']
                    )],
                    "values": df.values.tolist()
                }
            }
            
            return jsonify(result)
        
        # If we have data in DB, process it as before
        df = process_heatmap_data(heatmap_data, plant_mapping)
        
        if df.empty:
            return jsonify({
                "code": 404,
                "error": f"No data available for date {date}"
            })
        
        return jsonify({
            "code": 200,
            "data": {
                "hours": df.index.tolist(),
                "plants": [f"{name}--{capacity} Mw" for name, capacity in zip(
                    plant_mapping['plant_names'],
                    plant_mapping['capacities']
                )],
                "values": df.values.tolist()
            }
        })

    except ValueError as ve:
        return jsonify({"code": 400, "error": f"Invalid date format: {str(ve)}"})
    except Exception as e:
        current_app.logger.error(f"Error in heatmap_data: {str(e)}")
        return jsonify({"code": 500, "error": str(e)}), 500

@main.route('/realtime_heatmap_data', methods=['POST'])
def realtime_heatmap_data():
    try:
        data = request.json
        selected_date = data.get('date')
        
        if not selected_date:
            return jsonify({"code": 400, "error": "Missing 'date' parameter"})

        # Convert date string to date object
        date = datetime.strptime(selected_date, '%Y-%m-%d').date()

        # First try to get data from database
        heatmap_data = NaturalGasRealtimeData.query.filter_by(
            date=date
        ).all()

        # If we have data in database, process and return it
        if heatmap_data:
            df = pd.DataFrame(index=[f"{str(i).zfill(2)}:00" for i in range(24)], 
                            columns=plant_mapping['plant_names'])
            
            for record in heatmap_data:
                hour = f"{str(record.hour).zfill(2)}:00"
                df.at[hour, record.plant_name] = record.value

            # Replace NaN values with 0
            df = df.fillna(0)

            return jsonify({
                "code": 200,
                "data": {
                    "hours": df.index.tolist(),
                    "plants": [f"{name}--{capacity} Mw" for name, capacity in zip(
                        plant_mapping['plant_names'],
                        plant_mapping['capacities']
                    )],
                    "values": df.values.tolist()
                }
            })

        # If no data in database, fetch from API
        hours = [f"{str(i).zfill(2)}:00" for i in range(24)]
        df = pd.DataFrame(index=hours, columns=plant_mapping['plant_names'])
        
        # Get authentication token
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        
        # Create mappings for plant IDs
        p_id_count = {}
        for p_id in plant_mapping['p_ids']:
            p_id_count[p_id] = plant_mapping['p_ids'].count(p_id)

        p_id_indices = {}
        for idx, p_id in enumerate(plant_mapping['p_ids']):
            if p_id not in p_id_indices:
                p_id_indices[p_id] = []
            p_id_indices[p_id].append(idx)

        # Fetch realtime data for each unique powerplant
        batch_data = []
        unique_p_ids = set(plant_mapping['p_ids'])
        for p_id in unique_p_ids:
            try:
                print(f"Fetching realtime data for powerplant ID: {p_id}")
                
                request_data = {
                    "startDate": f"{selected_date}T00:00:00+03:00",
                    "endDate": f"{selected_date}T23:59:59+03:00",
                    "powerPlantId": str(p_id)
                }

                # Make API request
                response = requests.post(
                    current_app.config['REALTIME_URL'],
                    json=request_data,
                    headers={'TGT': tgt_token}
                )
                response.raise_for_status()
                
                items = response.json().get('items', [])
                
                hourly_values = [0] * 24
                for item in items:
                    hour = int(item.get('hour', '00:00').split(':')[0])
                    total = item.get('total', 0)
                    hourly_values[hour] = total

                # Distribute values among plant instances
                count = p_id_count[p_id]
                distributed_values = [val / count for val in hourly_values]
                
                for idx in p_id_indices[p_id]:
                    plant_name = plant_mapping['plant_names'][idx]
                    df[plant_name] = distributed_values
                    
                    # Prepare database records
                    for hour, value in enumerate(distributed_values):
                        batch_data.append({
                            'date': date,
                            'hour': hour,
                            'plant_name': plant_name,
                            'value': value
                        })
                
                time.sleep(0.5)  # Small delay between requests
                
            except Exception as e:
                print(f"Error fetching realtime data for powerplant {p_id}: {str(e)}")
                for idx in p_id_indices[p_id]:
                    plant_name = plant_mapping['plant_names'][idx]
                    df[plant_name] = [0] * 24

        # Store the fetched data in database
        try:
            if batch_data:
                db.session.bulk_insert_mappings(NaturalGasRealtimeData, batch_data)
                db.session.commit()
        except Exception as e:
            print(f"Error storing realtime data: {str(e)}")
            db.session.rollback()

        return jsonify({
            "code": 200,
            "data": {
                "hours": df.index.tolist(),
                "plants": [f"{name}--{capacity} Mw" for name, capacity in zip(
                    plant_mapping['plant_names'],
                    plant_mapping['capacities']
                )],
                "values": df.values.tolist()
            }
        })
    except Exception as e:
        print(f"Error in realtime_heatmap_data: {str(e)}")
        return jsonify({"code": 500, "error": str(e)})

@main.route('/import_coal_heatmap_data', methods=['POST'])
def import_coal_heatmap_data():
    try:
        data = request.json
        date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        version = data.get('version', 'first')
        
        # First try to get data from database
        heatmap_data = ImportedCoalHeatmapData.query.filter_by(
            date=date,
            version=version
        ).all()
        
        if not heatmap_data:
            current_app.logger.info(f"No imported coal data in DB for {date}, fetching from API...")
            
            # Get authentication token and URL
            dpp_url = current_app.config['DPP_FIRST_VERSION_URL'] if version == 'first' else current_app.config['DPP_URL']
            tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
            
            # Initialize DataFrame with hours and fill with 0
            hours = [f"{str(i).zfill(2)}:00" for i in range(24)]
            df = pd.DataFrame(0, index=hours, columns=import_coal_mapping['plant_names'])
            
            # Iterate through all plants with their IDs
            for plant_name, o_id, pl_id in zip(
                import_coal_mapping['plant_names'],
                import_coal_mapping['o_ids'],
                import_coal_mapping['uevcb_ids']
            ):
                try:
                    # Format request data exactly as shown in working example
                    request_data = {
                        'startDate': f"{date.strftime('%Y-%m-%d')}T00:00:00+03:00",
                        'endDate': f"{date.strftime('%Y-%m-%d')}T00:00:00+03:00",
                        'region': 'TR1',
                        'organizationId': int(o_id),
                        'uevcbId': int(pl_id)
                    }
                    
                    current_app.logger.info(f"Fetching data for {plant_name} with data: {request_data}")
                    
                    response = requests.post(
                        dpp_url,
                        headers={
                            'Accept': 'application/json',
                            'Content-Type': 'application/json',
                            'TGT': tgt_token
                        },
                        json=request_data,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        current_app.logger.info(f"Raw response for {plant_name}: {str(response_data)[:200]}...")
                        
                        if response_data and 'items' in response_data:
                            for item in response_data['items']:
                                try:
                                    hour = item.get('time', '00:00').split(':')[0]
                                    # Try both toplam and ithalKomur fields
                                    value = None
                                    if item.get('ithalKomur') is not None:
                                        value = float(item['ithalKomur'])
                                    elif item.get('toplam') is not None:
                                        value = float(item['toplam'])
                                        
                                    if value is not None:
                                        df.at[f"{hour.zfill(2)}:00", plant_name] = value
                                        current_app.logger.info(f"Added value {value} for {plant_name} at hour {hour}")
                                except (ValueError, TypeError) as e:
                                    current_app.logger.warning(f"Invalid value for {plant_name} at hour {hour}")
                                    continue
                        else:
                            current_app.logger.warning(f"No items in response for {plant_name}")
                    else:
                        current_app.logger.error(f"Bad response status {response.status_code} for {plant_name}")
                    
                    time.sleep(0.5)  # Small delay between API calls
                    
                except Exception as e:
                    current_app.logger.error(f"Error fetching data for {plant_name}: {str(e)}")
                    continue
            
            # Process the dataframe
            result = {
                "code": 200,
                "data": {
                    "hours": df.index.tolist(),
                    "plants": [f"{name}--{capacity} Mw" for name, capacity in zip(
                        import_coal_mapping['plant_names'],
                        import_coal_mapping['capacities']
                    )],
                    "values": df.values.tolist()
                }
            }
            
            return jsonify(result)
        
        # If we have data in DB, process it as before
        df = process_heatmap_data(heatmap_data, import_coal_mapping)
        
        if df.empty:
            return jsonify({
                "code": 404,
                "error": f"No data available for date {date}"
            })
        
        return jsonify({
            "code": 200,
            "data": {
                "hours": df.index.tolist(),
                "plants": [f"{name}--{capacity} Mw" for name, capacity in zip(
                    import_coal_mapping['plant_names'],
                    import_coal_mapping['capacities']
                )],
                "values": df.values.tolist()
            }
        })

    except ValueError as ve:
        return jsonify({"code": 400, "error": f"Invalid date format: {str(ve)}"})
    except Exception as e:
        current_app.logger.error(f"Error in import_coal_heatmap_data: {str(e)}")
        return jsonify({"code": 500, "error": "Internal server error"})

def process_heatmap_data(heatmap_data, mapping):
    """Process heatmap data from database into a pandas DataFrame."""
    hours = [f"{str(i).zfill(2)}:00" for i in range(24)]
    df = pd.DataFrame(index=hours, columns=mapping['plant_names'])
    
    for record in heatmap_data:
        hour = f"{str(record.hour).zfill(2)}:00"
        df.at[hour, record.plant_name] = record.value
    
    # Fix the pandas warning by explicitly converting to numeric
    return df.fillna(0).astype(float)

@main.route('/get_order_summary', methods=['GET'])
def get_order_summary():
    try:
        # Get current time in Turkey timezone
        tz = pytz.timezone('Europe/Istanbul')
        current_time = datetime.now(tz)
        
        # Calculate start and end dates
        yesterday = current_time - timedelta(days=1)
        tomorrow = current_time + timedelta(days=1)
        
        # Format dates for API
        start_date = yesterday.strftime("%Y-%m-%dT00:00:00+03:00")
        end_date = tomorrow.strftime("%Y-%m-%dT23:59:59+03:00")
        
        # Set up session with retries
        session = Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        
        # Get authentication token
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        
        # Make API request
        response = session.post(
            'https://seffaflik.epias.com.tr/electricity-service/v1/markets/bpm/data/order-summary-up',
            json={
                "startDate": start_date,
                "endDate": end_date
            },
            headers={'TGT': tgt_token}
        )
        response.raise_for_status()
        
        # Get data and filter based on current time
        data = response.json().get('items', [])
        
        # Filter data to show only up to 4 hours before current time
        cutoff_time = current_time - timedelta(hours=4)
        filtered_data = []
        
        for item in data:
            item_datetime = datetime.strptime(item['date'], "%Y-%m-%dT%H:%M:%S+03:00")
            item_datetime = tz.localize(item_datetime)
            
            if item_datetime <= cutoff_time:
                filtered_data.append({
                    'datetime': f"{item_datetime.strftime('%Y-%m-%d')} {item['hour']}",
                    'value': item['net']
                })
        
        return jsonify({
            'code': 200,
            'data': filtered_data
        })
        
    except Exception as e:
        print(f"Error in get_order_summary: {str(e)}")
        return jsonify({'code': 500, 'message': str(e)}), 500

@main.route('/get_smp_data', methods=['GET'])
def get_smp_data():
    try:
        # Get current time in Turkey timezone
        tz = pytz.timezone('Europe/Istanbul')
        current_time = datetime.now(tz)
        
        # Get yesterday's date
        yesterday = current_time - timedelta(days=1)
        
        # Format dates for API
        start_date = yesterday.strftime("%Y-%m-%dT00:00:00+03:00")
        end_date = yesterday.strftime("%Y-%m-%dT23:59:59+03:00")
        
        # Set up session with retries
        session = Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        
        # Get authentication token
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        
        # Make API request
        response = session.post(
            'https://seffaflik.epias.com.tr/electricity-service/v1/markets/bpm/data/system-marginal-price',
            json={
                "startDate": start_date,
                "endDate": end_date
            },
            headers={'TGT': tgt_token}
        )
        response.raise_for_status()
        
        # Process data
        data = response.json().get('items', [])
        processed_data = []
        
        for item in data:
            item_datetime = datetime.strptime(item['date'], "%Y-%m-%dT%H:%M:%S+03:00")
            processed_data.append({
                'datetime': f"{item_datetime.strftime('%Y-%m-%d')} {item_datetime.strftime('%H:%M')}",
                'value': item['systemMarginalPrice']
            })
        
        # Get statistics
        statistics = response.json().get('statistics', {})
        average = statistics.get('smpArithmeticalAverage', 0)
        
        return jsonify({
            'code': 200,
            'data': processed_data,
            'average': average
        })
        
    except Exception as e:
        print(f"Error in get_smp_data: {str(e)}")
        return jsonify({'code': 500, 'message': str(e)}), 500

@main.route('/get_pfc_data', methods=['GET'])
def get_pfc_data():
    try:
        # Get current time in Turkey timezone
        tz = pytz.timezone('Europe/Istanbul')
        current_time = datetime.now(tz)
        
        # Calculate dates (today and two days after)
        start_date = current_time.strftime("%Y-%m-%dT00:00:00+03:00")
        end_date = (current_time + timedelta(days=2)).strftime("%Y-%m-%dT23:59:59+03:00")
        
        # Set up session with retries
        session = Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        
        # Get authentication token
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        
        # Make API request
        response = session.post(
            'https://seffaflik.epias.com.tr/electricity-service/v1/markets/ancillary-services/data/primary-frequency-capacity-price',
            json={
                "startDate": start_date,
                "endDate": end_date
            },
            headers={'TGT': tgt_token}
        )
        response.raise_for_status()
        
        # Process data
        data = response.json().get('items', [])
        processed_data = []
        
        for item in data:
            item_datetime = datetime.strptime(item['date'], "%Y-%m-%dT%H:%M:%S+03:00")
            processed_data.append({
                'datetime': f"{item_datetime.strftime('%Y-%m-%d')} {str(item['hour']).zfill(2)}:00",
                'value': item['price']
            })
        
        # Get statistics
        statistics = response.json().get('statistics', {})
        average = statistics.get('priceAvg', 0)
        
        return jsonify({
            'code': 200,
            'data': processed_data,
            'average': average
        })
        
    except Exception as e:
        print(f"Error in get_pfc_data: {str(e)}")
        return jsonify({'code': 500, 'message': str(e)}), 500

@main.route('/get_sfc_data', methods=['GET'])
def get_sfc_data():
    try:
        # Get current time in Turkey timezone
        tz = pytz.timezone('Europe/Istanbul')
        current_time = datetime.now(tz)
        
        # Calculate dates (today and two days after)
        start_date = current_time.strftime("%Y-%m-%dT00:00:00+03:00")
        end_date = (current_time + timedelta(days=2)).strftime("%Y-%m-%dT23:59:59+03:00")
        
        # Set up session with retries
        session = Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        
        # Get authentication token
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        
        # Make API request
        response = session.post(
            'https://seffaflik.epias.com.tr/electricity-service/v1/markets/ancillary-services/data/secondary-frequency-capacity-price',
            json={
                "startDate": start_date,
                "endDate": end_date
            },
            headers={'TGT': tgt_token}
        )
        response.raise_for_status()
        
        # Process data
        data = response.json().get('items', [])
        processed_data = []
        
        for item in data:
            item_datetime = datetime.strptime(item['date'], "%Y-%m-%dT%H:%M:%S+03:00")
            processed_data.append({
                'datetime': f"{item_datetime.strftime('%Y-%m-%d')} {str(item['hour']).zfill(2)}:00",
                'value': item['price']
            })
        
        # Get statistics
        statistics = response.json().get('statistics', {})
        average = statistics.get('priceAvg', 0)
        
        return jsonify({
            'code': 200,
            'data': processed_data,
            'average': average
        })
        
    except Exception as e:
        print(f"Error in get_sfc_data: {str(e)}")
        return jsonify({'code': 500, 'message': str(e)}), 500

@main.route('/get_all_table_data', methods=['GET'])
def get_all_table_data():
    try:
        # Get current time in Turkey timezone
        tz = pytz.timezone('Europe/Istanbul')
        current_time = datetime.now(tz)
        
        # Get authentication token once
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        
        # Set up session with retries
        session = Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 443, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        
        # Prepare dates for different endpoints
        yesterday = current_time - timedelta(days=1)
        tomorrow = current_time + timedelta(days=1)
        two_days_after = current_time + timedelta(days=2)
        
        # Common headers
        headers = {'TGT': tgt_token}
        
        # Fetch order summary data
        order_summary_response = session.post(
            'https://seffaflik.epias.com.tr/electricity-service/v1/markets/bpm/data/order-summary-up',
            json={
                "startDate": yesterday.strftime("%Y-%m-%dT00:00:00+03:00"),
                "endDate": tomorrow.strftime("%Y-%m-%dT23:59:59+03:00")
            },
            headers=headers
        )
        
        # Fetch SMP data
        smp_response = session.post(
            'https://seffaflik.epias.com.tr/electricity-service/v1/markets/bpm/data/system-marginal-price',
            json={
                "startDate": yesterday.strftime("%Y-%m-%dT00:00:00+03:00"),
                "endDate": yesterday.strftime("%Y-%m-%dT23:59:59+03:00")
            },
            headers=headers
        )
        
        # Fetch PFC data
        pfc_response = session.post(
            'https://seffaflik.epias.com.tr/electricity-service/v1/markets/ancillary-services/data/primary-frequency-capacity-price',
            json={
                "startDate": current_time.strftime("%Y-%m-%dT00:00:00+03:00"),
                "endDate": two_days_after.strftime("%Y-%m-%dT23:59:59+03:00")
            },
            headers=headers
        )
        
        # Fetch SFC data
        sfc_response = session.post(
            'https://seffaflik.epias.com.tr/electricity-service/v1/markets/ancillary-services/data/secondary-frequency-capacity-price',
            json={
                "startDate": current_time.strftime("%Y-%m-%dT00:00:00+03:00"),
                "endDate": two_days_after.strftime("%Y-%m-%dT23:59:59+03:00")
            },
            headers=headers
        )
        
        # Process order summary data
        order_data = order_summary_response.json().get('items', [])
        cutoff_time = current_time - timedelta(hours=4)
        order_summary = []
        
        for item in order_data:
            item_datetime = datetime.strptime(item['date'], "%Y-%m-%dT%H:%M:%S+03:00")
            item_datetime = tz.localize(item_datetime)
            if item_datetime <= cutoff_time:
                order_summary.append({
                    'datetime': f"{item_datetime.strftime('%Y-%m-%d')} {item['hour']}",
                    'value': item['net']
                })
        
        # Process SMP data
        smp_data = smp_response.json()
        smp_processed = [{
            'datetime': f"{datetime.strptime(item['date'], '%Y-%m-%dT%H:%M:%S+03:00').strftime('%Y-%m-%d')} {datetime.strptime(item['date'], '%Y-%m-%dT%H:%M:%S+03:00').strftime('%H:%M')}",
            'value': item['systemMarginalPrice']
        } for item in smp_data.get('items', [])]
        
        # Process PFC data
        pfc_data = pfc_response.json()
        pfc_processed = [{
            'datetime': f"{datetime.strptime(item['date'], '%Y-%m-%dT%H:%M:%S+03:00').strftime('%Y-%m-%d')} {str(item['hour']).zfill(2)}:00",
            'value': item['price']
        } for item in pfc_data.get('items', [])]
        
        # Process SFC data
        sfc_data = sfc_response.json()
        sfc_processed = [{
            'datetime': f"{datetime.strptime(item['date'], '%Y-%m-%dT%H:%M:%S+03:00').strftime('%Y-%m-%d')} {str(item['hour']).zfill(2)}:00",
            'value': item['price']
        } for item in sfc_data.get('items', [])]
        
        return jsonify({
            'code': 200,
            'data': {
                'orderSummary': order_summary,
                'smp': {
                    'data': smp_processed,
                    'average': smp_data.get('statistics', {}).get('smpArithmeticalAverage', 0)
                },
                'pfc': {
                    'data': pfc_processed,
                    'average': pfc_data.get('statistics', {}).get('priceAvg', 0)
                },
                'sfc': {
                    'data': sfc_processed,
                    'average': sfc_data.get('statistics', {}).get('priceAvg', 0)
                }
            }
        })
        
    except Exception as e:
        print(f"Error in get_all_table_data: {str(e)}")
        return jsonify({'code': 500, 'message': str(e)}), 500

@main.route('/hydro_heatmap_data', methods=['POST'])
def hydro_heatmap_data():
    try:
        data = request.json
        date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        version = data.get('version', 'first')
        
        # First try to get data from database
        heatmap_data = HydroHeatmapData.query.filter_by(
            date=date,
            version=version
        ).all()
        
        if not heatmap_data:
            current_app.logger.info(f"No hydro data in DB for {date}, fetching from API...")
            
            # Get authentication token and URL
            dpp_url = current_app.config['DPP_FIRST_VERSION_URL'] if version == 'first' else current_app.config['DPP_URL']
            tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
            
            # Initialize DataFrame with hours and fill with 0
            hours = [f"{str(i).zfill(2)}:00" for i in range(24)]
            df = pd.DataFrame(0, index=hours, columns=hydro_mapping['plant_names'])
            
            # Iterate through all plants with their IDs
            for plant_name, o_id, pl_id in zip(
                hydro_mapping['plant_names'],
                hydro_mapping['o_ids'],
                hydro_mapping['uevcb_ids']
            ):
                try:
                    # Format request data exactly as shown in working example
                    request_data = {
                        'startDate': f"{date.strftime('%Y-%m-%d')}T00:00:00+03:00",
                        'endDate': f"{date.strftime('%Y-%m-%d')}T00:00:00+03:00",
                        'region': 'TR1',
                        'organizationId': int(o_id),
                        'uevcbId': int(pl_id)
                    }
                    
                    current_app.logger.info(f"Fetching data for {plant_name} with data: {request_data}")
                    
                    response = requests.post(
                        dpp_url,
                        headers={
                            'Accept': 'application/json',
                            'Content-Type': 'application/json',
                            'TGT': tgt_token
                        },
                        json=request_data,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        current_app.logger.info(f"Raw response for {plant_name}: {str(response_data)[:200]}...")
                        
                        if response_data and 'items' in response_data:
                            for item in response_data['items']:
                                try:
                                    hour = item.get('time', '00:00').split(':')[0]
                                    # Try both toplam and barajli fields
                                    value = None
                                    if item.get('barajli') is not None:
                                        value = float(item['barajli'])
                                    elif item.get('toplam') is not None:
                                        value = float(item['toplam'])
                                        
                                    if value is not None:
                                        df.at[f"{hour.zfill(2)}:00", plant_name] = value
                                        current_app.logger.info(f"Added value {value} for {plant_name} at hour {hour}")
                                except (ValueError, TypeError) as e:
                                    current_app.logger.warning(f"Invalid value for {plant_name} at hour {hour}")
                                    continue
                        else:
                            current_app.logger.warning(f"No items in response for {plant_name}")
                    else:
                        current_app.logger.error(f"Bad response status {response.status_code} for {plant_name}")
                    
                    time.sleep(0.5)  # Small delay between API calls
                    
                except Exception as e:
                    current_app.logger.error(f"Error fetching data for {plant_name}: {str(e)}")
                    continue
            
            # Process the dataframe
            result = {
                "code": 200,
                "data": {
                    "hours": df.index.tolist(),
                    "plants": [f"{name}--{capacity} Mw" for name, capacity in zip(
                        hydro_mapping['plant_names'],
                        hydro_mapping['capacities']
                    )],
                    "values": df.values.tolist()
                }
            }
            
            return jsonify(result)
        
        # If we have data in DB, process it as before
        df = process_heatmap_data(heatmap_data, hydro_mapping)
        
        if df.empty:
            return jsonify({
                "code": 404,
                "error": f"No data available for date {date}"
            })
        
        return jsonify({
            "code": 200,
            "data": {
                "hours": df.index.tolist(),
                "plants": [f"{name}--{capacity} Mw" for name, capacity in zip(
                    hydro_mapping['plant_names'],
                    hydro_mapping['capacities']
                )],
                "values": df.values.tolist()
            }
        })

    except ValueError as ve:
        return jsonify({"code": 400, "error": f"Invalid date format: {str(ve)}"})
    except Exception as e:
        current_app.logger.error(f"Error in hydro_heatmap_data: {str(e)}")
        return jsonify({"code": 500, "error": "Internal server error"})

@main.route('/hydro_realtime_heatmap_data', methods=['POST'])
def hydro_realtime_heatmap_data():
    try:
        data = request.json
        selected_date = data.get('date')
        
        if not selected_date:
            return jsonify({"code": 400, "error": "Missing 'date' parameter"})

        # Convert date string to date object
        date = datetime.strptime(selected_date, '%Y-%m-%d').date()

        # First try to get data from database
        heatmap_data = HydroRealtimeData.query.filter_by(
            date=date
        ).all()

        # If we have data in database, process and return it
        if heatmap_data:
            df = pd.DataFrame(index=[f"{str(i).zfill(2)}:00" for i in range(24)], 
                                    columns=hydro_mapping['plant_names'])
            
            for record in heatmap_data:
                hour = f"{str(record.hour).zfill(2)}:00"
                df.at[hour, record.plant_name] = record.value

            # Replace NaN values with 0
            df = df.fillna(0)

            return jsonify({
                "code": 200,
                "data": {
                    "hours": df.index.tolist(),
                    "plants": [f"{name}--{capacity} Mw" for name, capacity in zip(
                        hydro_mapping['plant_names'],
                        hydro_mapping['capacities']
                    )],
                    "values": df.values.tolist()
                }
            })

        # If no data in database, fetch from API
        hours = [f"{str(i).zfill(2)}:00" for i in range(24)]
        df = pd.DataFrame(index=hours, columns=hydro_mapping['plant_names'])
        
        # Get authentication token
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        
        # Create mappings for plant IDs
        p_id_count = {}
        for p_id in hydro_mapping['p_ids']:
            p_id_count[p_id] = hydro_mapping['p_ids'].count(p_id)

        p_id_indices = {}
        for idx, p_id in enumerate(hydro_mapping['p_ids']):
            if p_id not in p_id_indices:
                p_id_indices[p_id] = []
            p_id_indices[p_id].append(idx)

        # Fetch realtime data for each unique powerplant
        batch_data = []
        unique_p_ids = set(hydro_mapping['p_ids'])
        for p_id in unique_p_ids:
            try:
                print(f"Fetching realtime data for hydro plant ID: {p_id}")
                
                request_data = {
                    "startDate": f"{selected_date}T00:00:00+03:00",
                    "endDate": f"{selected_date}T23:59:59+03:00",
                    "powerPlantId": str(p_id)
                }

                # Make API request
                response = requests.post(
                    current_app.config['REALTIME_URL'],
                    json=request_data,
                    headers={'TGT': tgt_token}
                )
                response.raise_for_status()
                
                items = response.json().get('items', [])
                
                hourly_values = [0] * 24
                for item in items:
                    hour = int(item.get('hour', '00:00').split(':')[0])
                    total = item.get('total', 0)
                    hourly_values[hour] = total

                # Distribute values among plant instances
                count = p_id_count[p_id]
                distributed_values = [val / count for val in hourly_values]
                
                for idx in p_id_indices[p_id]:
                    plant_name = hydro_mapping['plant_names'][idx]
                    df[plant_name] = distributed_values
                    
                    # Prepare database records
                    for hour, value in enumerate(distributed_values):
                        batch_data.append({
                            'date': date,
                            'hour': hour,
                            'plant_name': plant_name,
                            'value': value
                        })
                
                time.sleep(0.5)  # Small delay between requests
                
            except Exception as e:
                print(f"Error fetching realtime data for hydro plant {p_id}: {str(e)}")
                for idx in p_id_indices[p_id]:
                    plant_name = hydro_mapping['plant_names'][idx]
                    df[plant_name] = [0] * 24

        # Store the fetched data in database
        try:
            if batch_data:
                db.session.bulk_insert_mappings(HydroRealtimeData, batch_data)
                db.session.commit()
        except Exception as e:
            print(f"Error storing realtime data: {str(e)}")
            db.session.rollback()

        return jsonify({
            "code": 200,
            "data": {
                "hours": df.index.tolist(),
                "plants": [f"{name}--{capacity} Mw" for name, capacity in zip(
                    hydro_mapping['plant_names'],
                    hydro_mapping['capacities']
                )],
                "values": df.values.tolist()
            }
        })

    except Exception as e:
        print(f"Error in hydro_realtime_heatmap_data: {str(e)}")
        return jsonify({"code": 500, "error": str(e)})

@main.route('/production_data', methods=['POST'])
def get_production_data():
    try:
        data = request.get_json()
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({
                'code': 400,
                'message': 'Start date and end date are required'
            }), 400
            
        # Check if data exists in database
        existing_data = ProductionData.query.filter(
            ProductionData.datetime.between(
                datetime.strptime(start_date, '%Y-%m-%d'),
                datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            )
        ).all()
        
        if existing_data:
            return jsonify({
                'code': 200,
                'data': [record.to_dict() for record in existing_data]
            })
        
        # If no data in database, fetch from API
        tgt_token = get_tgt_token(
            current_app.config.get('USERNAME'),
            current_app.config.get('PASSWORD')
        )
        
        url = "https://seffaflik.epias.com.tr/electricity-service/v1/generation/data/realtime-generation"
        
        payload = {
            "startDate": f"{start_date}T00:00:00+03:00",
            "endDate": f"{end_date}T23:59:59+03:00",
            "region": "TR1",
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': "application/json",
            'TGT': tgt_token
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        # Process the data
        items = response.json().get('items', [])
        if not items:
            return jsonify({
                'code': 404,
                'message': 'No data found for the specified date range'
            }), 404
            
        # Convert to DataFrame for easier processing
        df = pd.json_normalize(items)
        df['date'] = pd.to_datetime(df['date'])
        
        # Create DateTime column
        if 'hour' in df.columns:
            df['DateTime'] = pd.to_datetime(
                df['date'].dt.date.astype(str) + ' ' + df['hour']
            )
            df['DateTime'] = df['DateTime'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Store in database
        for _, row in df.iterrows():
            record = ProductionData(
                datetime=datetime.strptime(row['DateTime'], '%Y-%m-%d %H:%M:%S'),
                fueloil=row.get('fueloil', 0),
                gasoil=0,  # Setting default as 0 as per crawler
                blackcoal=row.get('blackCoal', 0),
                lignite=row.get('lignite', 0),
                geothermal=row.get('geothermal', 0),
                naturalgas=row.get('naturalGas', 0),
                river=row.get('river', 0),
                dammedhydro=row.get('dammedHydro', 0),
                lng=row.get('lng', 0),
                biomass=row.get('biomass', 0),
                naphta=row.get('naphta', 0),
                importcoal=row.get('importCoal', 0),
                asphaltitecoal=row.get('asphaltiteCoal', 0),
                wind=row.get('wind', 0),
                nuclear=0,  # Setting default as 0 as per crawler
                sun=row.get('sun', 0),
                importexport=row.get('importExport', 0),
                total=row.get('total', 0),
                wasteheat=row.get('wasteheat', 0)
            )
            db.session.add(record)
        
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'data': [record.to_dict() for record in ProductionData.query.filter(
                ProductionData.datetime.between(
                    datetime.strptime(start_date, '%Y-%m-%d'),
                    datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                )
            ).all()]
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in get_production_data: {str(e)}")
        return jsonify({
            'code': 500,
            'message': f'Error fetching production data: {str(e)}'
        }), 500

@main.route('/check-data-completeness')
def check_data_completeness():
    try:
        # Get min and max dates
        min_date = db.session.query(db.func.min(ProductionData.datetime)).scalar()
        max_date = db.session.query(db.func.max(ProductionData.datetime)).scalar()
        
        # Get count of records
        total_records = db.session.query(ProductionData).count()
        
        # Calculate expected records (assuming 24 records per day)
        days = (max_date - min_date).days + 1
        expected_records = days * 24
        
        # Find gaps in data using SQLAlchemy's text()
        query = text("""
            WITH dates AS (
                SELECT generate_series(
                    date_trunc('hour', min(datetime)),
                    date_trunc('hour', max(datetime)),
                    '1 hour'::interval
                ) as expected_datetime
                FROM production_data
            )
            SELECT expected_datetime::timestamp
            FROM dates
            LEFT JOIN production_data ON dates.expected_datetime = date_trunc('hour', production_data.datetime)
            WHERE production_data.id IS NULL
            ORDER BY expected_datetime;
        """)
        
        missing_dates = db.session.execute(query).fetchall()
        
        return jsonify({
            'start_date': min_date.strftime('%Y-%m-%d %H:%M'),
            'end_date': max_date.strftime('%Y-%m-%d %H:%M'),
            'total_days': days,
            'total_records': total_records,
            'expected_records': expected_records,
            'missing_records': expected_records - total_records,
            'coverage_percentage': (total_records / expected_records) * 100,
            'missing_dates': [d[0].strftime('%Y-%m-%d %H:%M') for d in missing_dates[:100]] if missing_dates else [],
            'total_missing_dates': len(missing_dates) if missing_dates else 0
        })
        
    except Exception as e:
        print(f"Error in check_data_completeness: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e)
        }), 500

@main.route('/get-rolling-data')
def get_rolling_data():
    try:
        # Load the original historical data (2016-2024) as the base
        historical_file = os.path.join(current_app.static_folder, 'data', 'historical_averages.json')
        
        if os.path.exists(historical_file):
            print("Loading original historical data (2016-2024) as base")
            with open(historical_file, 'r') as f:
                historical_data = json.load(f)
            
            # Set base metadata for 2016-2024 data
            historical_data['_metadata'] = {
                'data_source': 'original',
                'date_range': '2016-2024',
                'uses_combined_solar': False
            }
        else:
            historical_data = {}
            historical_data['_metadata'] = {
                'data_source': 'none',
                'date_range': '2016-2024',
                'uses_combined_solar': False
            }

        # Now load the combined solar data and override only the solar_combined entry
        combined_solar_file = os.path.join(current_app.static_folder, 'data', 'historical_averages_combined_solar.json')
        
        if os.path.exists(combined_solar_file):
            print("Loading combined solar historical data (2020-2024) for solar_combined chart")
            with open(combined_solar_file, 'r') as f:
                combined_solar_data = json.load(f)
            
            # Only override the solar_combined data, keep everything else from original file
            if 'solar_combined' in combined_solar_data:
                historical_data['solar_combined'] = combined_solar_data['solar_combined']
                
            # Also override renewables ratio since it now uses combined solar data
            if 'renewablesratio_monthly' in combined_solar_data:
                historical_data['renewablesratio_monthly'] = combined_solar_data['renewablesratio_monthly']
                
            # Add special metadata for solar_combined to indicate it uses 2020-2024 data
            historical_data['_solar_combined_metadata'] = {
                'date_range': '2020-2024',
                'uses_combined_solar': True
            }
            
            print("Successfully merged combined solar data with original historical data")
        else:
            print("Combined solar historical data file not found")

        # Get current year data (2025 and beyond)
        current_year = datetime.now().year
        cutoff_date = datetime(current_year, 1, 1)
        
        # Query production data (excluding solar since we'll use separate tables)
        production_query = db.session.query(ProductionData).filter(
            ProductionData.datetime >= cutoff_date
        ).order_by(ProductionData.datetime)
        
        # Query unlicensed solar data
        unlicensed_query = db.session.query(UnlicensedSolarData).filter(
            UnlicensedSolarData.datetime >= cutoff_date
        ).order_by(UnlicensedSolarData.datetime)
        
        # Query licensed solar data
        licensed_query = db.session.query(LicensedSolarData).filter(
            LicensedSolarData.datetime >= cutoff_date
        ).order_by(LicensedSolarData.datetime)
        
        current_data = production_query.all()
        unlicensed_data = unlicensed_query.all()
        licensed_data = licensed_query.all()
        
        print(f"Found {len(current_data)} production records, {len(unlicensed_data)} unlicensed solar records, and {len(licensed_data)} licensed solar records")
        
        if current_data:
            print(f"Processing {len(current_data)} current year records")
            
            # Convert to DataFrame with timezone handling
            df = pd.DataFrame([{
                'datetime': d.datetime.astimezone(pytz.UTC),
                'fueloil': d.fueloil,
                'gasoil': d.gasoil,
                'blackcoal': d.blackcoal,
                'lignite': d.lignite,
                'geothermal': d.geothermal,
                'naturalgas': d.naturalgas,
                'river': d.river,
                'dammedhydro': d.dammedhydro,
                'lng': d.lng,
                'biomass': d.biomass,
                'naphta': d.naphta,
                'importcoal': d.importcoal,
                'asphaltitecoal': d.asphaltitecoal,
                'wind': d.wind,
                'nuclear': d.nuclear,
                'sun': d.sun,  # Keep this for renewables calculation
                'importexport': d.importexport,
                'total': d.total,
                'wasteheat': d.wasteheat
            } for d in current_data])
            
            # Convert datetime to pandas datetime with UTC timezone
            df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
            df = df.set_index('datetime')
            
            # Convert to local time (Istanbul)
            istanbul_tz = pytz.timezone('Europe/Istanbul')
            df.index = df.index.tz_convert(istanbul_tz)
            
            # Process solar data from separate tables first
            if unlicensed_data or licensed_data:
                print(f"Processing {len(unlicensed_data)} unlicensed and {len(licensed_data)} licensed solar records")
                
                # Create unlicensed solar DataFrame
                if unlicensed_data:
                    unlicensed_df = pd.DataFrame([{
                        'datetime': d.datetime.astimezone(pytz.UTC),
                        'unlicensed_solar': d.unlicensed_solar
                    } for d in unlicensed_data])
                    
                    unlicensed_df['datetime'] = pd.to_datetime(unlicensed_df['datetime'], utc=True)
                    unlicensed_df = unlicensed_df.set_index('datetime')
                    unlicensed_df.index = unlicensed_df.index.tz_convert(istanbul_tz)
                else:
                    unlicensed_df = pd.DataFrame(columns=['unlicensed_solar'])
                    unlicensed_df.index = pd.DatetimeIndex([])
                
                # Create licensed solar DataFrame
                if licensed_data:
                    licensed_df = pd.DataFrame([{
                        'datetime': d.datetime.astimezone(pytz.UTC),
                        'licensed_solar': d.licensed_solar
                    } for d in licensed_data])
                    
                    licensed_df['datetime'] = pd.to_datetime(licensed_df['datetime'], utc=True)
                    licensed_df = licensed_df.set_index('datetime')
                    licensed_df.index = licensed_df.index.tz_convert(istanbul_tz)
                else:
                    licensed_df = pd.DataFrame(columns=['licensed_solar'])
                    licensed_df.index = pd.DatetimeIndex([])
                
                print(f"Unlicensed solar data range: {unlicensed_df.index.min() if not unlicensed_df.empty else 'None'} to {unlicensed_df.index.max() if not unlicensed_df.empty else 'None'}")
                print(f"Licensed solar data range: {licensed_df.index.min() if not licensed_df.empty else 'None'} to {licensed_df.index.max() if not licensed_df.empty else 'None'}")
                print(f"Production data range: {df.index.min()} to {df.index.max()}")
                
                # Resample all DataFrames to hourly frequency to align timestamps
                df_hourly = df.resample('H', closed='left', label='left').mean()
                unlicensed_hourly = unlicensed_df.resample('H', closed='left', label='left').mean() if not unlicensed_df.empty else pd.DataFrame()
                licensed_hourly = licensed_df.resample('H', closed='left', label='left').mean() if not licensed_df.empty else pd.DataFrame()
                
                print(f"After resampling - Production shape: {df_hourly.shape}")
                if not unlicensed_hourly.empty:
                    print(f"Unlicensed shape: {unlicensed_hourly.shape}")
                if not licensed_hourly.empty:
                    print(f"Licensed shape: {licensed_hourly.shape}")
                
                # Merge all DataFrames
                if not unlicensed_hourly.empty:
                    df_hourly = df_hourly.join(unlicensed_hourly, how='outer')
                    df_hourly['unlicensed_solar'] = df_hourly['unlicensed_solar'].fillna(0)
                else:
                    df_hourly['unlicensed_solar'] = 0
                
                if not licensed_hourly.empty:
                    df_hourly = df_hourly.join(licensed_hourly, how='outer')
                    df_hourly['licensed_solar'] = df_hourly['licensed_solar'].fillna(0)
                else:
                    df_hourly['licensed_solar'] = 0
                
                # Calculate combined solar (unlicensed + licensed)
                df_hourly['solar_combined'] = df_hourly['unlicensed_solar'] + df_hourly['licensed_solar']
                
                # Build completeness sets per-series so solar-derived series can lag without
                # forcing other series to drop the latest day
                print("Computing completeness per series (production vs solar)...")
                today = datetime.now().date()
                
                # Production completeness (use overall index)
                prod_counts_by_day = df_hourly.groupby(df_hourly.index.date).size()
                prod_complete_days = [d for d, c in prod_counts_by_day.items() if c == 24 and d != today]
                
                # Solar completeness (require 24 points in both unlicensed and licensed if they exist)
                solar_complete_days = None
                if not unlicensed_hourly.empty:
                    unl_counts = unlicensed_hourly.groupby(unlicensed_hourly.index.date).size()
                    unl_complete = set([d for d, c in unl_counts.items() if c == 24 and d != today])
                else:
                    unl_complete = set()
                if not licensed_hourly.empty:
                    lic_counts = licensed_hourly.groupby(licensed_hourly.index.date).size()
                    lic_complete = set([d for d, c in lic_counts.items() if c == 24 and d != today])
                else:
                    lic_complete = set()
                
                if not unlicensed_hourly.empty and not licensed_hourly.empty:
                    solar_complete_days = unl_complete.intersection(lic_complete)
                elif not unlicensed_hourly.empty:
                    solar_complete_days = unl_complete
                elif not licensed_hourly.empty:
                    solar_complete_days = lic_complete
                else:
                    # No separate solar sources → treat as production completeness
                    solar_complete_days = set(prod_complete_days)
                
                print(f"Production complete days: {len(prod_complete_days)} | Solar complete days: {len(solar_complete_days)}")
                
                # Do not filter df_hourly globally anymore; we will apply these day sets per-series
                # when constructing outputs to avoid unintended drops.
                
                print(f"Sample unlicensed solar values: {df_hourly['unlicensed_solar'].head()}")
                print(f"Sample licensed solar values: {df_hourly['licensed_solar'].head()}")
                print(f"Sample combined solar values: {df_hourly['solar_combined'].head()}")
                
                # Use the hourly DataFrame for further processing without global trimming
                df = df_hourly
            else:
                # No solar data from separate tables, set to 0
                df['unlicensed_solar'] = 0
                df['licensed_solar'] = 0
                df['solar_combined'] = 0
                print("No separate solar data found, setting all solar values to 0")
            
            # Calculate renewables total and ratio (using combined solar data) - AFTER solar processing
            df['renewablestotal'] = df['geothermal'] + df['biomass'] + df['wind'] + df['solar_combined']
            df['renewablesratio'] = df['renewablestotal'] / df['total']
            
            # Calculate rolling averages for current year
            rolling_data = historical_data.copy() if historical_data else {}
            
            # Process regular columns with 7-day rolling averages
            regular_columns = [col for col in df.columns if col not in ['renewablesratio', 'solar_combined']]
            regular_columns.append('solar_combined')  # Add combined solar data
            for column in regular_columns:
                # Resample to daily frequency
                daily_avg = df[column].resample('D', closed='left', label='left').mean()
                # Apply completeness per-series
                if column in ['solar_combined', 'unlicensed_solar', 'licensed_solar', 'sun']:
                    daily_avg = daily_avg[daily_avg.index.map(lambda x: x.date() in solar_complete_days)]
                else:
                    daily_avg = daily_avg[daily_avg.index.map(lambda x: x.date() in set(prod_complete_days))]
                rolling_avg = daily_avg.rolling(window=7, min_periods=1).mean()
                
                # Get current year data
                year_data = rolling_avg[rolling_avg.index.year == current_year]
                
                # Create or update column data
                if column not in rolling_data:
                    rolling_data[column] = {}
                
                # Add current year data
                rolling_data[column][str(current_year)] = [
                    round(float(x), 2) if pd.notnull(x) else None 
                    for x in year_data.values
                ]
            
            # Special handling for renewables ratio - monthly averages for current year
            if 'renewablesratio' in df.columns:
                # For renewables ratio, restrict to solar-complete days to avoid sharp drops
                df_ratio = df[df.index.map(lambda x: x.date() in solar_complete_days)]
                monthly_data = df_ratio.groupby([df_ratio.index.month, df_ratio.index.year])['renewablesratio'].mean()
            
            # Convert to DataFrame for easier manipulation
            monthly_df = pd.DataFrame(monthly_data)
            monthly_df.index.names = ['month', 'year']
            monthly_df.reset_index(inplace=True)
            
            # Create or update renewablesratio_monthly
            if 'renewablesratio_monthly' not in rolling_data:
                rolling_data['renewablesratio_monthly'] = {}
            
            # Add current year data
            year_data = []
            for month in range(1, 13):
                value = monthly_df[(monthly_df['month'] == month) & (monthly_df['year'] == current_year)]['renewablesratio'].values
                if len(value) > 0:
                    year_data.append(round(float(value[0]), 4))
                else:
                    year_data.append(None)
            
            rolling_data['renewablesratio_monthly'][str(current_year)] = year_data
                
            print(f"Sample renewables data for current year: {df['renewablesratio'].mean():.4f}")
            
            # Add this after calculating solar_combined
            print(f"Sample solar data - Licensed: {df['licensed_solar'].iloc[0] if len(df) > 0 else 'No data'}, Unlicensed: {df['unlicensed_solar'].iloc[0] if len(df) > 0 else 'No data'}, Combined: {df['solar_combined'].iloc[0] if len(df) > 0 else 'No data'}")
            
            return jsonify(rolling_data)
        else:
            # If no current year data, just return historical data
            return jsonify(historical_data)
        
    except Exception as e:
        print(f"Error in get_rolling_data: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@main.route('/get-rolling-last-update')
def get_rolling_last_update():
    try:
        # Get the most recent record's datetime
        latest_record = db.session.query(ProductionData.datetime).order_by(ProductionData.datetime.desc()).first()
        
        if latest_record:
            # Format the datetime for display
            latest_datetime = latest_record[0]
            istanbul_tz = pytz.timezone('Europe/Istanbul')
            localized_datetime = latest_datetime.replace(tzinfo=pytz.UTC).astimezone(istanbul_tz)
            formatted_datetime = localized_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')
            
            return jsonify({
                'last_update': formatted_datetime,
                'timestamp': latest_datetime.timestamp()
            })
        else:
            return jsonify({
                'last_update': None
            })
            
    except Exception as e:
        print(f"Error in get_rolling_last_update: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@main.route('/update-rolling-data')
def update_rolling_data():
    try:
        # Get the most recent record's datetime
        latest_record = db.session.query(ProductionData.datetime).order_by(ProductionData.datetime.desc()).first()
        
        if not latest_record:
            return jsonify({
                'error': 'No existing records found. Please populate the database first.'
            }), 400
            
        # Find the last complete day (all 24 hours present)
        latest_date = latest_record[0].date()
        
        # Check if the latest day has all 24 hours
        hours_count = db.session.query(ProductionData).filter(
            db.func.date(ProductionData.datetime) == latest_date
        ).count()
        
        # If we don't have all 24 hours, start from the beginning of this day
        if hours_count < 24:
            start_date = datetime.combine(latest_date, datetime.min.time())
        else:
            # Otherwise start from the next day
            start_date = datetime.combine(latest_date + timedelta(days=1), datetime.min.time())
        
        # Get the end date (today)
        end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Format dates for API
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # Check if we need to update (start date should be before end date)
        if start_date.date() > end_date.date():
            return jsonify({
                'message': 'Database is already up to date.',
                'records_added': 0
            })
            
        # Get TGT token for API authentication
        tgt_token = get_tgt_token(
            current_app.config.get('USERNAME'),
            current_app.config.get('PASSWORD')
        )
        
        # Prepare API request
        url = "https://seffaflik.epias.com.tr/electricity-service/v1/generation/data/realtime-generation"
        
        payload = {
            "startDate": f"{start_date_str}T00:00:00+03:00",
            "endDate": f"{end_date_str}T23:59:59+03:00",
            "region": "TR1",
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': "application/json",
            'TGT': tgt_token
        }
        
        # Make API request
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        # Process the data
        items = response.json().get('items', [])
        if not items:
            return jsonify({
                'message': 'No new data found for the specified date range.',
                'records_added': 0
            })
            
        # Convert to DataFrame for easier processing
        df = pd.json_normalize(items)
        df['date'] = pd.to_datetime(df['date'])
        
        # Create DateTime column
        if 'hour' in df.columns:
            df['DateTime'] = pd.to_datetime(
                df['date'].dt.date.astype(str) + ' ' + df['hour']
            )
            df['DateTime'] = df['DateTime'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Store in database
        records_added = 0
        for _, row in df.iterrows():
            # Check if record already exists
            existing_record = ProductionData.query.filter_by(
                datetime=datetime.strptime(row['DateTime'], '%Y-%m-%d %H:%M:%S')
            ).first()
            
            if not existing_record:
                record = ProductionData(
                    datetime=datetime.strptime(row['DateTime'], '%Y-%m-%d %H:%M:%S'),
                    fueloil=row.get('fueloil', 0),
                    gasoil=0,  # Setting default as 0 as per crawler
                    blackcoal=row.get('blackCoal', 0),
                    lignite=row.get('lignite', 0),
                    geothermal=row.get('geothermal', 0),
                    naturalgas=row.get('naturalGas', 0),
                    river=row.get('river', 0),
                    dammedhydro=row.get('dammedHydro', 0),
                    lng=row.get('lng', 0),
                    biomass=row.get('biomass', 0),
                    naphta=row.get('naphta', 0),
                    importcoal=row.get('importCoal', 0),
                    asphaltitecoal=row.get('asphaltiteCoal', 0),
                    wind=row.get('wind', 0),
                    nuclear=0,  # Setting default as 0 as per crawler
                    sun=row.get('sun', 0),
                    importexport=row.get('importExport', 0),
                    total=row.get('total', 0),
                    wasteheat=row.get('wasteheat', 0)
                )
                db.session.add(record)
                records_added += 1
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully added {records_added} new records.',
            'records_added': records_added,
            'date_range': {
                'start': start_date_str,
                'end': end_date_str
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_rolling_data: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@main.route('/check-demand-completeness')
def check_demand_completeness():
    try:
        # Get min and max dates
        min_date = db.session.query(db.func.min(DemandData.datetime)).scalar()
        max_date = db.session.query(db.func.max(DemandData.datetime)).scalar()
        
        # Get count of records
        total_records = db.session.query(DemandData).count()
        
        # Calculate expected records (assuming 24 records per day)
        days = (max_date - min_date).days + 1
        expected_records = days * 24
        
        # Get all existing datetimes and find gaps in Python
        all_datetimes_query = db.session.query(DemandData.datetime).order_by(DemandData.datetime).all()
        existing_hours = set()
        
        for dt_tuple in all_datetimes_query:
            dt = dt_tuple[0]
            # Truncate to hour
            hour_dt = dt.replace(minute=0, second=0, microsecond=0)
            existing_hours.add(hour_dt)
        
        # Generate all expected hours
        from datetime import timedelta
        expected_hours = []
        current = min_date.replace(minute=0, second=0, microsecond=0)
        end = max_date.replace(minute=0, second=0, microsecond=0)
        
        while current <= end:
            expected_hours.append(current)
            current += timedelta(hours=1)
        
        # Find missing hours
        missing_datetimes = [dt for dt in expected_hours if dt not in existing_hours]
        
        # Convert to the format expected by the rest of the code
        missing_dates = [(dt,) for dt in missing_datetimes]
        
        # Group consecutive missing dates into gap ranges
        gaps = []
        all_missing_dates_list = []
        
        # Convert missing_dates to list first
        if missing_dates and len(missing_dates) > 0:
            missing_datetimes = [d[0] for d in missing_dates]
            all_missing_dates_list = [d.strftime('%Y-%m-%d %H:%M') for d in missing_datetimes]
            
            # Group consecutive dates into gaps
            if len(missing_datetimes) > 0:
                gap_start = missing_datetimes[0]
                gap_end = missing_datetimes[0]
                
                for i in range(1, len(missing_datetimes)):
                    current = missing_datetimes[i]
                    # Check if current datetime is consecutive (1 hour after gap_end)
                    if (current - gap_end).total_seconds() == 3600:
                        gap_end = current
                    else:
                        # Save the previous gap and start a new one
                        gap_hours = int((gap_end - gap_start).total_seconds() / 3600) + 1
                        gaps.append({
                            'start': gap_start.strftime('%Y-%m-%d %H:%M'),
                            'end': gap_end.strftime('%Y-%m-%d %H:%M'),
                            'missing_hours': gap_hours
                        })
                        gap_start = current
                        gap_end = current
                
                # Don't forget the last gap
                gap_hours = int((gap_end - gap_start).total_seconds() / 3600) + 1
                gaps.append({
                    'start': gap_start.strftime('%Y-%m-%d %H:%M'),
                    'end': gap_end.strftime('%Y-%m-%d %H:%M'),
                    'missing_hours': gap_hours
                })
        
        return jsonify({
            'start_date': min_date.strftime('%Y-%m-%d %H:%M'),
            'end_date': max_date.strftime('%Y-%m-%d %H:%M'),
            'total_days': days,
            'total_records': total_records,
            'expected_records': expected_records,
            'missing_records': expected_records - total_records,
            'coverage_percentage': (total_records / expected_records) * 100,
            'total_gaps': len(gaps),
            'gaps': gaps,
            'all_missing_dates': all_missing_dates_list,
            'total_missing_dates': len(missing_dates) if missing_dates else 0,
            'debug_missing_dates_length': len(missing_dates) if missing_dates else 0,
            'debug_missing_dates_type': str(type(missing_dates)),
            'debug_first_missing': str(missing_dates[0]) if missing_dates and len(missing_dates) > 0 else 'none'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/get_demand_data')
def get_demand_data():
    try:
        current_year = datetime.now().year
        previous_year = current_year - 1
        
        # Get current date to limit the data range
        current_date = datetime.now()
        
        # Use raw SQL to avoid ORM issues with missing columns
        query = text("""
            SELECT id, datetime, consumption 
            FROM demand_data
            WHERE (EXTRACT(year FROM datetime) = :current_year AND datetime <= :current_date)
               OR (EXTRACT(year FROM datetime) = :previous_year)
            ORDER BY datetime
        """)
        
        # Execute query
        result = db.session.execute(
            query, 
            {
                "current_year": current_year, 
                "current_date": current_date,
                "previous_year": previous_year
            }
        ).fetchall()
        
        # Process the data for the frontend
        current_year_data = []
        previous_year_data = []
        
        for row in result:
            data_point = {
                "datetime": row.datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "consumption": float(row.consumption)
            }
            
            if row.datetime.year == current_year:
                current_year_data.append(data_point)
            else:
                previous_year_data.append(data_point)
        
        # Convert to pandas DataFrame for resampling and metrics
        if current_year_data:
            df_current = pd.DataFrame(current_year_data)
            df_current['datetime'] = pd.to_datetime(df_current['datetime'])
            df_current.set_index('datetime', inplace=True)
            weekly_avg_current = df_current.resample('W').mean()
        else:
            weekly_avg_current = pd.DataFrame()
            
        if previous_year_data:
            df_previous = pd.DataFrame(previous_year_data)
            df_previous['datetime'] = pd.to_datetime(df_previous['datetime'])
            df_previous.set_index('datetime', inplace=True)
            weekly_avg_previous = df_previous.resample('W').mean()
        else:
            weekly_avg_previous = pd.DataFrame()
        
        # Calculate MTD/YTD metrics (average consumption), comparing to same period last year
        # IMPORTANT: EPİAŞ has 4-hour data lag, so we must compare like-for-like periods
        metrics = {}
        try:
            now = pd.to_datetime(current_date)
            # Use the actual last timestamp from database instead of assuming 4-hour lag
            # This handles cases where data might be delayed more than 4 hours
            if current_year_data:
                data_available_until = df_current.index.max()
            else:
                # Fallback to 4-hour lag if no current year data
                data_available_until = now - pd.Timedelta(hours=4)
            
            # Month-to-date masks (both years compare to data_available_until)
            if current_year_data:
                mtd_start = data_available_until.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                df_cur_mtd = df_current.loc[(df_current.index >= mtd_start) & (df_current.index <= data_available_until)]
            else:
                df_cur_mtd = pd.DataFrame(columns=['consumption'])

            if previous_year_data:
                # Use same hour-of-day for previous year comparison
                prev_data_available = data_available_until.replace(year=previous_year)
                mtd_start_prev = prev_data_available.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                df_prev_mtd = df_previous.loc[(df_previous.index >= mtd_start_prev) & (df_previous.index <= prev_data_available)]
            else:
                df_prev_mtd = pd.DataFrame(columns=['consumption'])

            # Year-to-date masks (both years compare to data_available_until at same hour)
            # IMPORTANT: Handle leap years - if comparing across leap year boundary, skip Feb 29
            if current_year_data:
                ytd_start = data_available_until.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                df_cur_ytd = df_current.loc[(df_current.index >= ytd_start) & (df_current.index <= data_available_until)]
            else:
                df_cur_ytd = pd.DataFrame(columns=['consumption'])

            if previous_year_data:
                # Compare to same hour last year (accounting for 4-hour lag)
                prev_ytd_end = data_available_until.replace(year=previous_year)
                ytd_start_prev = prev_ytd_end.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                df_prev_ytd = df_previous.loc[(df_previous.index >= ytd_start_prev) & (df_previous.index <= prev_ytd_end)]
                
                # Handle leap year: if previous year was leap year and current is not (or vice versa),
                # exclude Feb 29 from the leap year to ensure fair comparison
                import calendar
                prev_is_leap = calendar.isleap(previous_year)
                curr_is_leap = calendar.isleap(current_year)
                
                if prev_is_leap and not curr_is_leap:
                    # Remove Feb 29 from previous year data
                    feb29_prev = pd.Timestamp(year=previous_year, month=2, day=29)
                    df_prev_ytd = df_prev_ytd[~((df_prev_ytd.index.month == 2) & (df_prev_ytd.index.day == 29))]
                elif curr_is_leap and not prev_is_leap and data_available_until.month > 2:
                    # If we're past Feb 29 in current leap year, remove Feb 29 from current year
                    df_cur_ytd = df_cur_ytd[~((df_cur_ytd.index.month == 2) & (df_cur_ytd.index.day == 29))]
            else:
                df_prev_ytd = pd.DataFrame(columns=['consumption'])

            def total(series: pd.Series) -> float:
                return float(series.sum()) if series is not None and not series.empty else 0.0

            mtd_cur = total(df_cur_mtd['consumption'])
            mtd_prev = total(df_prev_mtd['consumption'])
            ytd_cur = total(df_cur_ytd['consumption'])
            ytd_prev = total(df_prev_ytd['consumption'])

            def delta(cur: float, prev: float):
                diff = cur - prev
                pct = (diff / prev * 100.0) if prev not in [0, None] else None
                return diff, pct

            mtd_diff, mtd_pct = delta(mtd_cur, mtd_prev)
            ytd_diff, ytd_pct = delta(ytd_cur, ytd_prev)

            metrics = {
                'mtd': {
                    'current_year': round(mtd_cur, 2),
                    'previous_year': round(mtd_prev, 2),
                    'diff': round(mtd_diff, 2),
                    'pct': round(mtd_pct, 2) if mtd_pct is not None else None,
                    'month_name': now.strftime('%B')
                },
                'ytd': {
                    'current_year': round(ytd_cur, 2),
                    'previous_year': round(ytd_prev, 2),
                    'diff': round(ytd_diff, 2),
                    'pct': round(ytd_pct, 2) if ytd_pct is not None else None
                }
            }
        except Exception as _:
            metrics = {}

        # Format the response as expected by the frontend
        result = {'consumption': {}, 'metrics': metrics}
        
        if not weekly_avg_current.empty:
            result['consumption'][str(current_year)] = weekly_avg_current['consumption'].tolist()
            
        if not weekly_avg_previous.empty:
            result['consumption'][str(previous_year)] = weekly_avg_previous['consumption'].tolist()
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in get_demand_data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/get_monthly_demand_data')
def get_monthly_demand_data():
    try:
        current_year = datetime.now().year
        previous_year = current_year - 1
        
        # Get current date to limit the data range
        current_date = datetime.now()
        
        # Use raw SQL to get monthly averages
        query = text("""
            SELECT 
                EXTRACT(year FROM datetime) as year,
                EXTRACT(month FROM datetime) as month,
                AVG(consumption) as avg_consumption
            FROM demand_data
            WHERE (EXTRACT(year FROM datetime) = :current_year AND datetime <= :current_date)
               OR (EXTRACT(year FROM datetime) = :previous_year)
            GROUP BY EXTRACT(year FROM datetime), EXTRACT(month FROM datetime)
            ORDER BY year, month
        """)
        
        # Execute query
        result = db.session.execute(
            query, 
            {
                "current_year": current_year, 
                "current_date": current_date,
                "previous_year": previous_year
            }
        ).fetchall()
        
        # Process the data for the frontend
        monthly_data = {
            str(current_year): [0] * 12,
            str(previous_year): [0] * 12
        }
        
        for row in result:
            year_str = str(int(row.year))
            month_idx = int(row.month) - 1  # Convert to 0-based index
            if year_str in monthly_data:
                monthly_data[year_str][month_idx] = float(row.avg_consumption) if row.avg_consumption else 0
        
        return jsonify({'monthly_consumption': monthly_data})
        
    except Exception as e:
        print(f"Error in get_monthly_demand_data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/update_demand_data_api')
def update_demand_data_api():
    try:
        # Get the latest date in the database
        latest_record = db.session.query(DemandData.datetime).order_by(DemandData.datetime.desc()).first()
        
        # If no data, start from a default date
        if not latest_record:
            start_date = datetime(2023, 1, 1)
        else:
            # Start from the hour after the latest record
            start_date = latest_record[0] + timedelta(hours=1)
        
        # End date is current hour
        end_date = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        # If already up to date
        if start_date >= end_date:
            return jsonify({
                'message': 'Database is already up to date.',
                'records_added': 0
            })
        
        # Format dates for API
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # Get TGT token
        tgt_token = get_tgt_token(
            current_app.config.get('USERNAME'),
            current_app.config.get('PASSWORD')
        )
        
        # Prepare API request
        url = "https://seffaflik.epias.com.tr/electricity-service/v1/consumption/data/realtime-consumption"
        
        payload = {
            "startDate": f"{start_date_str}T00:00:00+03:00",
            "endDate": f"{end_date_str}T23:59:59+03:00",
            "region": "TR1",
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': "application/json",
            'TGT': tgt_token
        }
        
        # Make API request
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        # Process the data
        items = response.json().get('items', [])
        if not items:
            return jsonify({
                'message': 'No new data found for the specified date range.',
                'records_added': 0
            })
            
        # Convert to DataFrame for easier processing
        df = pd.json_normalize(items)
        df['date'] = pd.to_datetime(df['date'])
        
        # Store in database
        records_added = 0
        for _, row in df.iterrows():
            # Parse datetime from the date field
            dt = row['date'].to_pydatetime()
            
            # Check if record already exists
            existing_record = DemandData.query.filter_by(
                datetime=dt
            ).first()
            
            if not existing_record:
                record = DemandData(
                    datetime=dt,
                    consumption=row.get('consumption', 0),
                    created_at=datetime.now()  # Explicitly set created_at
                )
                db.session.add(record)
                records_added += 1
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully added {records_added} new records.',
            'records_added': records_added,
            'date_range': {
                'start': start_date.strftime('%Y-%m-%d %H:%M'),
                'end': end_date.strftime('%Y-%m-%d %H:%M')
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_demand_data_api: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/check_demand_updates')
def check_demand_updates():
    try:
        # Get the last 15 days of data
        end_date = datetime.now().replace(tzinfo=None)  # Ensure timezone-naive
        start_date = end_date - timedelta(days=15)
        
        # Set up a requests session with retry logic
        session = requests.Session()
        retries = requests.adapters.Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504, 429],
        )
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=retries))
        
        # Get TGT token
        tgt_token = get_tgt_token(
            current_app.config.get('USERNAME'),
            current_app.config.get('PASSWORD')
        )
        
        # Group dates by month to minimize API calls
        date_groups = {}
        current_date = start_date
        while current_date <= end_date:
            month_key = current_date.strftime('%Y-%m')
            if month_key not in date_groups:
                date_groups[month_key] = []
            date_groups[month_key].append(current_date)
            current_date += timedelta(hours=1)
        
        # Process each month
        success_count = 0
        updated_count = 0
        
        for month, dates in date_groups.items():
            # Get first and last day of the month
            first_date = min(dates)
            last_date = max(dates)
            
            # Prepare API request
            url = "https://seffaflik.epias.com.tr/electricity-service/v1/consumption/data/realtime-consumption"
            
            payload = {
                "startDate": f"{first_date.strftime('%Y-%m-%d')}T00:00:00+03:00",
                "endDate": f"{last_date.strftime('%Y-%m-%d')}T23:59:59+03:00",
                "region": "TR1",
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': "application/json",
                'TGT': tgt_token
            }
            
            # Make API request
            response = session.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            # Process the data
            items = response.json().get('items', [])
            if not items:
                continue
                
            # Convert to DataFrame for easier processing
            df = pd.json_normalize(items)
            df['date'] = pd.to_datetime(df['date'])
            
            # Get existing records for this date range
            existing_records = {}
            query = text("""
                SELECT datetime, consumption 
                FROM demand_data 
                WHERE datetime >= :start_date AND datetime <= :end_date
            """)
            result = db.session.execute(query, {
                'start_date': first_date,
                'end_date': last_date
            }).fetchall()
            
            for record in result:
                existing_records[record[0].strftime('%Y-%m-%d %H:%M')] = float(record[1])
            
            # Process items in batches
            batch_data = []
            current_time = datetime.now()  # Get current time once for all records
            
            for _, row in df.iterrows():
                try:
                    # Convert to timezone-naive datetime for comparison
                    dt = row['date'].to_pydatetime()
                    if dt.tzinfo is not None:
                        dt = dt.replace(tzinfo=None)
                    
                    dt_key = dt.strftime('%Y-%m-%d %H:%M')
                    consumption = float(row.get('consumption', 0))
                    
                    # Check if this datetime is in our date range and has a different value
                    if dt >= first_date and dt <= last_date:
                        success_count += 1
                        
                        if dt_key in existing_records:
                            # Compare with existing value with a small tolerance for floating point differences
                            if abs(existing_records[dt_key] - consumption) > 0.01:
                                batch_data.append({
                                    'datetime': dt,
                                    'consumption': consumption,
                                    'created_at': current_time
                                })
                                updated_count += 1
                except Exception as e:
                    print(f"Error processing item: {e}")
                    continue
            
            # Update records with different values
            if batch_data:
                try:
                    # Use bulk insert with ON CONFLICT DO UPDATE
                    insert_stmt = """
                    INSERT INTO demand_data (datetime, consumption, created_at)
                    VALUES (:datetime, :consumption, :created_at)
                    ON CONFLICT (datetime) DO UPDATE
                    SET consumption = EXCLUDED.consumption,
                        created_at = EXCLUDED.created_at
                    """
                    
                    db.session.execute(text(insert_stmt), batch_data)
                    db.session.commit()
                    
                except Exception as e:
                    db.session.rollback()
                    print(f"Error updating batch data: {e}")
        
        return jsonify({
            'message': f'Successfully checked for updates. Found {updated_count} records with changed values.',
            'updated_records': updated_count,
            'date_range': {
                'start': start_date.strftime('%Y-%m-%d %H:%M'),
                'end': end_date.strftime('%Y-%m-%d %H:%M')
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in check_demand_updates: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@main.route('/lignite_heatmap_data', methods=['POST'])
def lignite_heatmap_data():
    try:
        data = request.get_json()
        date_str = data.get('date')
        version = data.get('version', 'current')
        
        if not date_str:
            return jsonify({'code': 400, 'message': 'Date is required'})
        
        # Parse date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Import the model
        from app.models.heatmap import LigniteHeatmapData
        from app.mappings import lignite_mapping
        
        # Query lignite heatmap data
        query = LigniteHeatmapData.query.filter(
            LigniteHeatmapData.date == date_obj,
            LigniteHeatmapData.version == version
        ).all()
        
        if not query:
            current_app.logger.info(f"No lignite data in DB for {date_obj}, fetching from API...")
            
            # Get authentication token and URL
            dpp_url = current_app.config['DPP_FIRST_VERSION_URL'] if version == 'first' else current_app.config['DPP_URL']
            tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
            
            # Initialize DataFrame with hours and fill with 0
            hours = [f"{str(i).zfill(2)}:00" for i in range(24)]
            df = pd.DataFrame(0, index=hours, columns=lignite_mapping['plant_names'])
            
            # Iterate through all plants with their IDs
            for plant_name, o_id, pl_id in zip(
                lignite_mapping['plant_names'],
                lignite_mapping['o_ids'],
                lignite_mapping['uevcb_ids']
            ):
                try:
                    # Format request data exactly as shown in working example
                    request_data = {
                        'startDate': f"{date_obj.strftime('%Y-%m-%d')}T00:00:00+03:00",
                        'endDate': f"{date_obj.strftime('%Y-%m-%d')}T00:00:00+03:00",
                        'region': 'TR1',
                        'organizationId': int(o_id),
                        'uevcbId': int(pl_id)
                    }
                    
                    current_app.logger.info(f"Fetching data for {plant_name} with data: {request_data}")
                    
                    response = requests.post(
                        dpp_url,
                        headers={
                            'Accept': 'application/json',
                            'Content-Type': 'application/json',
                            'TGT': tgt_token
                        },
                        json=request_data,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        current_app.logger.info(f"Raw response for {plant_name}: {str(response_data)[:200]}...")
                        
                        if response_data and 'items' in response_data:
                            for item in response_data['items']:
                                try:
                                    hour = item.get('time', '00:00').split(':')[0]
                                    # Try both toplam and linyit fields
                                    value = None
                                    if item.get('linyit') is not None:
                                        value = float(item['linyit'])
                                    elif item.get('toplam') is not None:
                                        value = float(item['toplam'])
                                        
                                    if value is not None:
                                        df.at[f"{hour.zfill(2)}:00", plant_name] = value
                                        current_app.logger.info(f"Added value {value} for {plant_name} at hour {hour}")
                                except (ValueError, TypeError) as e:
                                    current_app.logger.warning(f"Invalid value for {plant_name} at hour {hour}")
                                    continue
                        else:
                            current_app.logger.warning(f"No items in response for {plant_name}")
                    else:
                        current_app.logger.error(f"Bad response status {response.status_code} for {plant_name}")
                    
                    time.sleep(0.5)  # Small delay between API calls
                    
                except Exception as e:
                    current_app.logger.error(f"Error fetching data for {plant_name}: {str(e)}")
                    continue
            
            # Process the dataframe
            result = {
                "code": 200,
                "data": {
                    "hours": df.index.tolist(),
                    "plants": [f"{name}--{capacity} MW" for name, capacity in zip(
                        lignite_mapping['plant_names'],
                        lignite_mapping['capacities']
                    )],
                    "values": df.values.tolist()
                }
            }
            
            return jsonify(result)
        
        # If we have data in DB, process it as before
        df = process_heatmap_data(query, lignite_mapping)
        
        if df.empty:
            return jsonify({
                "code": 404,
                "error": f"No data available for date {date_obj}"
            })
        
        # Get plant names from mapping
        plant_names = lignite_mapping['plant_names']
        hours = [f"{i:02d}:00" for i in range(24)]
        
        # Initialize values matrix
        values = [[0 for _ in range(len(plant_names))] for _ in range(24)]
        
        # Fill values matrix
        for record in query:
            try:
                plant_index = plant_names.index(record.plant_name)
                hour_index = record.hour
                if 0 <= hour_index < 24:
                    values[hour_index][plant_index] = record.value
            except ValueError:
                # Plant not in mapping, skip
                continue
        
        response_data = {
            'hours': hours,
            'plants': [f"{name}--{capacity} MW" for name, capacity in zip(
                lignite_mapping['plant_names'],
                lignite_mapping['capacities']
            )],
            'values': values
        }
        
        return jsonify({'code': 200, 'data': response_data})
        
    except ValueError as ve:
        return jsonify({"code": 400, "error": f"Invalid date format: {str(ve)}"})
    except Exception as e:
        current_app.logger.error(f"Error in lignite_heatmap_data: {str(e)}")
        return jsonify({'code': 500, 'message': 'Internal server error'})

@main.route('/lignite_realtime_heatmap_data', methods=['POST'])
def lignite_realtime_heatmap_data():
    try:
        data = request.get_json()
        date_str = data.get('date')
        
        if not date_str:
            return jsonify({'code': 400, 'message': 'Date is required'})
        
        # Parse date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Import the model
        from app.models.realtime import LigniteRealtimeData
        from app.mappings import lignite_mapping
        
        # Query lignite realtime data
        query = LigniteRealtimeData.query.filter(
            LigniteRealtimeData.date == date_obj
        ).all()
        
        # If we have data in database, process and return it
        if query:
            # Get plant names from mapping
            plant_names = lignite_mapping['plant_names']
            hours = [f"{i:02d}:00" for i in range(24)]
            
            # Initialize values matrix
            values = [[0 for _ in range(len(plant_names))] for _ in range(24)]
            
            # Fill values matrix
            for record in query:
                try:
                    plant_index = plant_names.index(record.plant_name)
                    hour_index = record.hour
                    if 0 <= hour_index < 24:
                        values[hour_index][plant_index] = record.value or 0
                except ValueError:
                    # Plant not in mapping, skip
                    continue
            
            response_data = {
                'hours': hours,
                'plants': [f"{name}--{capacity} MW" for name, capacity in zip(
                    lignite_mapping['plant_names'],
                    lignite_mapping['capacities']
                )],
                'values': values
            }
            
            return jsonify({'code': 200, 'data': response_data})

        # If no data in database, fetch from API
        hours = [f"{str(i).zfill(2)}:00" for i in range(24)]
        df = pd.DataFrame(index=hours, columns=lignite_mapping['plant_names'])
        
        # Get authentication token
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
        
        # Create mappings for plant IDs (handle both valid and invalid p_ids)
        p_id_count = {}
        p_id_indices = {}
        
        # Process all p_ids, including invalid ones
        for p_id in lignite_mapping['p_ids']:
            p_id_count[p_id] = lignite_mapping['p_ids'].count(p_id)

        for idx, p_id in enumerate(lignite_mapping['p_ids']):
            if p_id not in p_id_indices:
                p_id_indices[p_id] = []
            p_id_indices[p_id].append(idx)
        
        # Separate valid and invalid p_ids
        valid_p_ids = [p_id for p_id in set(lignite_mapping['p_ids']) if p_id and p_id > 0]
        invalid_p_ids = [p_id for p_id in set(lignite_mapping['p_ids']) if not p_id or p_id <= 0]
        
        current_app.logger.info(f"Lignite plants: {len(set(lignite_mapping['p_ids']))} total, {len(valid_p_ids)} valid, {len(invalid_p_ids)} invalid")

        # Fetch realtime data for each unique powerplant
        batch_data = []
        
        # Handle valid p_ids - fetch from API
        for p_id in valid_p_ids:
            try:
                print(f"Fetching realtime data for lignite plant ID: {p_id}")
                
                request_data = {
                    "startDate": f"{date_str}T00:00:00+03:00",
                    "endDate": f"{date_str}T23:59:59+03:00",
                    "powerPlantId": str(p_id)
                }

                # Make API request
                response = requests.post(
                    current_app.config['REALTIME_URL'],
                    json=request_data,
                    headers={'TGT': tgt_token}
                )
                response.raise_for_status()
                
                items = response.json().get('items', [])
                
                hourly_values = [0] * 24
                for item in items:
                    hour = int(item.get('hour', '00:00').split(':')[0])
                    total = item.get('total', 0)
                    hourly_values[hour] = total

                # Distribute values among plant instances
                count = p_id_count[p_id]
                distributed_values = [val / count for val in hourly_values]
                
                for idx in p_id_indices[p_id]:
                    plant_name = lignite_mapping['plant_names'][idx]
                    df[plant_name] = distributed_values
                    
                    # Prepare database records
                    for hour, value in enumerate(distributed_values):
                        batch_data.append({
                            'date': date_obj,
                            'hour': hour,
                            'plant_name': plant_name,
                            'value': value
                        })
                
                time.sleep(0.5)  # Small delay between requests
                
            except Exception as e:
                print(f"Error fetching realtime data for lignite plant {p_id}: {str(e)}")
                for idx in p_id_indices.get(p_id, []):
                    plant_name = lignite_mapping['plant_names'][idx]
                    df[plant_name] = [0] * 24
        
        # Handle invalid p_ids - set to zero values
        for p_id in invalid_p_ids:
            current_app.logger.info(f"Setting zero values for invalid lignite plant ID: {p_id}")
            for idx in p_id_indices.get(p_id, []):
                plant_name = lignite_mapping['plant_names'][idx]
                df[plant_name] = [0] * 24
                
                # Prepare database records with zero values
                for hour in range(24):
                    batch_data.append({
                        'date': date_obj,
                        'hour': hour,
                        'plant_name': plant_name,
                        'value': 0.0
                    })

        # Store the fetched data in database
        try:
            if batch_data:
                db.session.bulk_insert_mappings(LigniteRealtimeData, batch_data)
                db.session.commit()
        except Exception as e:
            print(f"Error storing lignite realtime data: {str(e)}")
            db.session.rollback()

        return jsonify({
            "code": 200,
            "data": {
                "hours": df.index.tolist(),
                "plants": [f"{name}--{capacity} MW" for name, capacity in zip(
                    lignite_mapping['plant_names'],
                    lignite_mapping['capacities']
                )],
                "values": df.values.tolist()
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in lignite_realtime_heatmap_data: {str(e)}")
        return jsonify({'code': 500, 'message': 'Internal server error'})

@main.route('/update-unlicensed-solar-data')
def update_unlicensed_solar_data():
    try:
        # Get current date
        current_date = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        
        # Look back 30 days for retroactive updates
        start_date = current_date - timedelta(days=30)
        end_date = current_date
        
        import os
        import requests
        import zipfile
        import tempfile
        import json
        from dotenv import load_dotenv
        from sqlalchemy import text
        
        # Load environment variables
        load_dotenv()
        
        # Get credentials from environment
        username = os.getenv('XTRADERS_USERNAME')
        password = os.getenv('XTRADERS_PASSWORD')
        
        if not username or not password:
            return jsonify({'error': 'Missing API credentials'}), 500
        
        # Get authentication token
        auth_response = requests.post(
            "https://api-markets.meteologica.com/api/v1/login",
            json={"user": username, "password": password}
        )
        auth_response.raise_for_status()
        token = auth_response.json().get("token")
        
        if not token:
            return jsonify({'error': 'Failed to get authentication token'}), 500
        
        records_added = 0
        records_updated = 0
        
        print(f"🔍 RETROACTIVE UPDATE (Unlicensed Solar):")
        print(f"   Checking date range: {start_date} to {end_date}")
        
        # Calculate which months we need to process
        months_to_process = set()
        current_check = start_date
        while current_check <= end_date:
            months_to_process.add((current_check.year, current_check.month))
            # Move to next month
            if current_check.month == 12:
                current_check = current_check.replace(year=current_check.year + 1, month=1, day=1)
            else:
                current_check = current_check.replace(month=current_check.month + 1, day=1)
        
        print(f"   Processing months: {sorted(months_to_process)}")
        
        # Collect all data first, then select best for each hour
        hourly_data = {}  # Key: hour datetime (minute=0), Value: list of forecasts for that hour
        
        for year, month in sorted(months_to_process):
            try:
                # Use content ID 1430 for unlicensed solar
                response = requests.get(
                    url=f"https://api-markets.meteologica.com/api/v1/contents/1430/historical_data/{year}/{month}",
                    params={"token": token}
                )
                
                if response.status_code != 200:
                    print(f"Failed to fetch data for {year}-{month}: {response.status_code}")
                    continue
                
                # Check if response is a zip file
                if not (response.headers.get('content-type', '').find('zip') != -1 or response.content.startswith(b'PK')):
                    print(f"Response for {year}-{month} is not a ZIP file")
                    continue
                
                # Process ZIP file
                with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
                    temp_zip.write(response.content)
                    temp_zip_path = temp_zip.name
                
                try:
                    with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                        json_files = [f for f in zip_ref.namelist() if f.endswith('.json')]
                        
                        print(f"Processing {year}-{month} (Unlicensed): {len(json_files)} files")
                        
                        # Process each JSON file (each represents a forecast at some minute)
                        for json_filename in json_files:
                            try:
                                with zip_ref.open(json_filename) as json_file_handle:
                                    json_content = json.load(json_file_handle)
                                    
                                    # Extract datetime from filename (e.g., 1430_202508141513.json)
                                    if '_' in json_filename and '.json' in json_filename:
                                        parts = json_filename.split('_')
                                        if len(parts) >= 2:
                                            date_part = parts[1].replace('.json', '')
                                            if len(date_part) >= 12:
                                                try:
                                                    # Parse: 202508141513 -> 2025-08-14 15:13
                                                    file_year = int(date_part[:4])
                                                    file_month = int(date_part[4:6])
                                                    day = int(date_part[6:8])
                                                    hour = int(date_part[8:10])
                                                    minute = int(date_part[10:12])
                                                    
                                                    from_dt = datetime(file_year, file_month, day, hour, minute, tzinfo=timezone.utc)
                                                    
                                                    # Check if this record is in our date range
                                                    if start_date <= from_dt <= end_date:
                                                        # Extract forecast value from JSON
                                                        forecast_value = None
                                                        if 'data' in json_content and isinstance(json_content['data'], list):
                                                            for data_entry in json_content['data']:
                                                                if 'forecast' in data_entry:
                                                                    forecast_value = float(data_entry['forecast'])
                                                                    break
                                                        
                                                        if forecast_value is not None:
                                                            # Group by hour (set minute to 0 for the key)
                                                            hour_key = from_dt.replace(minute=0, second=0, microsecond=0)
                                                            
                                                            if hour_key not in hourly_data:
                                                                hourly_data[hour_key] = []
                                                            
                                                            hourly_data[hour_key].append({
                                                                'original_datetime': from_dt,
                                                                'forecast_value': forecast_value,
                                                                'minute': minute
                                                            })
                                                        
                                                except (ValueError, TypeError) as e:
                                                    continue
                                            
                            except Exception as e:
                                continue
                finally:
                    # Clean up temporary file
                    os.unlink(temp_zip_path)
                                
            except Exception as e:
                print(f"Error processing {year}-{month}: {e}")
                continue
        
        print(f"   Collected data for {len(hourly_data)} hours")
        
        # Now select the best forecast for each hour and prepare for database
        all_data_to_process = []
        minute_stats = {}
        
        for hour_datetime, forecasts in hourly_data.items():
            # Strategy 1: Prefer minute=0, then closest to minute=0, then use average if multiple
            if len(forecasts) == 1:
                # Only one forecast for this hour, use it
                selected_forecast = forecasts[0]
            else:
                # Multiple forecasts for this hour
                # First, try to find minute=0
                minute_0_forecasts = [f for f in forecasts if f['minute'] == 0]
                if minute_0_forecasts:
                    selected_forecast = minute_0_forecasts[0]  # Use minute=0 if available
                else:
                    # No minute=0, find the one closest to minute=0
                    forecasts.sort(key=lambda x: abs(x['minute']))
                    selected_forecast = forecasts[0]
                
                # Track minute statistics for analysis
                minutes_in_hour = [f['minute'] for f in forecasts]
                minutes_key = ','.join(map(str, sorted(minutes_in_hour)))
                minute_stats[minutes_key] = minute_stats.get(minutes_key, 0) + 1
            
            all_data_to_process.append({
                'datetime': hour_datetime,  # Always use minute=0 for storage
                'unlicensed_solar': selected_forecast['forecast_value'],
                'created_at': datetime.now(timezone.utc)
            })
        
        # Print minute analysis
        if minute_stats:
            print("   Minute patterns found:")
            for pattern, count in sorted(minute_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"     {pattern}: {count} hours")
        
        print(f"   Final data points to process: {len(all_data_to_process)}")
        
        # Now batch process the data using upsert operations
        batch_size = 500  # Process in smaller batches
        total_batches = (len(all_data_to_process) + batch_size - 1) // batch_size
        
        for i in range(0, len(all_data_to_process), batch_size):
            batch = all_data_to_process[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            try:
                # Use PostgreSQL's ON CONFLICT DO UPDATE for upsert
                upsert_sql = """
                INSERT INTO unlicensed_solar_data (datetime, unlicensed_solar, created_at)
                VALUES (:datetime, :unlicensed_solar, :created_at)
                ON CONFLICT (datetime) DO UPDATE SET
                    unlicensed_solar = EXCLUDED.unlicensed_solar,
                    created_at = EXCLUDED.created_at
                """
                
                # Count existing records before upsert
                datetime_list = [item['datetime'] for item in batch]
                existing_count = db.session.query(UnlicensedSolarData).filter(
                    UnlicensedSolarData.datetime.in_(datetime_list)
                ).count()
                
                # Execute upsert
                result = db.session.execute(text(upsert_sql), batch)
                db.session.commit()
                
                # Calculate stats
                batch_added = len(batch) - existing_count
                batch_updated = existing_count
                
                records_added += batch_added
                records_updated += batch_updated
                
                print(f"   Batch {batch_num}/{total_batches}: +{batch_added} new, ~{batch_updated} updated")
                
            except Exception as e:
                db.session.rollback()
                print(f"Error processing batch {batch_num}: {e}")
                continue
        
        return jsonify({
            'message': f'Successfully processed unlicensed solar data: {records_added} new records added, {records_updated} records updated.',
            'records_added': records_added,
            'records_updated': records_updated,
            'date_range': {
                'start': start_date.strftime('%Y-%m-%d %H:%M'),
                'end': end_date.strftime('%Y-%m-%d %H:%M')
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_unlicensed_solar_data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/update-licensed-solar-data')  
def update_licensed_solar_data():
    try:
        # Get current date
        current_date = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        
        # Look back 30 days for retroactive updates
        start_date = current_date - timedelta(days=30)
        end_date = current_date
        
        import os
        import requests
        import zipfile
        import tempfile
        import json
        from dotenv import load_dotenv
        from sqlalchemy import text
        
        load_dotenv()
        
        username = os.getenv('XTRADERS_USERNAME')
        password = os.getenv('XTRADERS_PASSWORD')
        
        if not username or not password:
            return jsonify({'error': 'Missing API credentials'}), 500
        
        # Get authentication token
        auth_response = requests.post(
            "https://api-markets.meteologica.com/api/v1/login",
            json={"user": username, "password": password}
        )
        auth_response.raise_for_status()
        token = auth_response.json().get("token")
        
        records_added = 0
        records_updated = 0
        
        print(f"🔍 RETROACTIVE UPDATE (Licensed Solar):")
        print(f"   Checking date range: {start_date} to {end_date}")
        
        # Calculate which months we need to process
        months_to_process = set()
        current_check = start_date
        while current_check <= end_date:
            months_to_process.add((current_check.year, current_check.month))
            # Move to next month
            if current_check.month == 12:
                current_check = current_check.replace(year=current_check.year + 1, month=1, day=1)
            else:
                current_check = current_check.replace(month=current_check.month + 1, day=1)
        
        print(f"   Processing months: {sorted(months_to_process)}")
        
        # Collect all data first, then select best for each hour
        hourly_data = {}  # Key: hour datetime (minute=0), Value: list of forecasts for that hour
        
        for year, month in sorted(months_to_process):
            try:
                # Use content ID 1429 for licensed solar
                response = requests.get(
                    url=f"https://api-markets.meteologica.com/api/v1/contents/1429/historical_data/{year}/{month}",
                    params={"token": token}
                )
                
                if response.status_code != 200:
                    print(f"Failed to fetch data for {year}-{month}: {response.status_code}")
                    continue
                
                # Check if response is a zip file
                if not (response.headers.get('content-type', '').find('zip') != -1 or response.content.startswith(b'PK')):
                    print(f"Response for {year}-{month} is not a ZIP file")
                    continue
                
                # Process ZIP file
                with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
                    temp_zip.write(response.content)
                    temp_zip_path = temp_zip.name
                
                try:
                    with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                        json_files = [f for f in zip_ref.namelist() if f.endswith('.json')]
                        
                        print(f"Processing {year}-{month} (Licensed): {len(json_files)} files")
                        
                        # Process each JSON file (each represents a forecast at some minute)
                        for json_filename in json_files:
                            try:
                                with zip_ref.open(json_filename) as json_file_handle:
                                    json_content = json.load(json_file_handle)
                                    
                                    # Extract datetime from filename (e.g., 1429_202508141513.json)
                                    if '_' in json_filename and '.json' in json_filename:
                                        parts = json_filename.split('_')
                                        if len(parts) >= 2:
                                            date_part = parts[1].replace('.json', '')
                                            if len(date_part) >= 12:
                                                try:
                                                    # Parse: 202508141513 -> 2025-08-14 15:13
                                                    file_year = int(date_part[:4])
                                                    file_month = int(date_part[4:6])
                                                    day = int(date_part[6:8])
                                                    hour = int(date_part[8:10])
                                                    minute = int(date_part[10:12])
                                                    
                                                    from_dt = datetime(file_year, file_month, day, hour, minute, tzinfo=timezone.utc)
                                                    
                                                    # Check if this record is in our date range
                                                    if start_date <= from_dt <= end_date:
                                                        # Extract forecast value from JSON
                                                        forecast_value = None
                                                        if 'data' in json_content and isinstance(json_content['data'], list):
                                                            for data_entry in json_content['data']:
                                                                if 'forecast' in data_entry:
                                                                    forecast_value = float(data_entry['forecast'])
                                                                    break
                                                        
                                                        if forecast_value is not None:
                                                            # Group by hour (set minute to 0 for the key)
                                                            hour_key = from_dt.replace(minute=0, second=0, microsecond=0)
                                                            
                                                            if hour_key not in hourly_data:
                                                                hourly_data[hour_key] = []
                                                            
                                                            hourly_data[hour_key].append({
                                                                'original_datetime': from_dt,
                                                                'forecast_value': forecast_value,
                                                                'minute': minute
                                                            })
                                                        
                                                except (ValueError, TypeError) as e:
                                                    continue
                                            
                            except Exception as e:
                                continue
                finally:
                    # Clean up temporary file
                    os.unlink(temp_zip_path)
                                
            except Exception as e:
                print(f"Error processing {year}-{month}: {e}")
                continue
        
        print(f"   Collected data for {len(hourly_data)} hours")
        
        # Now select the best forecast for each hour and prepare for database
        all_data_to_process = []
        minute_stats = {}
        
        for hour_datetime, forecasts in hourly_data.items():
            # Strategy 1: Prefer minute=0, then closest to minute=0, then use average if multiple
            if len(forecasts) == 1:
                # Only one forecast for this hour, use it
                selected_forecast = forecasts[0]
            else:
                # Multiple forecasts for this hour
                # First, try to find minute=0
                minute_0_forecasts = [f for f in forecasts if f['minute'] == 0]
                if minute_0_forecasts:
                    selected_forecast = minute_0_forecasts[0]  # Use minute=0 if available
                else:
                    # No minute=0, find the one closest to minute=0
                    forecasts.sort(key=lambda x: abs(x['minute']))
                    selected_forecast = forecasts[0]
                
                # Track minute statistics for analysis
                minutes_in_hour = [f['minute'] for f in forecasts]
                minutes_key = ','.join(map(str, sorted(minutes_in_hour)))
                minute_stats[minutes_key] = minute_stats.get(minutes_key, 0) + 1
            
            all_data_to_process.append({
                'datetime': hour_datetime,  # Always use minute=0 for storage
                'licensed_solar': selected_forecast['forecast_value'],
                'created_at': datetime.now(timezone.utc)
            })
        
        # Print minute analysis
        if minute_stats:
            print("   Minute patterns found:")
            for pattern, count in sorted(minute_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"     {pattern}: {count} hours")
        
        print(f"   Final data points to process: {len(all_data_to_process)}")
        
        # Now batch process the data using upsert operations
        batch_size = 500  # Process in smaller batches
        total_batches = (len(all_data_to_process) + batch_size - 1) // batch_size
        
        for i in range(0, len(all_data_to_process), batch_size):
            batch = all_data_to_process[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            try:
                # Use PostgreSQL's ON CONFLICT DO UPDATE for upsert
                upsert_sql = """
                INSERT INTO licensed_solar_data (datetime, licensed_solar, created_at)
                VALUES (:datetime, :licensed_solar, :created_at)
                ON CONFLICT (datetime) DO UPDATE SET
                    licensed_solar = EXCLUDED.licensed_solar,
                    created_at = EXCLUDED.created_at
                """
                
                # Count existing records before upsert
                datetime_list = [item['datetime'] for item in batch]
                existing_count = db.session.query(LicensedSolarData).filter(
                    LicensedSolarData.datetime.in_(datetime_list)
                ).count()
                
                # Execute upsert
                result = db.session.execute(text(upsert_sql), batch)
                db.session.commit()
                
                # Calculate stats
                batch_added = len(batch) - existing_count
                batch_updated = existing_count
                
                records_added += batch_added
                records_updated += batch_updated
                
                print(f"   Batch {batch_num}/{total_batches}: +{batch_added} new, ~{batch_updated} updated")
                
            except Exception as e:
                db.session.rollback()
                print(f"Error processing batch {batch_num}: {e}")
                continue
        
        return jsonify({
            'message': f'Successfully processed licensed solar data: {records_added} new records added, {records_updated} records updated.',
            'records_added': records_added,
            'records_updated': records_updated,
            'date_range': {
                'start': start_date.strftime('%Y-%m-%d %H:%M'),
                'end': end_date.strftime('%Y-%m-%d %H:%M')
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_licensed_solar_data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/forecast-performance-data')
def get_forecast_performance_data():
    try:
        # Get period parameter from request
        period_days = request.args.get('period', '30', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        import psycopg2
        from sqlalchemy import create_engine
        
        # Get database connection using existing config or environment variables
        try:
            # Try to use Supabase credentials from environment
            user = os.getenv("SUPABASE_USER")
            password = os.getenv("SUPABASE_PASSWORD")
            
            if user and password:
                connection_str = f"postgresql+psycopg2://{user}:{password}@aws-0-us-east-2.pooler.supabase.com:5432/postgres"
                engine = create_engine(connection_str)
            else:
                # Fallback to local database if Supabase credentials not available
                return jsonify({
                    'error': 'Database credentials not configured'
                }), 500
        except Exception as e:
            return jsonify({
                'error': f'Database connection failed: {str(e)}'
            }), 500
        
        # Query actual price data (PTF) - fetch all data first
        ptf_query = "SELECT date, price AS actual_price FROM epias.ptf"
        
        with engine.connect() as conn:
            ptf_df = pd.read_sql(ptf_query, con=conn)
        
        if ptf_df.empty:
            return jsonify({
                'error': f'No PTF data available'
            }), 404
        
        # Clean and process PTF data
        ptf_df['actual_price'] = ptf_df['actual_price'].apply(lambda x: 1 if x <= 0 else x)
        # Convert date to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(ptf_df['date']):
            ptf_df['date'] = ptf_df['date'].apply(lambda x: str(x).split('+')[0].replace('T', ' ') if isinstance(x, str) else x)
            ptf_df['date'] = pd.to_datetime(ptf_df['date'])
        else:
            ptf_df['date'] = pd.to_datetime(ptf_df['date'])
        
        # Query Meteologica forecast data - fetch all data
        meteologica_query = """
        SELECT date, min_price AS meteologica_min, avg_price AS meteologica_avg, max_price AS meteologica_max
        FROM public.meteologica_forecast
        """
        
        with engine.connect() as conn:
            meteologica_forecast = pd.read_sql(meteologica_query, con=conn)
        
        meteologica_forecast['date'] = pd.to_datetime(meteologica_forecast['date'])
        
        # Query model forecast data - fetch all data
        model_query = "SELECT * FROM public.model_forecast_ptf"
        
        with engine.connect() as conn:
            model_forecast = pd.read_sql(model_query, con=conn)
        
        model_forecast['date'] = pd.to_datetime(model_forecast['date'])
        
        # Merge all dataframes
        price_df = pd.merge(ptf_df, meteologica_forecast, on='date', how='outer').sort_values(by='date')
        price_df = pd.merge(price_df, model_forecast, on='date', how='left')
        
        # Apply date filtering after merging
        if start_date and end_date:
            # Custom date range
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            price_df = price_df[(price_df['date'] >= start_dt) & (price_df['date'] <= end_dt)]
            period_info = f"{start_date} to {end_date}"
        else:
            # Use period in days
            cutoff_date = pd.Timestamp.now() - pd.Timedelta(days=period_days)
            price_df = price_df[price_df['date'] >= cutoff_date]
            period_info = f"Last {period_days} Days"
        
        # Remove rows with missing actual prices for evaluation
        evaluation_df = price_df.dropna(subset=['actual_price']).copy()
        
        if evaluation_df.empty:
            return jsonify({
                'error': 'No data available with actual prices for evaluation period'
            }), 404
        
        # Calculate metrics using darts metrics
        def calculate_darts_metrics(actual_series, forecast_series):
            try:
                # Clean the data and align indices
                actual_clean = actual_series.dropna()
                forecast_clean = forecast_series[actual_clean.index].dropna()
                
                if len(forecast_clean) == 0 or len(actual_clean) == 0:
                    return {'wmape': 0, 'rmse': 0, 'r2': 0}
                
                # Find common indices
                common_indices = actual_clean.index.intersection(forecast_clean.index)
                if len(common_indices) == 0:
                    return {'wmape': 0, 'rmse': 0, 'r2': 0}
                
                # Align the data
                actual_aligned = actual_clean[common_indices]
                forecast_aligned = forecast_clean[common_indices]
                
                # Ensure the index is datetime for TimeSeries
                if not isinstance(actual_aligned.index, pd.DatetimeIndex):
                    actual_aligned.index = pd.to_datetime(actual_aligned.index)
                    forecast_aligned.index = pd.to_datetime(forecast_aligned.index)
                
                # Create DataFrame for TimeSeries conversion
                df_actual = pd.DataFrame({'value': actual_aligned.values}, index=actual_aligned.index)
                df_forecast = pd.DataFrame({'value': forecast_aligned.values}, index=forecast_aligned.index)
                
                # Convert to TimeSeries
                ts_actual = TimeSeries.from_dataframe(df_actual, time_col=None, value_cols=['value'])
                ts_forecast = TimeSeries.from_dataframe(df_forecast, time_col=None, value_cols=['value'])
                
                # Calculate metrics using darts
                darts_wmape_raw = wmape(ts_actual, ts_forecast)
                rmse_score = rmse(ts_actual, ts_forecast)
                r2_score_value = r2_score(ts_actual, ts_forecast)
                
                # Calculate WMAPE manually for validation
                # WMAPE = 100 * sum(|actual - forecast|) / sum(|actual|)
                numerator = np.sum(np.abs(actual_aligned.values - forecast_aligned.values))
                denominator = np.sum(np.abs(actual_aligned.values))
                manual_wmape = (numerator / denominator) * 100 if denominator != 0 else 0
                
                # Determine correct WMAPE format and use reliable calculation
                # Check if darts WMAPE is in decimal (0-1) or percentage (0-100) format
                if darts_wmape_raw < 1.0 and manual_wmape > 1.0:
                    wmape_score = darts_wmape_raw * 100  # Convert from decimal to percentage
                elif abs(darts_wmape_raw - manual_wmape) < 5:  # Values are close, use darts
                    wmape_score = darts_wmape_raw
                else:
                    # Use manual calculation if darts value seems unreasonable
                    wmape_score = manual_wmape
                    print(f"Using manual WMAPE calculation ({manual_wmape:.2f}) instead of darts value ({darts_wmape_raw:.2f})")
                
                return {
                    'wmape': round(wmape_score, 2),
                    'rmse': round(rmse_score, 2),
                    'r2': round(r2_score_value, 2)
                }
                
            except Exception as e:
                print(f"Error in calculate_darts_metrics: {e}")
                import traceback
                traceback.print_exc()
                return {'wmape': 0, 'rmse': 0, 'r2': 0}
        
        # Prepare response data
        response_data = {
            'dates': evaluation_df['date'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            'actual_price': evaluation_df['actual_price'].fillna(0).tolist(),
            'meteologica_min': evaluation_df['meteologica_min'].fillna(0).tolist(),
            'meteologica_avg': evaluation_df['meteologica_avg'].fillna(0).tolist(),
            'meteologica_max': evaluation_df['meteologica_max'].fillna(0).tolist(),
            'model_forecast': evaluation_df['best_price'].fillna(0).tolist() if 'best_price' in evaluation_df.columns else [],
            'period_info': period_info,
            'data_points': len(evaluation_df)
        }
        
        # Calculate metrics only for series with data
        metrics = {}
        actual_series = evaluation_df['actual_price']
        
        if not actual_series.dropna().empty:
            for col, name in [
                ('meteologica_min', 'Meteologica Min'),
                ('meteologica_avg', 'Meteologica Avg'),
                ('meteologica_max', 'Meteologica Max'),
                ('best_price', 'Model Forecast')
            ]:
                if col in evaluation_df.columns and not evaluation_df[col].dropna().empty:
                    try:
                        metrics[name] = calculate_darts_metrics(actual_series, evaluation_df[col])
                    except Exception as e:
                        print(f"Error calculating metrics for {name}: {e}")
                        metrics[name] = {'wmape': 0, 'rmse': 0, 'r2': 0}
        
        response_data['metrics'] = metrics
        
        return jsonify({
            'code': 200,
            'data': response_data
        })
        
    except Exception as e:
        print(f"Error in get_forecast_performance_data: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'code': 500,
            'error': f'Error fetching forecast performance data: {str(e)}'
        }), 500