import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta
from darts import TimeSeries
from sqlalchemy import create_engine, pool
import os
from dotenv import load_dotenv
import time
import random

# Load environment variables
load_dotenv()

def get_database_connection():
    """Create a database connection using environment variables with better connection pooling."""
    sb_user = os.getenv("SUPABASE_USER")
    sb_password = os.getenv("SUPABASE_PASSWORD")
    
    if not sb_user or not sb_password:
        raise ValueError("Database credentials not found in environment variables")
    
    # Add connection pooling parameters to avoid hitting connection limits
    connection_str = f"postgresql+psycopg2://{sb_user}:{sb_password}@aws-0-us-east-2.pooler.supabase.com:5432/postgres"
    
    # Create engine with connection pooling settings
    engine = create_engine(
        connection_str,
        poolclass=pool.QueuePool,
        pool_size=5,  # Reduce pool size
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,  # Recycle connections after 30 minutes
        pool_pre_ping=True  # Check connection validity before using
    )
    
    return engine

def fetch_with_retry(query, engine, max_retries=3):
    """Fetch data with retry logic to handle connection issues."""
    for attempt in range(max_retries):
        try:
            df = pd.read_sql(query, con=engine)
            return df
        except Exception as e:
            if "max clients reached" in str(e) and attempt < max_retries - 1:
                # Add exponential backoff with jitter
                sleep_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"Database connection limit reached, retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            else:
                raise

def fetch_generation_data(engine):
    """Fetch generation data from the database with retry logic."""
    query = """
    SELECT u."From-yyyy-mm-dd-hh-mm" AS date, w.wind_forecast AS wind,
    d.conventional_forecast + r.runofriver_forecast AS hydro,
    u.unlicensed_forecast + l.licensed_forecast AS solar
    FROM meteologica.unlicensed_solar u
    JOIN meteologica.licensed_solar l ON u."From-yyyy-mm-dd-hh-mm" = l."From-yyyy-mm-dd-hh-mm"
    JOIN meteologica.wind w on u."From-yyyy-mm-dd-hh-mm" = w."From-yyyy-mm-dd-hh-mm"
    JOIN meteologica.dam_hydro d on u."From-yyyy-mm-dd-hh-mm" = d."From-yyyy-mm-dd-hh-mm"
    JOIN meteologica.runofriver_hydro r on u."From-yyyy-mm-dd-hh-mm" = r."From-yyyy-mm-dd-hh-mm"
    WHERE u."From-yyyy-mm-dd-hh-mm" > '2025'
    """
    
    generation_df = fetch_with_retry(query, engine)
    generation_df['date'] = pd.to_datetime(generation_df['date']).dt.tz_localize(None)
    return generation_df

def fetch_dgp_data(engine):
    """Fetch DGP data from the database with retry logic."""
    query = """
    SELECT date, net AS system_direction FROM epias.yal
    WHERE date > '2025'
    """
    
    dgp_df = fetch_with_retry(query, engine)
    dgp_df['date'] = pd.to_datetime(dgp_df['date']).dt.tz_localize(None)
    return dgp_df

def process_excel_data(excel_data):
    """Process uploaded Excel data."""
    # Get current time in Turkey
    turkey_tz = pytz.timezone("Europe/Istanbul")
    now_tr = datetime.now(tz=turkey_tz)
    
    # Get the current hour in Turkey time (0-23)
    current_hour = now_tr.hour
    
    # Set start time to midnight today
    start_time = now_tr.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Create time range from midnight to the current hour (inclusive)
    # This ensures we have data up to the current hour
    time_range = pd.date_range(start=start_time, periods=current_hour+1, freq='h')
    
    # Only use rows in the Excel file up to and including the current hour
    updated_yal_yat = excel_data[excel_data['Saat'] <= current_hour].copy()
    
    # Process the data
    updated_yal_yat['YAT TeslimEdilemeyenMiktar(MWh)'] = updated_yal_yat['YAT TeslimEdilemeyenMiktar(MWh)'].fillna(0)
    updated_yal_yat['YAL TeslimEdilemeyenMiktar(MWh)'] = updated_yal_yat['YAL TeslimEdilemeyenMiktar(MWh)'].fillna(0)
    updated_yal_yat['yal'] = updated_yal_yat['YAL0(MWh)'] + updated_yal_yat['YAL1(MWh)'] - updated_yal_yat['YAL TeslimEdilemeyenMiktar(MWh)']
    updated_yal_yat['yat'] = updated_yal_yat['YAT0(MWh)'] + updated_yal_yat['YAT1(MWh)'] - updated_yal_yat['YAT TeslimEdilemeyenMiktar(MWh)']
    updated_yal_yat['system_direction'] = updated_yal_yat['yal'] - updated_yal_yat['yat']
    
    # Make sure we have exactly the right number of rows
    if len(updated_yal_yat) > len(time_range):
        updated_yal_yat = updated_yal_yat.iloc[:len(time_range)]
    
    # Assign dates to the rows
    updated_yal_yat['date'] = time_range[:len(updated_yal_yat)]
    updated_yal_yat['date'] = pd.to_datetime(updated_yal_yat['date']).dt.tz_localize(None)
    updated_yal_yat = updated_yal_yat[['date','system_direction']]
    updated_yal_yat['system_direction'] = updated_yal_yat['system_direction'].fillna(0)
    
    print(f"Processed Excel data with {len(updated_yal_yat)} rows, last timestamp: {updated_yal_yat['date'].max()}")
    
    return updated_yal_yat

def prepare_data_for_modeling(generation_df, dgp_df, excel_data):
    """Prepare data for modeling by combining database and Excel data."""
    if excel_data is not None:
        updated_yal_yat = process_excel_data(excel_data)
        dgp_df = pd.concat([dgp_df, updated_yal_yat])
    
    df = pd.merge(generation_df, dgp_df, on='date', how='left')
    df.set_index('date', inplace=True)
    
    # Create time series without holidays first
    ts_df = TimeSeries.from_dataframe(df)
    
    # Add holidays with a different name to avoid conflict with Prophet
    ts_df_with_holidays = ts_df.add_holidays('TR')
    df = ts_df_with_holidays.pd_dataframe().rename(columns={'holidays': 'is_holiday'})
    
    df['hour'] = df.index.hour.astype(float)
    hour_map = {hour: 'off-peak1' if hour < 10 else 'peak' if hour >= 18 else 'off-peak2' for hour in range(24)}
    df['is_peak'] = df.index.hour.map(hour_map)
    day_map = {day: 'Sunday' if day == 'Sunday' else 'Saturday' if day == 'Saturday' else 'Weekday' for day in df.index.day_name().unique()}
    df['week_part'] = df.index.day_name().map(day_map)
    df['is_last_week'] = (df.index.day > (df.index.to_period('M').days_in_month - 7)).astype(float)
    df = pd.get_dummies(df, dtype='float')
    df['system_direction_lag1'] = df['system_direction'].shift(1)
    df = df.iloc[1:]
    
    # Convert back to TimeSeries
    ts_df = TimeSeries.from_dataframe(df)
    
    return ts_df 