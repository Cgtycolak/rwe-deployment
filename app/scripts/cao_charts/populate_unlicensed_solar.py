#!/usr/bin/env python3
"""
Script to fetch and populate unlicensed solar data from Meteologica API
"""

import os
import sys
import requests
import pandas as pd
import zipfile
import tempfile
from datetime import datetime, timedelta
import pytz
import json # Added for JSON processing

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(parent_dir)

from app.factory import create_app
from app.database.config import db
from app.models.unlicensed_solar import UnlicensedSolarData

def get_meteologica_token():
    """Get authentication token from Meteologica API"""
    username = os.getenv('XTRADERS_USERNAME')
    password = os.getenv('XTRADERS_PASSWORD')
    
    if not username or not password:
        raise ValueError("XTRADERS_USERNAME and XTRADERS_PASSWORD must be set in environment variables")
    
    url = "https://api-markets.meteologica.com/api/v1/login"
    
    data = {
        "user": username,
        "password": password
    }
    
    response = requests.post(url, json=data)
    
    if response.status_code == 200:
        response_data = response.json()
        token = response_data.get("token")
        expiration = response_data.get("expiration_date")
        print(f"Token obtained successfully. Expires: {expiration}")
        return token
    else:
        raise Exception(f"Failed to get token: {response.status_code}, {response.text}")

def fetch_unlicensed_solar_data(token, year, month):
    """Fetch unlicensed solar data for a specific month"""
    url = f"https://api-markets.meteologica.com/api/v1/contents/1430/historical_data/{year}/{month}"
    
    print(f"Fetching from URL: {url}")
    response = requests.get(url, params={"token": token})
    
    print(f"Response status: {response.status_code}")
    print(f"Response headers: {response.headers}")
    
    if response.status_code == 200:
        # Check if response is actually a zip file
        content_type = response.headers.get('content-type', '')
        print(f"Content type: {content_type}")
        
        if 'zip' in content_type or response.content.startswith(b'PK'):
            print(f"Received ZIP file, size: {len(response.content)} bytes")
            return response.content
        else:
            print(f"Response is not a ZIP file. First 200 chars: {response.text[:200]}")
            return None
    else:
        print(f"API request failed: {response.text}")
        return None

def process_zip_data(zip_content, year, month):
    """Process the zip file content and extract hourly data"""
    print(f"Processing ZIP data for {year}-{month}")
    
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
        temp_zip.write(zip_content)
        temp_zip_path = temp_zip.name
    
    try:
        with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
            # List all files in the ZIP
            file_list = zip_ref.namelist()
            print(f"Total files in ZIP: {len(file_list)}")
            
            # Extract JSON files (not CSV)
            json_files = [f for f in file_list if f.endswith('.json')]
            print(f"JSON files found: {len(json_files)}")
            
            if not json_files:
                print("No JSON files found in ZIP")
                return []
            
            all_data = []
            processed_files = 0
            
            for json_file in json_files:
                processed_files += 1
                if processed_files % 100 == 0:  # Print progress every 100 files instead of 10
                    print(f"Processed {processed_files}/{len(json_files)} files...")
                
                with zip_ref.open(json_file) as file:
                    try:
                        # Parse JSON content
                        json_content = file.read().decode('utf-8')
                        json_data = json.loads(json_content)
                        
                        # Only show detailed structure for first few files
                        if processed_files <= 3:
                            print(f"🔍 First data item structure in {json_file}:")
                            if 'data' in json_data and json_data['data']:
                                first_item = json_data['data'][0]
                                print(f"   Keys: {list(first_item.keys())}")
                                print(f" Sample data values from {json_file}:")
                                for key, value in first_item.items():
                                    if key in ['forecast', 'perc10', 'perc90']:
                                        print(f"   {key}: {value}")
                        
                        # Extract solar value
                        solar_value = extract_solar_value_from_json(json_data, json_file)
                        
                        if solar_value is not None:
                            # Extract datetime from filename or JSON data
                            datetime_str = extract_datetime_from_filename(json_file, json_data)
                            if datetime_str:
                                all_data.append({
                                    'datetime': datetime_str,
                                    'unlicensed_solar': solar_value
                                })
                        
                    except Exception as e:
                        print(f"❌ Error processing {json_file}: {e}")
                        continue
            
            print(f"Total data points extracted: {len(all_data)}")
            return all_data
    finally:
        # Clean up temporary file
        os.unlink(temp_zip_path)

def extract_solar_value_from_json(json_data, filename):
    """Extract solar value from JSON data"""
    try:
        # Check if we have the expected structure
        if 'data' not in json_data or not json_data['data']:
            return None
        
        # Get the first data item (they all seem to have the same structure)
        first_item = json_data['data'][0]
        
        # Look for the actual solar power value
        # Based on the output, we have 'forecast', 'perc10', 'perc90' keys
        # The 'forecast' value should be the main solar power value
        if 'forecast' in first_item:
            forecast_value = first_item['forecast']
            if forecast_value is not None and forecast_value != '':
                try:
                    # Convert to float and return
                    return float(forecast_value)
                except (ValueError, TypeError):
                    pass
        
        # If forecast is not available, try perc10 or perc90 as fallback
        for key in ['perc10', 'perc90']:
            if key in first_item:
                value = first_item[key]
                if value is not None and value != '':
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        continue
        
        # If we still don't have a value, let's see what's actually in the data
        print(f"🔍 No solar value found in {filename}")
        print(f"   Available keys: {list(first_item.keys())}")
        print(f"   Sample values: {first_item}")
        
        return None
        
    except Exception as e:
        print(f"❌ Error extracting solar value from {filename}: {e}")
        return None

