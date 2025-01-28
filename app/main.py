import sys
import time
from datetime import datetime, timedelta
from flask import abort, app, Blueprint, session, render_template, redirect, url_for, Response, request, jsonify, Request, Response, current_app
from requests import post, Session
from .functions import get_tgt_token, asutc, invalidates_or_none
from requests.adapters import HTTPAdapter
from urllib3 import Retry
import pandas as pd
import numpy as np

main = Blueprint('main', __name__)

# Define the mapping of plants to their IDs at module level
plant_mapping = {
    'plant_names': [
        "ACWA", "AKENRJ ERZIN", "AKSA ANT", "BAN1", "BAN2", "BAYMINA", 
        "BILGIN1", "BILGIN2", "BURSA BLOK1", "BURSA BLOK2", "CENGIZ",
        "ENKA ADP", "ENKA GBZ1", "ENKA GBZ2", "ENKA IZM1", "ENKA IZM2",
        "GAMA ICAN", "HABAS", "HAM-10", "HAM-20", "RWE", "TEKİRA",
        "TEKİRB", "YENI", "İST A-(A)", "İST A-(B)", "İST A-(C)",
        "İST B (Blok40+ Blok50)"
    ],
    'o_ids': [
        10372, 166, 396, 282, 282, 11816, 294, 294, 195, 195, 1964,
        11810, 11811, 11811, 11997, 11997, 9488, 181, 378, 378, 3625,
        195, 195, 6839, 195, 195, 195, 195
    ],
    'uevcb_ids': [
        3197267, 3205710, 134405, 24604, 3194367, 3205527, 3204758, 3204759,
        924, 928, 1740316, 3205381, 3205524, 3205525, 3206732, 3206733,
        3195727, 2543, 945, 983, 301420, 3204400, 3204399, 472111, 923,
        979, 980, 937
    ],
    'p_ids': [
        2170, 1673, 754, 1426, 2045, 893, 869, 869, 687, 687, 2334, 2800, 
        661, 661, 962, 962, 2048, 2411, 1113, 1113, 966, 1112, 1224, 1424, 
        1230, 1230, 1230, 638 
    ],
    'capacities': [
        "927", "904", "900", "935", "607", "770", "443", "443", "680",
        "680", "610", "820", "815", "815", "760", "760", "853", "1043",
        "600", "600", "797", "480", "480", "480", "450", "450", "450", "816"
    ],
}

export_coal_mapping = {
    'plant_names': [
        "ZETES 1", "ZETES 2-A", "ZETES 2-B", "ZETES 3-A", "ZETES 3-B", "HUNUTLU TES_TR1", 
            "HUNUTLU TES_TR2", "CENAL TES(TR1+TRA)", "CENAL TES(TR2)", "İSKENDERUN İTHAL KÖMÜR SANTRALI-2", 
            "İSKENDERUN İTHAL KÖMÜR SANTRALI-1", "ATLAS TES", "İÇDAŞ BEKİRLİ 1", "İÇDAŞ BEKİRLİ 2", "İÇDAŞ BİGA TERMİK SANTRALİ_1",
            "İÇDAŞ BİGA TERMİK SANTRALİ_2", "İÇDAŞ BİGA TERMİK SANTRALİ_3", "İZDEMİR ENERJİ", "ÇOLAKOĞLU OP-2 SANTRALİ"
    ],
    'o_ids': [
        603, 603, 603, 603, 603, 18921, 18921, 11033, 11033, 13257, 13257, 7639,
        4831, 4831, 369, 369, 369, 6999, 149
    ],
    'uevcb_ids': [
        18588, 25501, 28365, 3196007, 3196567, 3220150, 3221490, 3200210, 
        3217890, 3208212, 3208213, 1478766, 61976, 1542318, 2728, 4054, 4136, 952237, 3718
    ],
    'capacities': ["2790", "2790", "2790", "2790", "2790", "1320", "1320 ", "1320", "1320", "1308", "1308",
                   "1260", "1260", "1200", " 1200", "1200", "405", "370"],
    'p_ids': []
}

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
    try:
        data = request.json
        selected_date = data.get('date')
        version = data.get('version', 'first')
        
        if not selected_date:
            return jsonify({"code": 400, "error": "Missing 'date' parameter"})

        # Use different URLs based on version
        dpp_url = current_app.config['DPP_FIRST_VERSION_URL'] if version == 'first' else current_app.config['DPP_URL']
        
        # Define hours
        hours = [f"{str(i).zfill(2)}:00" for i in range(24)]

        # Create an empty DataFrame
        df = pd.DataFrame(index=hours, columns=plant_mapping['plant_names'])
        
        # Fetch real data for each plant
        total_plants = len(plant_mapping['plant_names'])
        for idx, (o_id, pl_id, plant_name) in enumerate(zip(
            plant_mapping['o_ids'], 
            plant_mapping['uevcb_ids'], 
            plant_mapping['plant_names']
        )):
            try:
                print(f"Fetching data for plant {idx + 1}/{total_plants}: {plant_name}")
                plant_data = fetch_plant_data(selected_date, o_id, pl_id, dpp_url)
                if plant_data is not None:
                    df[plant_name] = plant_data
                else:
                    df[plant_name] = 0
            except Exception as e:
                print(f"Error fetching data for plant {plant_name}: {str(e)}")
                df[plant_name] = 0

        # Create plant labels with capacities
        plant_labels = [
            f"{name}--{capacity} Mw" 
            for name, capacity in zip(plant_mapping['plant_names'], plant_mapping['capacities'])
        ]

        # Convert DataFrame to JSON response
        response_data = {
            "code": 200,
            "data": {
                "hours": df.index.tolist(),
                "plants": plant_labels,
                "values": df.values.tolist()
            }
        }

        return jsonify(response_data)
    
    except Exception as e:
        print(f"Error in heatmap_data: {str(e)}")
        return jsonify({"code": 500, "error": str(e)})

