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
from .tasks.data_fetcher import fetch_and_store_hydro_data, fetch_and_store_natural_gas_data, fetch_and_store_imported_coal_data
from .database.config import db
import requests

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
            data = res.json().get('items')
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
            system_orgs[org_id] = res.json().get('items')
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
                items = data.get('items')
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
    """Legacy endpoint for natural gas heatmap - redirects to natural_gas_heatmap_data"""
    return natural_gas_heatmap_data()

@main.route('/natural_gas_heatmap_data', methods=['POST'])
def natural_gas_heatmap_data():
    try:
        data = request.json
        date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        version = data.get('version', 'current')
        
        # First try to get data from database
        heatmap_data = NaturalGasHeatmapData.query.filter_by(
            date=date,
            version=version
        ).all()
        
        # If no data in database, fetch from API and store it
        if not heatmap_data:
            current_app.logger.info(f"No natural gas data in DB for {date}, fetching from API...")
            
            # Get authentication token and URL
            dpp_url = current_app.config['DPP_FIRST_VERSION_URL'] if version == 'first' else current_app.config['DPP_URL']
            tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
            
            # Create DataFrame for API data
            hours = [f"{str(i).zfill(2)}:00" for i in range(24)]
            df = pd.DataFrame(index=hours, columns=plant_mapping['plant_names'])
            
            # Fetch data for each plant
            for o_id, pl_id, plant_name in zip(
                plant_mapping['o_ids'],
                plant_mapping['uevcb_ids'],
                plant_mapping['plant_names']
            ):
                try:
                    response = fetch_plant_data(date, date, o_id, pl_id, dpp_url, tgt_token)
                    
                    if response and 'items' in response:
                        # Store data in database
                        for item in response['items']:
                            hour = int(item.get('time', '00:00').split(':')[0])
                            value = item.get('toplam', 0)
                            
                            heatmap_data = NaturalGasHeatmapData(
                                date=date,
                                hour=hour,
                                plant_name=plant_name,
                                value=value,
                                version=version
                            )
                            db.session.merge(heatmap_data)
                            
                            # Also update DataFrame for immediate response
                            df.at[f"{str(hour).zfill(2)}:00", plant_name] = value
                    
                    time.sleep(0.5)  # Small delay between API calls
                    
                except Exception as e:
                    current_app.logger.error(f"Error fetching data for {plant_name}: {str(e)}")
                    continue
            
            try:
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Error storing data: {str(e)}")
                db.session.rollback()
            
            # If we got any data from API, use it
            if not df.empty and not df.isna().all().all():
                return jsonify({
                    "code": 200,
                    "data": {
                        "hours": df.index.tolist(),
                        "plants": [f"{name}--{capacity} Mw" for name, capacity in zip(
                            plant_mapping['plant_names'],
                            plant_mapping['capacities']
                        )],
                        "values": df.fillna(0).astype(float).values.tolist()
                    }
                })
            
            # If no data from either source
            return jsonify({
                "code": 404,
                "error": f"No data available for date {date}"
            })
        
        # If we have data in database, process it normally
        df = process_heatmap_data(heatmap_data, plant_mapping)
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
        current_app.logger.error(f"Error in natural_gas_heatmap_data: {str(e)}")
        return jsonify({"code": 500, "error": "Internal server error"})

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
        version = data.get('version', 'current')
        
        heatmap_data = ImportedCoalHeatmapData.query.filter_by(
            date=date,
            version=version
        ).all()
        
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
        version = data.get('version', 'current')
        
        # Try database first
        heatmap_data = HydroHeatmapData.query.filter_by(
            date=date,
            version=version
        ).all()
        
        # If no data, fetch from API
        if not heatmap_data:
            current_app.logger.info(f"No hydro data in DB for {date}, fetching from API...")
            fetch_and_store_hydro_data(date)  # This function already handles API fetching and DB storage
            
            # Try to get the newly stored data
            heatmap_data = HydroHeatmapData.query.filter_by(
                date=date,
                version=version
            ).all()
        
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

@main.route('/imported_coal_heatmap_data', methods=['POST'])
def imported_coal_heatmap_data():
    try:
        data = request.json
        date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        version = data.get('version', 'current')
        
        heatmap_data = ImportedCoalHeatmapData.query.filter_by(
            date=date,
            version=version
        ).all()
        
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
        current_app.logger.error(f"Error in imported_coal_heatmap_data: {str(e)}")
        return jsonify({"code": 500, "error": "Internal server error"})