def extract_datetime_from_filename(filename, json_data):
    """Extract datetime from filename or JSON data"""
    try:
        # First try to get datetime from JSON data
        if 'data' in json_data and json_data['data']:
            first_item = json_data['data'][0]
            
            # Look for datetime fields
            for key in ['From yyyy-mm-dd hh:mm', 'To yyyy-mm-dd hh:mm']:
                if key in first_item:
                    datetime_str = first_item[key]
                    if datetime_str:
                        # Parse the datetime string
                        try:
                            # The format appears to be "2025-01-27 14:13"
                            dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
                            # Convert to ISO format with timezone
                            return dt.strftime('%Y-%m-%dT%H:%M:%S+03:00')
                        except ValueError:
                            continue
        
        # If no datetime in JSON, try to extract from filename
        # Filename format: 1430_202501271413.json
        if '_' in filename and '.json' in filename:
            parts = filename.split('_')
            if len(parts) >= 2:
                date_part = parts[1].replace('.json', '')
                if len(date_part) >= 12:  # Should be at least 12 characters
                    try:
                        # Parse: 202501271413 -> 2025-01-27 14:13
                        year = date_part[:4]
                        month = date_part[4:6]
                        day = date_part[6:8]
                        hour = date_part[8:10]
                        minute = date_part[10:12]
                        
                        dt = datetime(int(year), int(month), int(day), int(hour), int(minute))
                        return dt.strftime('%Y-%m-%dT%H:%M:%S+03:00')
                    except ValueError:
                        pass
        
        print(f"⚠️ Could not extract datetime from {filename}")
        return None
        
    except Exception as e:
        print(f"❌ Error extracting datetime from {filename}: {e}")
        return None

def populate_unlicensed_solar_data(start_date, end_date):
    """Populate unlicensed solar data for a date range"""
    app = create_app()
    
    with app.app_context():
        print(f"Populating unlicensed solar data from {start_date} to {end_date}")
        
        # Get token
        token = get_meteologica_token()
        
        # Process each month in the range
        current_date = start_date
        total_records = 0
        
        while current_date <= end_date:
            year = current_date.year
            month = current_date.month
            
            print(f"Processing {year}-{month:02d}")
            
            try:
                # Fetch data for this month
                zip_content = fetch_unlicensed_solar_data(token, year, month)
                
                if zip_content:
                    # Process the zip data
                    monthly_data = process_zip_data(zip_content, year, month)
                    
                    if monthly_data:
                        # Insert or update unlicensed solar data
                        updated_count = 0
                        for data_point in monthly_data:
                            try:
                                # Parse datetime string to datetime object
                                dt_str = data_point['datetime']
                                if isinstance(dt_str, str):
                                    # Remove timezone info for parsing
                                    dt_str_clean = dt_str.split('+')[0].replace('T', ' ')
                                    dt_obj = datetime.strptime(dt_str_clean, '%Y-%m-%d %H:%M:%S')
                                else:
                                    dt_obj = dt_str
                                
                                # Check if record already exists
                                existing_record = UnlicensedSolarData.query.filter(
                                    UnlicensedSolarData.datetime == dt_obj
                                ).first()
                                
                                if existing_record:
                                    # Update existing record
                                    existing_record.unlicensed_solar = data_point['unlicensed_solar']
                                    existing_record.updated_at = datetime.utcnow()
                                    updated_count += 1
                                else:
                                    # Create new record
                                    new_record = UnlicensedSolarData(
                                        datetime=dt_obj,
                                        unlicensed_solar=data_point['unlicensed_solar']
                                    )
                                    db.session.add(new_record)
                                    updated_count += 1
                                
                            except Exception as e:
                                print(f"Error processing data point {data_point['datetime']}: {e}")
                                continue
                        
                        # Commit the changes for this month
                        db.session.commit()
                        print(f"✅ {year}-{month:02d}: {updated_count} records processed")
                        total_records += updated_count
                    else:
                        print(f"⚠️ No data found for {year}-{month:02d}")
                else:
                    print(f"❌ Failed to fetch data for {year}-{month:02d}")
                
            except Exception as e:
                print(f"❌ Error processing {year}-{month:02d}: {e}")
                db.session.rollback()
                continue
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        print(f"🎉 Total records processed: {total_records}")
        return total_records

def main():
    # Set date range from 2020 to current date  
    start_date = datetime(2020, 1, 1).date()
    end_date = datetime.now().date()
    
    populate_unlicensed_solar_data(start_date, end_date)

if __name__ == "__main__":
    main() 