import requests
import json
from datetime import datetime, timedelta
import threading
from app import create_app
import time
import pytest
import logging

BASE_URL = "http://localhost:5000"

def run_flask_app():
    app = create_app()
    app.run(port=5000)

# Start Flask app in a separate thread
@pytest.fixture(scope="session", autouse=True)
def setup_flask():
    thread = threading.Thread(target=run_flask_app)
    thread.daemon = True
    thread.start()
    # Wait for the server to start
    time.sleep(1)
    yield
    # Cleanup after tests

def test_get_orgs():
    """Test /get_orgs endpoint"""
    url = f"{BASE_URL}/get_orgs"
    payload = {
        "start": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
        "end": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    }
    
    print("\nTesting /get_orgs")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    
    try:
        response.raise_for_status()
        data = response.json()
        if response.status_code == 200:
            print(f"Number of organizations: {len(data['data'])}")
            if data['data']:
                print("Sample organization:")
                print(json.dumps(data['data'][0], indent=2))
        else:
            print("Error:", data)
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTPError: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"Error parsing response: {str(e)}")
    
    print("-" * 50)

def test_get_orgs_uevcbids():
    """Test /get_orgs_uevcbids endpoint"""
    url = f"{BASE_URL}/get_orgs_uevcbids"
    payload = {
        "start": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
        "end": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        "orgIds": ["1", "2"]  # Add some valid organization IDs
    }
    
    print("\nTesting /get_orgs_uevcbids")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    
    try:
        response.raise_for_status()
        data = response.json()
        if response.status_code == 200:
            print("Organizations with UEVCBs:")
            print(json.dumps(data['data'], indent=2))
        else:
            print("Error:", data)
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTPError: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"Error parsing response: {str(e)}")
    
    print("-" * 50)

def test_dpp_table():
    """Test /dpp_table endpoint"""
    url = f"{BASE_URL}/dpp_table"
    payload = {
        "start": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%-d"),
        "end": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        "orgsData": {
            "1": {
                "organizationName": "Test Org",
                "organizationEtsoCode": "TEST",
                "uevcbids": [
                    {"id": "123", "name": "Test UEVCB", "eic": "TEST123"}
                ]
            }
        }
    }
    
    print("\nTesting /dpp_table")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    
    try:
        response.raise_for_status()
        data = response.json()
        if response.status_code == 200:
            print("Columns:", data['data']['columns'])
            print("\nSample data:")
            if data['data']['orgsData']:
                first_org = next(iter(data['data']['orgsData'].values()))
                if first_org['uevcbids'][0]['rows']:
                    print(json.dumps(first_org['uevcbids'][0]['rows'][0], indent=2))
        else:
            print("Error:", data)
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTPError: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"Error parsing response: {str(e)}")
    
    print("-" * 50)

def test_powerplants():
    """Test /powerplants endpoint"""
    url = f"{BASE_URL}/powerplants"
    
    print("\nTesting /powerplants")
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    
    try:
        response.raise_for_status()
        data = response.json()
        if response.status_code == 200:
            print(f"Number of power plants: {len(data['data'])}")
            if data['data']:
                print("Sample power plant:")
                print(json.dumps(data['data'][0], indent=2))
        else:
            print("Error:", data)
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTPError: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"Error parsing response: {str(e)}")
    
    print("-" * 50)

def test_realtime_data():
    """Test /realtime_data endpoint"""
    url = f"{BASE_URL}/realtime_data"
    payload = {
        "powerPlantId": "123",  # Add a valid power plant ID
        "start": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
        "end": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    }
    
    print("\nTesting /realtime_data")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    
    try:
        response.raise_for_status()
        data = response.json()
        if response.status_code == 200:
            print("Columns:", data['columns'])
            if data['data']:
                print("\nSample data:")
                print(json.dumps(data['data'][0], indent=2))
        else:
            print("Error:", data)
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTPError: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"Error parsing response: {str(e)}")
    
    print("-" * 50)

def test_get_aic_data():
    """Test /get_aic_data endpoint"""
    url = f"{BASE_URL}/get_aic_data"
    params = {"range": "week"}
    
    print("\nTesting /get_aic_data")
    print(f"Parameters: {params}")
    
    response = requests.get(url, params=params)
    print(f"Status Code: {response.status_code}")
    
    try:
        response.raise_for_status()
        data = response.json()
        if response.status_code == 200:
            print(f"Number of AIC records: {len(data['data'])}")
            if data['data']:
                print("Sample AIC data:")
                print(json.dumps(data['data'][0], indent=2))
        else:
            print("Error:", data)
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTPError: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"Error parsing response: {str(e)}")
    
    print("-" * 50)

if __name__ == "__main__":
    print("Starting API tests...")
    test_get_orgs()
    test_get_orgs_uevcbids()
    test_dpp_table()
    test_powerplants()
    test_realtime_data()
    test_get_aic_data()
    print("\nAPI tests completed.") 