import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta
from sqlalchemy import create_engine, pool, text
import os
from dotenv import load_dotenv
import time
import random
# darts imported lazily inside functions to reduce per-worker memory on Render

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
            # Use an explicit connection to support both pandas 1.x and SQLAlchemy 2.x
            with engine.connect() as conn:
                df = pd.read_sql(text(query), con=conn)
            return df
        except Exception as e:
            if "max clients reached" in str(e) and attempt < max_retries - 1:
                # Add exponential backoff with jitter
                sleep_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"Database connection limit reached, retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            else:
                raise

CONTEXT_LENGTHS = {"Model 1": 168, "Model 2": 336}

def fetch_generation_data(engine):
    """Fetch generation data (wind/hydro/solar/demand) including future Meteologica forecasts."""
    query = """
    SELECT u."From-yyyy-mm-dd-hh-mm" AS date,
    mdem.demand_forecast AS demand,
    w.wind_forecast AS wind,
    dam.conventional_forecast + r.runofriver_forecast AS hydro,
    u.unlicensed_forecast + l.licensed_forecast AS solar
    FROM meteologica.unlicensed_solar u
    JOIN meteologica.licensed_solar l ON u."From-yyyy-mm-dd-hh-mm" = l."From-yyyy-mm-dd-hh-mm"
    JOIN meteologica.wind w on u."From-yyyy-mm-dd-hh-mm" = w."From-yyyy-mm-dd-hh-mm"
    JOIN meteologica.dam_hydro dam on u."From-yyyy-mm-dd-hh-mm" = dam."From-yyyy-mm-dd-hh-mm"
    JOIN meteologica.runofriver_hydro r on u."From-yyyy-mm-dd-hh-mm" = r."From-yyyy-mm-dd-hh-mm"
    JOIN meteologica.demand mdem on u."From-yyyy-mm-dd-hh-mm" = mdem."From-yyyy-mm-dd-hh-mm"
    WHERE u."From-yyyy-mm-dd-hh-mm" > '2025'
    """

    generation_df = fetch_with_retry(query, engine)
    generation_df['date'] = pd.to_datetime(generation_df['date']).dt.tz_localize(None)
    return generation_df

def fetch_smf_data(engine):
    """Fetch System Marginal Price (SMF) data from the database with retry logic."""
    query = """
    SELECT date, "systemMarginalPrice" FROM epias.smf
    WHERE date >= '2025-01-01'
    """

    smf_df = fetch_with_retry(query, engine)
    smf_df['date'] = pd.to_datetime(smf_df['date']).dt.tz_localize(None)
    return smf_df

def fetch_smf_ptf_data(engine):
    """Fetch combined SMF + PTF data; PTF has future day-ahead prices, SMF is real-time."""
    query = """
    SELECT ptf.date,
           smf."systemMarginalPrice" AS smf,
           ptf.price AS ptf
    FROM epias.ptf
    LEFT JOIN epias.smf ON ptf.date = smf.date
    WHERE ptf.date >= '2025-01-01'
    """

    df = fetch_with_retry(query, engine)
    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
    df['smf_ptf_diff'] = df['smf'] - df['ptf']
    return df

def fetch_ramadan_data(engine):
    """Return the set of Ramadan dates (date-only, normalized) from DB."""
    query = "SELECT date FROM epias.ramadan_dates"
    df = fetch_with_retry(query, engine)
    df['date'] = pd.to_datetime(df['date']).dt.normalize()
    return set(df['date'])

