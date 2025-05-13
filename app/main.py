import sys
import time
from datetime import datetime, timedelta
from flask import abort, app, Blueprint, session, render_template, redirect, url_for, Response, request, jsonify, Request, Response, current_app
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

pd.set_option('future.no_silent_downcasting', True)

main = Blueprint('main', __name__)

@main.route('/', methods=['GET'])
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
        
        # Create a dictionary to track how many times each powerplant ID is used
        p_id_count = {}
        for p_id in plant_mapping['p_ids']:
            p_id_count[p_id] = plant_mapping['p_ids'].count(p_id)

        # Create a mapping of powerplant ID to its indices in the plant list
        p_id_indices = {}
        for idx, p_id in enumerate(plant_mapping['p_ids']):
            if p_id not in p_id_indices:
                p_id_indices[p_id] = []
            p_id_indices[p_id].append(idx)

        # Fetch realtime data for each unique powerplant
        batch_data = []  # For storing database records
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
                
                # Process response data
                items = response.json().get('items', [])
                
                # Extract hourly values
                hourly_values = [0] * 24
                for item in items:
                    hour = int(item.get('hour', '00:00').split(':')[0])
                    total = item.get('total', 0)
                    hourly_values[hour] = total

                # Distribute the values among all instances of this powerplant
                count = p_id_count[p_id]
                distributed_values = [val / count for val in hourly_values]
                
                # Store data in DataFrame and prepare database records
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
                # Set zero values for all instances of this powerplant
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
        # Load pre-calculated historical data
        historical_file = os.path.join(current_app.static_folder, 'data', 'historical_averages.json')
        
        if os.path.exists(historical_file):
            print("Using pre-calculated historical data")
            with open(historical_file, 'r') as f:
                historical_data = json.load(f)
        else:
            print("Historical data file not found, calculating from scratch")
            historical_data = {}
        
        # Get current year data only (2025 and beyond)
        current_year = datetime.now().year
        cutoff_date = datetime(current_year, 1, 1)
        
        current_data = db.session.query(ProductionData).filter(
            ProductionData.datetime >= cutoff_date
        ).order_by(ProductionData.datetime).all()
        
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
                'sun': d.sun,
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
            
            # Calculate renewables total and ratio
            df['renewablestotal'] = df['geothermal'] + df['biomass'] + df['wind'] + df['sun']
            df['renewablesratio'] = df['renewablestotal'] / df['total']
            
            # Calculate rolling averages for current year
            rolling_data = historical_data.copy() if historical_data else {}
            
            # Process regular columns with 7-day rolling averages
            regular_columns = [col for col in df.columns if col != 'renewablesratio']
            for column in regular_columns:
                # Resample to daily frequency
                daily_avg = df[column].resample('D', closed='left', label='left').mean()
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
            monthly_data = df.groupby([df.index.month, df.index.year])['renewablesratio'].mean()
            
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
        
        # Find gaps in data using SQLAlchemy's text()
        query = text("""
            WITH dates AS (
                SELECT generate_series(
                    date_trunc('hour', min(datetime)),
                    date_trunc('hour', max(datetime)),
                    '1 hour'::interval
                ) as expected_datetime
                FROM demand_data
            )
            SELECT expected_datetime::timestamp
            FROM dates
            LEFT JOIN demand_data ON dates.expected_datetime = date_trunc('hour', demand_data.datetime)
            WHERE demand_data.id IS NULL
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
            'total_missing_dates': len(missing_dates)
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
        
        # Convert to pandas DataFrame for resampling
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
        
        # Format the response as expected by the frontend
        result = {'consumption': {}}
        
        if not weekly_avg_current.empty:
            result['consumption'][str(current_year)] = weekly_avg_current['consumption'].tolist()
            
        if not weekly_avg_previous.empty:
            result['consumption'][str(previous_year)] = weekly_avg_previous['consumption'].tolist()
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in get_demand_data: {str(e)}")
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
