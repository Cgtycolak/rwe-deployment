import sys
import time
from datetime import datetime, timedelta
from flask import abort, app, Blueprint, session, render_template, redirect, url_for, Response, request, jsonify, Request, Response, current_app
from requests import post, Session
from .functions import get_tgt_token, asutc, invalidates_or_none
from requests.adapters import HTTPAdapter
from urllib3 import Retry
#from requests.packages.urllib3 import Retry
import pandas as pd
import pytz
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
        print(f'Getting AIC data for range: {range_type}')
        
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
        
        session = Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        
        # Fetch AIC data
        res = session.post(
            current_app.config['AIC_URL'],
            json={
                "startDate": start_str,
                "endDate": end_str,
                "region": "TR1"
            },
            headers={'TGT': tgt_token}
        )
        res.raise_for_status()
        data = res.json().get('items', [])
        print(f'Retrieved {len(data)} AIC records')
        
        return jsonify({
            'code': 200,
            'data': data
        })
    except Exception as e:
        print('Error From get_aic_data:', str(e))
        return jsonify({
            'code': 500,
            'message': f'Unable to load AIC data: {str(e)}'
        }), 500