def fetch_dgp_data(engine):
    """Fetch DGP data from the database with retry logic."""
    query = """
    SELECT date, net AS system_direction FROM epias.yal
    WHERE date >= '2025-01-01'
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
    
    # Set start time to midnight today (timezone-naive to avoid pandas tz issues)
    start_time = now_tr.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    
    # Create time range from midnight to the hour BEFORE current hour (exclusive of current hour)
    # This ensures we don't include incomplete data for the current hour
    if current_hour == 0:
        # If it's midnight, we don't have any complete hours today yet
        print("Current hour is 0 (midnight), no complete hours available for today")
        return pd.DataFrame(columns=['date', 'system_direction'])
    
    time_range = pd.date_range(start=start_time, periods=current_hour, freq='h')
    
    # Only use rows in the Excel file up to but NOT including the current hour
    updated_yal_yat = excel_data[excel_data['Saat'] < current_hour].copy()
    
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

def build_chronos_features(engine, excel_data, model_name):
    """Build a fully feature-engineered flat DataFrame for Chronos-2 predict_df.

    Returns a single DataFrame with:
    - All feature columns (demand, wind, hydro, solar, lags, MAs, temporal, etc.)
    - system_direction column: real values for historical rows, NaN for future rows
    - id = 'DF', date column (not index)

    Caller splits into train/covariates based on system_direction nullability.
    """
    ctx_len = CONTEXT_LENGTHS.get(model_name, 168)

    # 1. Fetch data
    generation_df = fetch_generation_data(engine)
    smf_ptf_df    = fetch_smf_ptf_data(engine)
    dgp_df        = fetch_dgp_data(engine)
    ramadan_dates = fetch_ramadan_data(engine)

    # 2. Merge today's Excel data into system_direction
    if excel_data is not None:
        today_df = process_excel_data(excel_data)
        if not today_df.empty:
            dgp_df = (
                pd.concat([dgp_df, today_df])
                .drop_duplicates(subset=['date'], keep='last')
                .sort_values('date')
                .reset_index(drop=True)
            )

    # 3. Merge all sources on date
    df = pd.merge(generation_df, smf_ptf_df, on='date', how='left')
    df = pd.merge(df, dgp_df, on='date', how='left')
    df = df.drop_duplicates(subset=['date'], keep='last').sort_values('date')
    df.set_index('date', inplace=True)

    # 4. Holiday flags using the `holidays` package (no Darts dependency needed)
    import holidays as _holidays_lib
    tr_holidays = _holidays_lib.Turkey(years=sorted(df.index.year.unique().tolist()))
    df['is_holiday'] = df.index.normalize().isin(tr_holidays).astype(float)

    # 5. Ramadan flag
    df['is_ramadan'] = df.index.normalize().isin(ramadan_dates).astype(float)

    # 6. Temporal features
    df['hour'] = df.index.hour.astype(float)
    hour_map = {h: ('off-peak1' if h < 10 else ('peak' if h >= 18 else 'off-peak2')) for h in range(24)}
    df['is_peak'] = df.index.hour.map(hour_map)
    unique_days = df.index.day_name().unique()
    day_map = {d: ('Sunday' if d == 'Sunday' else ('Saturday' if d == 'Saturday' else 'Weekday')) for d in unique_days}
    df['week_part'] = df.index.day_name().map(day_map)
    df = pd.get_dummies(df, dtype='float')

    # 7. Derived demand features
    df['demand_renewable_diff'] = df['demand'] - df['wind'] - df['solar'] - df['hydro']
    df['demand_diff24'] = df['demand'].diff(24)

    # 8. Price lag features
    df['smf_lag24']        = df['smf'].shift(24)
    df['smf_lag168']       = df['smf'].shift(168)
    df['smf_ptf_diff_lag24'] = df['smf_ptf_diff'].shift(24)
    df.drop(columns=['smf', 'smf_ptf_diff', 'ptf'], inplace=True, errors='ignore')

    # 9. System direction lags and rolling averages
    df['system_direction_lag1'] = df['system_direction'].shift(1)
    df['system_direction_ma3']  = df['system_direction'].rolling(3).mean().shift(1)
    df['system_direction_ma6']  = df['system_direction'].rolling(6).mean().shift(1)
    df['system_direction_ma12'] = df['system_direction'].rolling(12).mean().shift(1)
    if model_name == "Model 2":
        df['system_direction_ma2'] = df['system_direction'].rolling(2).mean().shift(1)

    # 10. Drop warmup rows needed for smf_lag168
    df = df.iloc[168:].copy()

    # 11. Flatten: reset index, add id column
    df.reset_index(inplace=True)   # date becomes a column again
    df['id'] = 'DF'

    return df