def get_plant_generation_data(date, o_id, pl_id, dpp_url):
    """
    Fetch generation data for a specific plant and date using DPP endpoint.
    """
    try:
        # Setup session with optimized retries and timeouts
        session = Session()
        retries = Retry(
            total=2,  # Reduced from 3 to 2
            backoff_factor=0.3,  # Reduced from 0.5 to 0.3
            status_forcelist=[500, 502, 503, 504],  # Removed 429 as it's rare
            allowed_methods=["POST"]  # Only allow POST retries
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount('https://', adapter)

        # Get authentication token (consider caching this)
        tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))

        # Format date for API request
        start_date = f"{date}T00:00:00+03:00"
        end_date = f"{date}T23:59:59+03:00"

        # Prepare request data
        request_data = {
            "startDate": start_date,
            "endDate": end_date,
            "region": "TR1",
            "organizationId": str(o_id),
            "uevcbId": str(pl_id)
        }

        # Make API request with reduced timeout
        response = session.post(
            dpp_url,
            json=request_data,
            headers={'TGT': tgt_token},
            timeout=(3, 7)  # Reduced from (5, 15) to (3, 7)
        )
        response.raise_for_status()
        
        # Process response data
        items = response.json().get('items', [])
        
        # Create a dictionary with hour as key and generation value as value
        hourly_data = {}
        for item in items:
            hour = item.get('time', '00:00').split(':')[0]
            total = item.get('toplam', 0)
            hourly_data[f"{hour.zfill(2)}:00"] = total

        # Reduced delay between requests
        time.sleep(0.05)  # Reduced from 0.1 to 0.05
        
        return hourly_data

    except Exception as e:
        print(f"Error in get_plant_generation_data for plant {pl_id}: {str(e)}")
        return None

def fetch_plant_data(date, o_id, pl_id, dpp_url):
    """
    Fetch hourly generation data for a specific plant.
    Optimized retry logic.
    """
    max_retries = 2  # Reduced from 3 to 2
    retry_delay = 0.5  # Reduced from 1 to 0.5
    
    for attempt in range(max_retries):
        try:
            # Get the data from API
            data = get_plant_generation_data(date, o_id, pl_id, dpp_url)
            
            if data is None:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                return [0] * 24
            
            # Process the data to get hourly values
            hourly_values = []
            for hour in range(24):
                hour_str = f"{str(hour).zfill(2)}:00"
                value = data.get(hour_str, 0)
                hourly_values.append(value)
                
            return hourly_values
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed for plant {pl_id}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                print(f"All retries failed for plant {pl_id}")
                return [0] * 24

