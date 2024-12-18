import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timedelta
from requests import Session
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry # type: ignore

# Load environment variables
load_dotenv()
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

# Set up session with retries
session = Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

def get_tgt_token(username, password):
    tgt_url = "https://giris.epias.com.tr/cas/v1/tickets"
    headers = {"Accept": "text/plain"}
    response = session.post(tgt_url, data={"username": username, "password": password}, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text.strip()

def fetch_data(url, payload, headers, chunk_start_date, chunk_end_date):
    """Generic function to fetch data from APIs with error handling"""
    max_retries = 3
    retry_delay = 60  # seconds
    
    for attempt in range(max_retries):
        try:
            response = session.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json().get("items", [])
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429 and attempt < max_retries - 1:
                print(f"Rate limit reached. Waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)
                continue
            print(f"Error fetching data for period {chunk_start_date} to {chunk_end_date}: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error: {e}")
            return []
    return []

def main():
    # Get authentication token
    tgt_token = get_tgt_token(username, password)
    headers = {
        "TGT": tgt_token,
        "Content-Type": "application/json"
    }

    # Define date range (from 2020 to now)
    end_date = datetime.now()
    start_date = datetime(2024, 1, 1)

    # Initialize DataFrames to store all data
    all_aic_data = []
    all_consumption_data = []
    all_generation_data = []

    # Process data in 3-month chunks
    current_date = start_date
    while current_date < end_date:
        chunk_end_date = min(current_date + timedelta(days=89), end_date)
        
        # Format dates for API requests
        start_str = current_date.strftime("%Y-%m-%dT00:00:00+03:00")
        end_str = chunk_end_date.strftime("%Y-%m-%dT23:00:00+03:00")

        print(f"Fetching data for period: {start_str} to {end_str}")

        # Fetch AIC data
        aic_url = "https://seffaflik.epias.com.tr/electricity-service/v1/generation/data/aic"
        aic_payload = {
            "startDate": start_str,
            "endDate": end_str,
            "region": "TR1"
        }
        aic_data = fetch_data(aic_url, aic_payload, headers, start_str, end_str)
        all_aic_data.extend(aic_data)

        # Fetch consumption data
        consumption_url = "https://seffaflik.epias.com.tr/electricity-service/v1/consumption/data/realtime-consumption"
        consumption_payload = {
            "startDate": start_str,
            "endDate": end_str
        }
        consumption_data = fetch_data(consumption_url, consumption_payload, headers, start_str, end_str)
        all_consumption_data.extend(consumption_data)

        # Fetch generation data
        generation_url = "https://seffaflik.epias.com.tr/electricity-service/v1/generation/data/realtime-generation"
        generation_payload = {
            "startDate": start_str,
            "endDate": end_str
        }
        generation_data = fetch_data(generation_url, generation_payload, headers, start_str, end_str)
        all_generation_data.extend(generation_data)

        # Move to next chunk
        current_date = chunk_end_date + timedelta(days=1)
        time.sleep(1)  # Delay between chunks to avoid rate limits

    # Convert to DataFrames
    df_aic = pd.DataFrame(all_aic_data)
    df_consumption = pd.DataFrame(all_consumption_data)
    df_generation = pd.DataFrame(all_generation_data)

    # Create Excel writer object
    with pd.ExcelWriter('combined_energy_data.xlsx') as writer:
        df_aic.to_excel(writer, sheet_name='AIC_Data', index=False)
        df_consumption.to_excel(writer, sheet_name='Consumption_Data', index=False)
        df_generation.to_excel(writer, sheet_name='Generation_Data', index=False)

    print("Data has been successfully saved to combined_energy_data.xlsx")

if __name__ == "__main__":
    main() 