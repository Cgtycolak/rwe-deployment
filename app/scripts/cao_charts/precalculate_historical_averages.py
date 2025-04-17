import os
import sys
import json
import pandas as pd
import pytz
from datetime import datetime

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(parent_dir)

from app.factory import create_app
from app.database.config import db
from app.models.production import ProductionData

def precalculate_historical_averages():
    app = create_app()
    with app.app_context():
        print("Fetching production data...")
        
        # Get all production data up to the end of 2024
        cutoff_date = datetime(2025, 1, 1)
        data = db.session.query(ProductionData).filter(
            ProductionData.datetime < cutoff_date
        ).order_by(ProductionData.datetime).all()
        
        print(f"Processing {len(data)} historical records...")
        
        # Convert to DataFrame with timezone handling
        df = pd.DataFrame([{
            'datetime': d.datetime.astimezone(pytz.UTC),  # Convert to UTC
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
        } for d in data])
        
        # Convert datetime to pandas datetime with UTC timezone
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        df = df.set_index('datetime')
        
        # Convert to local time (Istanbul)
        istanbul_tz = pytz.timezone('Europe/Istanbul')
        df.index = df.index.tz_convert(istanbul_tz)
        
        # Calculate renewables total and ratio
        df['renewablestotal'] = df['geothermal'] + df['biomass'] + df['wind'] + df['sun']
        df['renewablesratio'] = df['renewablestotal'] / df['total']
        
        # Calculate rolling averages for most columns
        historical_data = {}
        
        # Process regular columns with 7-day rolling averages
        regular_columns = [col for col in df.columns if col != 'renewablesratio']
        for column in regular_columns:
            print(f"Processing {column}...")
            # Resample to daily frequency
            daily_avg = df[column].resample('D', closed='left', label='left').mean()
            rolling_avg = daily_avg.rolling(window=7, min_periods=1).mean()
            
            by_year = {}
            
            # Get all years
            years = rolling_avg.index.year.unique()
            
            # Calculate historical range and average
            historical_range = {}
            for day in range(366):  # Include leap years
                day_values = []
                for year in years:
                    year_data = rolling_avg[rolling_avg.index.year == year]
                    if len(year_data) > day:
                        day_values.append(year_data.iloc[day])
                
                if day_values:
                    historical_range[day] = {
                        'min': float(min(day_values)),
                        'max': float(max(day_values)),
                        'avg': float(sum(day_values) / len(day_values))
                    }
            
            # Store historical range and average
            by_year['historical_range'] = [
                {'min': historical_range[d]['min'], 'max': historical_range[d]['max']}
                if d in historical_range else None
                for d in range(366)
            ]
            by_year['historical_avg'] = [
                round(historical_range[d]['avg'], 2) if d in historical_range else None
                for d in range(366)
            ]
            
            # Add year-specific data
            for year in years:
                year_data = rolling_avg[rolling_avg.index.year == year]
                by_year[str(year)] = [
                    round(float(x), 2) if pd.notnull(x) else None 
                    for x in year_data.values
                ]
            
            historical_data[column] = by_year
        
        # Special handling for renewables ratio - monthly averages
        print("Processing renewables ratio monthly averages...")
        monthly_ratio = {}
        
        # Calculate monthly averages for renewables ratio
        monthly_data = df.groupby([df.index.month, df.index.year])['renewablesratio'].mean()
        
        # Convert to DataFrame for easier manipulation
        monthly_df = pd.DataFrame(monthly_data)
        monthly_df.index.names = ['month', 'year']
        monthly_df.reset_index(inplace=True)
        
        # Get all years for historical data
        years = monthly_df['year'].unique()
        
        # Calculate historical range and average by month
        historical_range = {}
        for month in range(1, 13):
            month_values = []
            for year in years:
                value = monthly_df[(monthly_df['month'] == month) & (monthly_df['year'] == year)]['renewablesratio'].values
                if len(value) > 0:
                    month_values.append(value[0])
            
            if month_values:
                historical_range[month] = {
                    'min': float(min(month_values)),
                    'max': float(max(month_values)),
                    'avg': float(sum(month_values) / len(month_values))
                }
        
        # Store historical range and average
        monthly_ratio['historical_range'] = [
            {'min': historical_range[m]['min'], 'max': historical_range[m]['max']}
            if m in historical_range else None
            for m in range(1, 13)
        ]
        monthly_ratio['historical_avg'] = [
            round(float(historical_range[m]['avg']), 4) if m in historical_range else None
            for m in range(1, 13)
        ]
        
        # Add year-specific data
        for year in years:
            year_data = []
            for month in range(1, 13):
                value = monthly_df[(monthly_df['month'] == month) & (monthly_df['year'] == year)]['renewablesratio'].values
                if len(value) > 0:
                    year_data.append(round(float(value[0]), 4))
                else:
                    year_data.append(None)
            
            monthly_ratio[str(year)] = year_data
        
        # Add monthly renewables ratio to historical data
        historical_data['renewablesratio_monthly'] = monthly_ratio
        
        # Save to JSON file
        output_path = os.path.join(app.static_folder, 'data', 'historical_averages.json')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        print(f"Saving historical data to {output_path}...")
        with open(output_path, 'w') as f:
            json.dump(historical_data, f)
        
        print("Pre-calculation complete!")

if __name__ == "__main__":
    precalculate_historical_averages() 