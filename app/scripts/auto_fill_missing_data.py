import os
import sys
import requests
from datetime import datetime, timedelta

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(parent_dir)

def auto_fill_missing_data(base_url="http://127.0.0.1:5000"):
    print("Checking for missing data...")
    
    # Get missing dates from the check-data-completeness endpoint
    response = requests.get(f"{base_url}/check-data-completeness")
    data = response.json()
    
    missing_dates = data.get('missing_dates', [])
    
    if not missing_dates:
        print("No missing dates found.")
        return
    
    print(f"Found {len(missing_dates)} missing timestamps")
    
    # Group missing dates by day to minimize API calls
    missing_days = {}
    for date_str in missing_dates:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        day_key = date_obj.strftime("%Y-%m-%d")
        
        if day_key not in missing_days:
            missing_days[day_key] = []
        
        missing_days[day_key].append(date_str)
    
    print(f"Grouped into {len(missing_days)} days to update")
    
    # Update each day with missing data
    for day, missing_hours in missing_days.items():
        date_obj = datetime.strptime(day, "%Y-%m-%d")
        start_date = (date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
        
        print(f"Updating data for {day} (range: {start_date} to {end_date})...")
        
        # Call the update-rolling-data endpoint
        update_response = requests.post(
            f"{base_url}/update-rolling-data",
            json={"start_date": start_date, "end_date": end_date}
        )
        
        update_data = update_response.json()
        
        if 'error' in update_data:
            print(f"Error updating {day}: {update_data['error']}")
        else:
            print(f"Successfully updated {day}: {update_data.get('records_added', 0)} records added")
    
    # Verify all gaps are filled
    verify_response = requests.get(f"{base_url}/check-data-completeness")
    verify_data = verify_response.json()
    
    remaining_missing = verify_data.get('missing_dates', [])
    
    if remaining_missing:
        print(f"Warning: {len(remaining_missing)} timestamps still missing.")
        print(remaining_missing)
    else:
        print("All gaps successfully filled!")

if __name__ == "__main__":
    # Use the local development server by default
    # For production, pass the base URL as an argument
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
        auto_fill_missing_data(base_url)
    else:
        auto_fill_missing_data()