@main.route('/realtime_heatmap_data', methods=['POST'])
def realtime_heatmap_data():
    try:
        data = request.json
        selected_date = data.get('date')
        
        if not selected_date:
            return jsonify({"code": 400, "error": "Missing 'date' parameter"})

        # Define hours
        hours = [f"{str(i).zfill(2)}:00" for i in range(24)]

        # Create an empty DataFrame
        df = pd.DataFrame(index=hours, columns=plant_mapping['plant_names'])
        
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
        unique_p_ids = set(plant_mapping['p_ids'])
        for p_id in unique_p_ids:
            try:
                print(f"Fetching realtime data for powerplant ID: {p_id}")
                
                request_data = {
                    "startDate": f"{selected_date}T00:00:00+03:00",
                    "endDate": f"{selected_date}T23:59:59+03:00",
                    "powerPlantId": str(p_id)
                }

                # Setup session
                session = Session()
                retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
                session.mount('https://', HTTPAdapter(max_retries=retries))
                
                # Get authentication token
                tgt_token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))

                # Make API request
                response = session.post(
                    current_app.config['REALTIME_URL'],
                    json=request_data,
                    headers={'TGT': tgt_token},
                    timeout=(5, 15)
                )
                response.raise_for_status()
                
                # Process response data
                items = response.json().get('items', [])
                
                # Extract hourly values
                hourly_values = [0] * 24
                for item in items:
                    hour_str = item.get('hour', '00:00')
                    hour = int(hour_str.split(':')[0])
                    total = item.get('total', 0)
                    hourly_values[hour] = total

                # Distribute the values among all instances of this powerplant
                count = p_id_count[p_id]
                distributed_values = [val / count for val in hourly_values]
                
                # Assign the distributed values to all instances of this powerplant
                for idx in p_id_indices[p_id]:
                    plant_name = plant_mapping['plant_names'][idx]
                    df[plant_name] = distributed_values
                
            except Exception as e:
                print(f"Error fetching realtime data for powerplant {p_id}: {str(e)}")
                # Set zero values for all instances of this powerplant
                for idx in p_id_indices[p_id]:
                    plant_name = plant_mapping['plant_names'][idx]
                    df[plant_name] = [0] * 24

        # Create plant labels with capacities
        plant_labels = [
            f"{name}--{capacity} Mw" 
            for name, capacity in zip(plant_mapping['plant_names'], plant_mapping['capacities'])
        ]

        # Convert DataFrame to JSON response
        response_data = {
            "code": 200,
            "data": {
                "hours": df.index.tolist(),
                "plants": plant_labels,
                "values": df.values.tolist()
            }
        }

        return jsonify(response_data)
    
    except Exception as e:
        print(f"Error in realtime_heatmap_data: {str(e)}")
        return jsonify({"code": 500, "error": str(e)})

@main.route('/export_coal_heatmap_data', methods=['POST'])
def export_coal_heatmap_data():
    try:
        data = request.json
        selected_date = data.get('date')
        version = data.get('version', 'first')
        
        if not selected_date:
            return jsonify({"code": 400, "error": "Missing 'date' parameter"})

        # Use different URLs based on version
        dpp_url = current_app.config['DPP_FIRST_VERSION_URL'] if version == 'first' else current_app.config['DPP_URL']
        
        # Define hours
        hours = [f"{str(i).zfill(2)}:00" for i in range(24)]

        # Create an empty DataFrame for export coal plants only
        df = pd.DataFrame(index=hours, columns=export_coal_mapping['plant_names'])
        
        # Fetch data for each export coal plant
        total_plants = len(export_coal_mapping['plant_names'])
        for idx, (o_id, pl_id, plant_name) in enumerate(zip(
            export_coal_mapping['o_ids'], 
            export_coal_mapping['uevcb_ids'], 
            export_coal_mapping['plant_names']
        )):
            try:
                print(f"Fetching data for export coal plant {idx + 1}/{total_plants}: {plant_name}")
                plant_data = fetch_plant_data(selected_date, o_id, pl_id, dpp_url)
                if plant_data is not None:
                    df[plant_name] = plant_data
                else:
                    df[plant_name] = 0
            except Exception as e:
                print(f"Error fetching data for plant {plant_name}: {str(e)}")
                df[plant_name] = 0

        # Create plant labels with capacities
        plant_labels = [
            f"{name}--{capacity} Mw" 
            for name, capacity in zip(export_coal_mapping['plant_names'], export_coal_mapping['capacities'])
        ]

        # Convert DataFrame to JSON response
        response_data = {
            "code": 200,
            "data": {
                "hours": df.index.tolist(),
                "plants": plant_labels,
                "values": df.values.tolist()
            }
        }

        return jsonify(response_data)
    
    except Exception as e:
        print(f"Error in export_coal_heatmap_data: {str(e)}")
        return jsonify({"code": 500, "error": str(e)})
