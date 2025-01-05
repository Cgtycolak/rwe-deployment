import requests
import json
from datetime import datetime, timedelta
import threading
from app import create_app
import time

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

def test_generation_comparison():
    test_cases = [
        # Valid cases
        {
            "start": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
            "end": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            "expected_status": 200
        },
        {
            "start": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "end": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            "expected_status": 200
        },
        # Error cases
        {
            "start": "invalid-date",
            "end": "2024-03-20",
            "expected_status": 400
        },
        {
            "start": "2024-03-20",
            "end": "2024-03-19",  # end before start
            "expected_status": 400
        },
    ]

    for case in test_cases:
        url = f"{BASE_URL}/api/generation-comparison"
        
        print(f"\nTesting with dates: {case['start']} to {case['end']}")
        response = requests.post(url, json=case)
        
        print(f"Status Code: {response.status_code} (Expected: {case['expected_status']})")
        
        if response.status_code == 200:
            data = response.json()
            print("\nMetadata:")
            print(json.dumps(data['data']['metadata'], indent=2))
            
            print("\nSample differences:")
            if data['data']['differences']['items']:
                print(json.dumps(data['data']['differences']['items'][0], indent=2))
            
            print("\nTotals:")
            print(json.dumps(data['data']['differences']['totals'], indent=2))
        else:
            try:
                error_data = response.json()  # Attempt to decode JSON
            except ValueError:  # Catch JSON decode errors
                error_data = {"error": "Invalid response from server."}
            print("Error:", error_data)
        
        print("-" * 50)

if __name__ == "__main__":
    test_generation_comparison() 