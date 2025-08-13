#!/usr/bin/env python3
"""
Script to generate historical averages including combined solar data (licensed + unlicensed)
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(parent_dir)

from app.factory import create_app
from app.database.config import db
from app.models.production import ProductionData
from app.models.unlicensed_solar import UnlicensedSolarData
from app.models.licensed_solar import LicensedSolarData

def generate_combined_historical_averages():
    """Generate historical averages with combined solar data (2020-2024)"""
    app = create_app()
    
    with app.app_context():
        print("Generating historical averages with combined solar data (2020-2024)...")
        
        # Define date range for historical data (2020-2024)
        # Start from May 1, 2020 since that's when data is available
        start_date = datetime(2020, 5, 1)  # Changed from 2020-01-01
        end_date = datetime(2024, 12, 31, 23, 59, 59)
        
        print(f"Processing data from {start_date} to {end_date}")
        
        # Query production data
        print("Loading production data...")
        production_query = db.session.query(ProductionData).filter(
            ProductionData.datetime >= start_date,
            ProductionData.datetime <= end_date
        ).order_by(ProductionData.datetime)
        production_data = production_query.all()
        
        # Query unlicensed solar data
        print("Loading unlicensed solar data...")
        unlicensed_query = db.session.query(UnlicensedSolarData).filter(
            UnlicensedSolarData.datetime >= start_date,
            UnlicensedSolarData.datetime <= end_date
        ).order_by(UnlicensedSolarData.datetime)
        unlicensed_data = unlicensed_query.all()
        
        # Query licensed solar data
        print("Loading licensed solar data...")
        licensed_query = db.session.query(LicensedSolarData).filter(
            LicensedSolarData.datetime >= start_date,
            LicensedSolarData.datetime <= end_date
        ).order_by(LicensedSolarData.datetime)
        licensed_data = licensed_query.all()
        
        print(f"Found {len(production_data)} production records")
        print(f"Found {len(unlicensed_data)} unlicensed solar records")
        print(f"Found {len(licensed_data)} licensed solar records")
        
        if not production_data:
            print("No production data found for the specified period!")
            return
        
        # Convert production data to DataFrame
        df_production = pd.DataFrame([{
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
        } for d in production_data])
        
        # Convert datetime and set timezone
        df_production['datetime'] = pd.to_datetime(df_production['datetime'], utc=True)
        df_production = df_production.set_index('datetime')
        
        # Convert to Istanbul timezone
        istanbul_tz = pytz.timezone('Europe/Istanbul')
        df_production.index = df_production.index.tz_convert(istanbul_tz)
        
        # Process unlicensed solar data
        if unlicensed_data:
            df_unlicensed = pd.DataFrame([{
                'datetime': d.datetime.astimezone(pytz.UTC),
                'unlicensed_solar': d.unlicensed_solar
            } for d in unlicensed_data])
            
            df_unlicensed['datetime'] = pd.to_datetime(df_unlicensed['datetime'], utc=True)
            df_unlicensed = df_unlicensed.set_index('datetime')
            df_unlicensed.index = df_unlicensed.index.tz_convert(istanbul_tz)
        else:
            df_unlicensed = pd.DataFrame()
        
        # Process licensed solar data
        if licensed_data:
            df_licensed = pd.DataFrame([{
                'datetime': d.datetime.astimezone(pytz.UTC),
                'licensed_solar': d.licensed_solar
            } for d in licensed_data])
            
            df_licensed['datetime'] = pd.to_datetime(df_licensed['datetime'], utc=True)
            df_licensed = df_licensed.set_index('datetime')
            df_licensed.index = df_licensed.index.tz_convert(istanbul_tz)
        else:
            df_licensed = pd.DataFrame()
        
        # Resample all DataFrames to hourly frequency
        df_hourly = df_production.resample('H', closed='left', label='left').mean()
        
        # Merge solar data
        if not df_unlicensed.empty:
            unlicensed_hourly = df_unlicensed.resample('H', closed='left', label='left').mean()
            df_hourly = df_hourly.join(unlicensed_hourly, how='outer')
            df_hourly['unlicensed_solar'] = df_hourly['unlicensed_solar'].fillna(0)
        else:
            df_hourly['unlicensed_solar'] = 0
        
        if not df_licensed.empty:
            licensed_hourly = df_licensed.resample('H', closed='left', label='left').mean()
            df_hourly = df_hourly.join(licensed_hourly, how='outer')
            df_hourly['licensed_solar'] = df_hourly['licensed_solar'].fillna(0)
        else:
            df_hourly['licensed_solar'] = 0
        
        # Calculate combined solar
        df_hourly['solar_combined'] = df_hourly['unlicensed_solar'] + df_hourly['licensed_solar']
        
        # Filter out any rows with missing production data (this removes the zero-filled periods)
        df_hourly = df_hourly.dropna(subset=['naturalgas', 'wind', 'total'])
        
        # Filter out incomplete days - only keep days with all 24 hours
        print("Filtering out incomplete days...")
        daily_counts = df_hourly.groupby(df_hourly.index.date).size()
        complete_days = daily_counts[daily_counts == 24].index
        
        # Filter the DataFrame to only include complete days
        # Convert dates to strings for comparison to avoid numpy array issues
        complete_days_set = set(complete_days)
        df_hourly = df_hourly[df_hourly.index.map(lambda x: x.date()).isin(complete_days_set)]
        
        print(f"Found {len(complete_days)} complete days out of {len(daily_counts)} total days")
        print(f"Combined DataFrame shape after filtering incomplete days: {df_hourly.shape}")
        print(f"Date range after filtering: {df_hourly.index.min()} to {df_hourly.index.max()}")
        print(f"Sample combined solar values: {df_hourly['solar_combined'].head()}")
        
        # Calculate historical averages and ranges
        historical_data = {}
        
        # Define columns to process
        columns_to_process = [
            'naturalgas', 'lignite', 'wind', 'solar_combined', 'importcoal', 
            'importexport', 'river', 'dammedhydro', 'consumption'
        ]
        
        # Remove consumption for now since we don't have demand data in this scope
        columns_to_process = [col for col in columns_to_process if col != 'consumption']
        
        print("Calculating rolling averages and statistics...")
        
        for column in columns_to_process:
            if column not in df_hourly.columns:
                print(f"Skipping {column} - not found in data")
                continue
            
            print(f"Processing {column}...")
            
            # Calculate daily averages first
            daily_avg = df_hourly[column].resample('D', closed='left', label='left').mean()
            
            # Calculate 7-day rolling averages
            rolling_avg = daily_avg.rolling(window=7, min_periods=1).mean()
            
            # Group by year and day of year for calculations
            rolling_avg_df = rolling_avg.to_frame()
            rolling_avg_df['day_of_year'] = rolling_avg_df.index.dayofyear
            rolling_avg_df['year'] = rolling_avg_df.index.year
            
            # Calculate statistics for each day of year (2020-2024)
            historical_range = []
            historical_avg = []
            
            # Adjust day range based on data availability
            # Since we start from May 1 (day 121 in non-leap years), adjust the range
            for day in range(1, 366):  # 1 to 365 (366 for leap years)
                day_data = rolling_avg_df[rolling_avg_df['day_of_year'] == day][column]
                
                if len(day_data) > 0:
                    # Only use data if we have actual values (not just zeros from missing periods)
                    valid_data = day_data[day_data > 0] if column == 'solar_combined' else day_data
                    
                    if len(valid_data) > 0:
                        min_val = valid_data.min()
                        max_val = valid_data.max()
                        avg_val = valid_data.mean()
                    else:
                        min_val = max_val = avg_val = 0
                    
                    historical_range.append({"min": float(min_val), "max": float(max_val)})
                    historical_avg.append(float(avg_val))
                else:
                    historical_range.append({"min": 0, "max": 0})
                    historical_avg.append(0)
            
            # Store data for this column
            historical_data[column] = {
                "historical_range": historical_range,
                "historical_avg": historical_avg
            }
            
            # Add year-specific data for 2024
            year_2024_data = rolling_avg[rolling_avg.index.year == 2024]
            if not year_2024_data.empty:
                historical_data[column]["2024"] = [
                    round(float(x), 2) if pd.notnull(x) else None 
                    for x in year_2024_data.values
                ]
        
        # Add renewables ratio monthly (special handling)
        if all(col in df_hourly.columns for col in ['geothermal', 'biomass', 'wind', 'total', 'solar_combined']):
            print("Processing renewables ratio...")
            # Use solar_combined instead of sun for renewables calculation
            df_hourly['renewablestotal'] = df_hourly['geothermal'] + df_hourly['biomass'] + df_hourly['wind'] + df_hourly['solar_combined']
            df_hourly['renewablesratio'] = df_hourly['renewablestotal'] / df_hourly['total']
            
            # Monthly renewables ratio - handle the groupby properly
            monthly_grouped = df_hourly.groupby([df_hourly.index.month, df_hourly.index.year])['renewablesratio'].mean()
            
            # Convert to DataFrame without index conflicts
            monthly_data = []
            for (month, year), value in monthly_grouped.items():
                monthly_data.append({'month': month, 'year': year, 'renewablesratio': value})
            
            monthly_df = pd.DataFrame(monthly_data)
            
            # Calculate historical averages for each month (2020-2024)
            monthly_historical = {}
            for month in range(1, 13):
                month_data = monthly_df[monthly_df['month'] == month]['renewablesratio']
                if len(month_data) > 0:
                    monthly_historical[month] = float(month_data.mean())
                else:
                    monthly_historical[month] = 0
            
            # Calculate monthly ranges for 2020-2024
            monthly_ranges = {}
            for month in range(1, 13):
                month_data = monthly_df[monthly_df['month'] == month]['renewablesratio']
                if len(month_data) > 0:
                    monthly_ranges[month] = {
                        "min": float(month_data.min()), 
                        "max": float(month_data.max())
                    }
                else:
                    monthly_ranges[month] = {"min": 0, "max": 0}
            
            historical_data['renewablesratio_monthly'] = {
                "historical_avg": list(monthly_historical.values()),
                "historical_range": list(monthly_ranges.values())
            }
            
            # Add 2024 data
            year_2024_monthly = []
            for month in range(1, 13):
                month_data = monthly_df[(monthly_df['month'] == month) & (monthly_df['year'] == 2024)]['renewablesratio']
                if len(month_data) > 0:
                    year_2024_monthly.append(round(float(month_data.values[0]), 4))
                else:
                    year_2024_monthly.append(None)
            
            historical_data['renewablesratio_monthly']["2024"] = year_2024_monthly
            
            print(f"Sample renewables calculation: geothermal={df_hourly['geothermal'].mean():.2f}, biomass={df_hourly['biomass'].mean():.2f}, wind={df_hourly['wind'].mean():.2f}, solar_combined={df_hourly['solar_combined'].mean():.2f}")
            print(f"Average renewables ratio: {df_hourly['renewablesratio'].mean():.4f}")
            print(f"Monthly ranges sample: {list(monthly_ranges.values())[:3]}")
        
        # Save to a separate JSON file for combined solar data
        output_file = os.path.join(parent_dir, 'app', 'static', 'data', 'historical_averages_combined_solar.json')
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(historical_data, f, indent=2)
        
        print(f"✅ Combined solar historical averages saved to: {output_file}")
        print(f"Processed {len(historical_data)} data series")
        
        return historical_data

def main():
    generate_combined_historical_averages()

if __name__ == "__main__":
    main() 