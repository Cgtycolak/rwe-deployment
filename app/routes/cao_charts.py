"""CAO Charts tab: rolling averages of production, demand and solar."""
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, current_app
from ..functions import login_required
import pandas as pd
import pytz
from ..database.config import db
import json
from ..models.production import ProductionData
from sqlalchemy import text
import os
from ..models.demand import DemandData
from ..models.unlicensed_solar import UnlicensedSolarData
from ..models.licensed_solar import LicensedSolarData
from .common import api_error

cao_charts_bp = Blueprint('cao_charts', __name__)


@cao_charts_bp.route('/get-rolling-data')
@login_required
def get_rolling_data():
    try:
        # Load the original historical data (2016-2025) as the base
        historical_file = os.path.join(current_app.static_folder, 'data', 'historical_averages.json')
        
        if os.path.exists(historical_file):
            current_app.logger.debug("Loading original historical data (2016-2025) as base")
            with open(historical_file, 'r') as f:
                historical_data = json.load(f)
            
            # Set base metadata for 2016-2025 data
            historical_data['_metadata'] = {
                'data_source': 'original',
                'date_range': '2016-2025',
                'uses_combined_solar': False
            }
        else:
            historical_data = {}
            historical_data['_metadata'] = {
                'data_source': 'none',
                'date_range': '2016-2025',
                'uses_combined_solar': False
            }

        # Now load the combined solar data and override only the solar_combined entry
        combined_solar_file = os.path.join(current_app.static_folder, 'data', 'historical_averages_combined_solar.json')
        
        if os.path.exists(combined_solar_file):
            current_app.logger.debug("Loading combined solar historical data (2020-2025) for solar_combined chart")
            with open(combined_solar_file, 'r') as f:
                combined_solar_data = json.load(f)
            
            # Only override the solar_combined data, keep everything else from original file
            if 'solar_combined' in combined_solar_data:
                historical_data['solar_combined'] = combined_solar_data['solar_combined']
                
            # Also override renewables ratio since it now uses combined solar data
            if 'renewablesratio_monthly' in combined_solar_data:
                historical_data['renewablesratio_monthly'] = combined_solar_data['renewablesratio_monthly']
                
            # Add special metadata for solar_combined to indicate it uses 2020-2025 data
            historical_data['_solar_combined_metadata'] = {
                'date_range': '2020-2025',
                'uses_combined_solar': True
            }
            
            current_app.logger.debug("Successfully merged combined solar data with original historical data")
        else:
            current_app.logger.debug("Combined solar historical data file not found")

        # Get current year data (2026 and beyond)
        current_year = datetime.now().year
        cutoff_date = datetime(current_year, 1, 1)
        
        # Query production data (excluding solar since we'll use separate tables)
        production_query = db.session.query(ProductionData).filter(
            ProductionData.datetime >= cutoff_date
        ).order_by(ProductionData.datetime)
        
        # Query unlicensed solar data
        unlicensed_query = db.session.query(UnlicensedSolarData).filter(
            UnlicensedSolarData.datetime >= cutoff_date
        ).order_by(UnlicensedSolarData.datetime)
        
        # Query licensed solar data
        licensed_query = db.session.query(LicensedSolarData).filter(
            LicensedSolarData.datetime >= cutoff_date
        ).order_by(LicensedSolarData.datetime)
        
        current_data = production_query.all()
        unlicensed_data = unlicensed_query.all()
        licensed_data = licensed_query.all()
        
        current_app.logger.debug(f"Found {len(current_data)} production records, {len(unlicensed_data)} unlicensed solar records, and {len(licensed_data)} licensed solar records")
        
        if current_data:
            current_app.logger.debug(f"Processing {len(current_data)} current year records")
            
            # Convert to DataFrame with timezone handling
            df = pd.DataFrame([{
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
                'sun': d.sun,  # Keep this for renewables calculation
                'importexport': d.importexport,
                'total': d.total,
                'wasteheat': d.wasteheat
            } for d in current_data])
            
            # Convert datetime to pandas datetime with UTC timezone
            df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
            df = df.set_index('datetime')
            
            # Ensure timezone is set before conversion
            if df.index.tz is None:
                current_app.logger.warning("Warning: DataFrame index has no timezone, localizing to UTC")
                df.index = df.index.tz_localize('UTC')
            
            # Convert to Istanbul timezone using string instead of pytz object
            df.index = df.index.tz_convert('Europe/Istanbul')
            
            # Process solar data from separate tables first
            if unlicensed_data or licensed_data:
                current_app.logger.debug(f"Processing {len(unlicensed_data)} unlicensed and {len(licensed_data)} licensed solar records")
                
                # Create unlicensed solar DataFrame
                if unlicensed_data:
                    unlicensed_df = pd.DataFrame([{
                        'datetime': d.datetime.astimezone(pytz.UTC),
                        'unlicensed_solar': d.unlicensed_solar
                    } for d in unlicensed_data])
                    
                    unlicensed_df['datetime'] = pd.to_datetime(unlicensed_df['datetime'], utc=True)
                    unlicensed_df = unlicensed_df.set_index('datetime')
                    if unlicensed_df.index.tz is None:
                        unlicensed_df.index = unlicensed_df.index.tz_localize('UTC')
                    unlicensed_df.index = unlicensed_df.index.tz_convert('Europe/Istanbul')
                else:
                    unlicensed_df = pd.DataFrame(columns=['unlicensed_solar'])
                    unlicensed_df.index = pd.DatetimeIndex([])
                
                # Create licensed solar DataFrame
                if licensed_data:
                    licensed_df = pd.DataFrame([{
                        'datetime': d.datetime.astimezone(pytz.UTC),
                        'licensed_solar': d.licensed_solar
                    } for d in licensed_data])
                    
                    licensed_df['datetime'] = pd.to_datetime(licensed_df['datetime'], utc=True)
                    licensed_df = licensed_df.set_index('datetime')
                    if licensed_df.index.tz is None:
                        licensed_df.index = licensed_df.index.tz_localize('UTC')
                    licensed_df.index = licensed_df.index.tz_convert('Europe/Istanbul')
                else:
                    licensed_df = pd.DataFrame(columns=['licensed_solar'])
                    licensed_df.index = pd.DatetimeIndex([])
                
                current_app.logger.debug(f"Unlicensed solar data range: {unlicensed_df.index.min() if not unlicensed_df.empty else 'None'} to {unlicensed_df.index.max() if not unlicensed_df.empty else 'None'}")
                current_app.logger.debug(f"Licensed solar data range: {licensed_df.index.min() if not licensed_df.empty else 'None'} to {licensed_df.index.max() if not licensed_df.empty else 'None'}")
                current_app.logger.debug(f"Production data range: {df.index.min()} to {df.index.max()}")
                
                # Resample all DataFrames to hourly frequency to align timestamps
                df_hourly = df.resample('h', closed='left', label='left').mean()
                unlicensed_hourly = unlicensed_df.resample('h', closed='left', label='left').mean() if not unlicensed_df.empty else pd.DataFrame()
                licensed_hourly = licensed_df.resample('h', closed='left', label='left').mean() if not licensed_df.empty else pd.DataFrame()
                
                current_app.logger.debug(f"After resampling - Production shape: {df_hourly.shape}")
                if not unlicensed_hourly.empty:
                    current_app.logger.debug(f"Unlicensed shape: {unlicensed_hourly.shape}")
                if not licensed_hourly.empty:
                    current_app.logger.debug(f"Licensed shape: {licensed_hourly.shape}")
                
                # Merge all DataFrames
                if not unlicensed_hourly.empty:
                    df_hourly = df_hourly.join(unlicensed_hourly, how='outer')
                    df_hourly['unlicensed_solar'] = df_hourly['unlicensed_solar'].fillna(0)
                else:
                    df_hourly['unlicensed_solar'] = 0
                
                if not licensed_hourly.empty:
                    df_hourly = df_hourly.join(licensed_hourly, how='outer')
                    df_hourly['licensed_solar'] = df_hourly['licensed_solar'].fillna(0)
                else:
                    df_hourly['licensed_solar'] = 0
                
                # Calculate combined solar (unlicensed + licensed)
                df_hourly['solar_combined'] = df_hourly['unlicensed_solar'] + df_hourly['licensed_solar']
                
                # Build completeness sets per-series so solar-derived series can lag without
                # forcing other series to drop the latest day
                current_app.logger.debug("Computing completeness per series (production vs solar)...")
                today = datetime.now().date()
                
                # Production completeness (use overall index)
                prod_counts_by_day = df_hourly.groupby(df_hourly.index.date).size()
                prod_complete_days = [d for d, c in prod_counts_by_day.items() if c == 24 and d != today]
                
                # Solar completeness (require 24 points in both unlicensed and licensed if they exist)
                solar_complete_days = None
                if not unlicensed_hourly.empty:
                    unl_counts = unlicensed_hourly.groupby(unlicensed_hourly.index.date).size()
                    unl_complete = set([d for d, c in unl_counts.items() if c == 24 and d != today])
                else:
                    unl_complete = set()
                if not licensed_hourly.empty:
                    lic_counts = licensed_hourly.groupby(licensed_hourly.index.date).size()
                    lic_complete = set([d for d, c in lic_counts.items() if c == 24 and d != today])
                else:
                    lic_complete = set()
                
                if not unlicensed_hourly.empty and not licensed_hourly.empty:
                    solar_complete_days = unl_complete.intersection(lic_complete)
                elif not unlicensed_hourly.empty:
                    solar_complete_days = unl_complete
                elif not licensed_hourly.empty:
                    solar_complete_days = lic_complete
                else:
                    # No separate solar sources → treat as production completeness
                    solar_complete_days = set(prod_complete_days)
                
                current_app.logger.debug(f"Production complete days: {len(prod_complete_days)} | Solar complete days: {len(solar_complete_days)}")
                
                # Do not filter df_hourly globally anymore; we will apply these day sets per-series
                # when constructing outputs to avoid unintended drops.
                
                current_app.logger.debug(f"Sample unlicensed solar values: {df_hourly['unlicensed_solar'].head()}")
                current_app.logger.debug(f"Sample licensed solar values: {df_hourly['licensed_solar'].head()}")
                current_app.logger.debug(f"Sample combined solar values: {df_hourly['solar_combined'].head()}")
                
                # Use the hourly DataFrame for further processing without global trimming
                df = df_hourly
            else:
                # No solar data from separate tables, set to 0
                df['unlicensed_solar'] = 0
                df['licensed_solar'] = 0
                df['solar_combined'] = 0
                current_app.logger.debug("No separate solar data found, setting all solar values to 0")
            
            # Calculate renewables total and ratio (using combined solar data) - AFTER solar processing
            df['renewablestotal'] = df['geothermal'] + df['biomass'] + df['wind'] + df['solar_combined']
            df['renewablesratio'] = df['renewablestotal'] / df['total']
            
            # Calculate rolling averages for current year
            rolling_data = historical_data.copy() if historical_data else {}
            
            # Process regular columns with 7-day rolling averages
            regular_columns = [col for col in df.columns if col not in ['renewablesratio', 'solar_combined']]
            regular_columns.append('solar_combined')  # Add combined solar data
            for column in regular_columns:
                # For solar columns, only average daytime hours (07:00-18:00)
                # to avoid diluting the average with zero-generation night hours
                if column in ['solar_combined', 'unlicensed_solar', 'licensed_solar', 'sun']:
                    col_series = df[df.index.hour.isin(range(7, 19))][column]
                    daily_avg = col_series.resample('d', closed='left', label='left').mean()
                    daily_avg = daily_avg[daily_avg.index.map(lambda x: x.date() in solar_complete_days)]
                else:
                    daily_avg = df[column].resample('d', closed='left', label='left').mean()
                    daily_avg = daily_avg[daily_avg.index.map(lambda x: x.date() in set(prod_complete_days))]
                rolling_avg = daily_avg.rolling(window=7, min_periods=1).mean()
                
                # Get current year data
                year_data = rolling_avg[rolling_avg.index.year == current_year]
                
                # Create or update column data
                if column not in rolling_data:
                    rolling_data[column] = {}
                
                # Add current year data
                rolling_data[column][str(current_year)] = [
                    round(float(x), 2) if pd.notnull(x) else None 
                    for x in year_data.values
                ]
            
            # Special handling for renewables ratio - monthly averages for current year
            if 'renewablesratio' in df.columns:
                # For renewables ratio, restrict to solar-complete days to avoid sharp drops
                df_ratio = df[df.index.map(lambda x: x.date() in solar_complete_days)]
                monthly_data = df_ratio.groupby([df_ratio.index.month, df_ratio.index.year])['renewablesratio'].mean()
            
            # Convert to DataFrame for easier manipulation
            monthly_df = pd.DataFrame(monthly_data)
            monthly_df.index.names = ['month', 'year']
            monthly_df.reset_index(inplace=True)
            
            # Create or update renewablesratio_monthly
            if 'renewablesratio_monthly' not in rolling_data:
                rolling_data['renewablesratio_monthly'] = {}
            
            # Add current year data
            year_data = []
            for month in range(1, 13):
                value = monthly_df[(monthly_df['month'] == month) & (monthly_df['year'] == current_year)]['renewablesratio'].values
                if len(value) > 0:
                    year_data.append(round(float(value[0]), 4))
                else:
                    year_data.append(None)
            
            rolling_data['renewablesratio_monthly'][str(current_year)] = year_data
                
            current_app.logger.debug(f"Sample renewables data for current year: {df['renewablesratio'].mean():.4f}")
            
            # Add this after calculating solar_combined
            current_app.logger.debug(f"Sample solar data - Licensed: {df['licensed_solar'].iloc[0] if len(df) > 0 else 'No data'}, Unlicensed: {df['unlicensed_solar'].iloc[0] if len(df) > 0 else 'No data'}, Combined: {df['solar_combined'].iloc[0] if len(df) > 0 else 'No data'}")
            
            return jsonify(rolling_data)
        else:
            # If no current year data, just return historical data
            return jsonify(historical_data)
        
    except Exception as e:
        return api_error("get_rolling_data", e)


@cao_charts_bp.route('/get-rolling-last-update')
@login_required
def get_rolling_last_update():
    """Latest stored hour of each CAO dataset, as Istanbul wall-clock ISO strings."""
    try:
        def latest(model):
            return db.session.query(db.func.max(model.datetime)).scalar()

        production, demand, solar = latest(ProductionData), latest(DemandData), latest(UnlicensedSolarData)
        istanbul_tz = pytz.timezone('Europe/Istanbul')
        # production_data and demand_data hold naive Istanbul time; the solar tables hold UTC
        if solar is not None:
            solar = (solar if solar.tzinfo else solar.replace(tzinfo=pytz.UTC)).astimezone(istanbul_tz).replace(tzinfo=None)
        fmt = lambda dt: dt.strftime('%Y-%m-%dT%H:%M') if dt else None
        return jsonify({'production': fmt(production), 'demand': fmt(demand), 'solar': fmt(solar)})

    except Exception as e:
        return api_error("get_rolling_last_update", e)


@cao_charts_bp.route('/get-solar-weekly-data')
@login_required
def get_solar_weekly_data():
    try:
        import datetime as dt_module
        istanbul_tz = pytz.timezone('Europe/Istanbul')

        latest_solar = db.session.query(UnlicensedSolarData.datetime).order_by(UnlicensedSolarData.datetime.desc()).first()
        if not latest_solar:
            return jsonify({'error': 'No solar data found'}), 404

        latest_dt = latest_solar[0].replace(tzinfo=pytz.UTC).astimezone(istanbul_tz)
        end_date = latest_dt.date()
        start_date = end_date - timedelta(days=6)

        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=6)

        ly_start = start_date - timedelta(days=365)
        ly_end = end_date - timedelta(days=365)

        def _utc_bounds(date_from, date_to):
            from_utc = datetime(date_from.year, date_from.month, date_from.day,
                                tzinfo=istanbul_tz).astimezone(pytz.UTC)
            to_utc   = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59,
                                tzinfo=istanbul_tz).astimezone(pytz.UTC)
            return from_utc, to_utc

        def _solar_from_rows(rows_unl, rows_lic):
            unl_map, lic_map = {}, {}
            for r in rows_unl:
                key = r.datetime.replace(tzinfo=pytz.UTC).astimezone(istanbul_tz).replace(
                    minute=0, second=0, microsecond=0)
                unl_map[key] = unl_map.get(key, 0) + (r.unlicensed_solar or 0)
            for r in rows_lic:
                key = r.datetime.replace(tzinfo=pytz.UTC).astimezone(istanbul_tz).replace(
                    minute=0, second=0, microsecond=0)
                lic_map[key] = lic_map.get(key, 0) + (r.licensed_solar or 0)
            all_keys = sorted(set(unl_map) | set(lic_map))
            labels = [k.strftime('%a %d %b %H:%M') for k in all_keys]
            values = [round(unl_map.get(k, 0) + lic_map.get(k, 0), 1) for k in all_keys]
            return labels, values

        def smooth(values, window=5):
            if not values:
                return values
            return pd.Series(values).rolling(window=window, center=True, min_periods=1).mean().round(1).tolist()

        # Build all date ranges we need at once
        week_number = start_date.isocalendar()[1]
        hist_ranges = []
        for year in range(2020, 2026):
            try:
                hist_ranges.append((
                    dt_module.date.fromisocalendar(year, week_number, 1),
                    dt_module.date.fromisocalendar(year, week_number, 7),
                ))
            except (ValueError, AttributeError):
                pass

        named_ranges = [
            ('cur',  start_date,  end_date),
            ('prev', prev_start,  prev_end),
            ('ly',   ly_start,    ly_end),
        ] + [('hist', hs, he) for hs, he in hist_ranges]

        # Two queries total — one per solar table — covering all ranges via OR
        def _fetch_solar_table(model_cls, field):
            clauses, params = [], {}
            for i, (_, d_from, d_to) in enumerate(named_ranges):
                f, t = _utc_bounds(d_from, d_to)
                clauses.append(f"(datetime >= :f{i} AND datetime <= :t{i})")
                params[f'f{i}'] = f
                params[f't{i}'] = t
            return db.session.query(model_cls).filter(
                db.or_(*[db.text(c) for c in clauses])
            ).params(**params).order_by(model_cls.datetime).all()

        all_unl = _fetch_solar_table(UnlicensedSolarData, 'unlicensed_solar')
        all_lic = _fetch_solar_table(LicensedSolarData,   'licensed_solar')

        def _subset(rows, attr, d_from, d_to):
            f, t = _utc_bounds(d_from, d_to)
            return [r for r in rows if f <= r.datetime <= t]

        cur_labels,  cur_values  = _solar_from_rows(
            _subset(all_unl, None, start_date, end_date),
            _subset(all_lic, None, start_date, end_date))
        prev_labels, prev_values = _solar_from_rows(
            _subset(all_unl, None, prev_start, prev_end),
            _subset(all_lic, None, prev_start, prev_end))
        ly_labels,   ly_values   = _solar_from_rows(
            _subset(all_unl, None, ly_start, ly_end),
            _subset(all_lic, None, ly_start, ly_end))

        all_hist = []
        for hs, he in hist_ranges:
            _, h_vals = _solar_from_rows(
                _subset(all_unl, None, hs, he),
                _subset(all_lic, None, hs, he))
            if h_vals and len(h_vals) >= 100:
                all_hist.append(smooth(h_vals, window=5))

        max_len = max((len(v) for v in all_hist), default=0)
        hist_min, hist_max, hist_avg = [], [], []
        for i in range(max_len):
            vals = [v[i] for v in all_hist if i < len(v)]
            if vals:
                hist_min.append(round(min(vals), 1))
                hist_max.append(round(max(vals), 1))
                hist_avg.append(round(sum(vals) / len(vals), 1))
            else:
                hist_min.append(None)
                hist_max.append(None)
                hist_avg.append(None)

        return jsonify({
            'current_week': {'labels': cur_labels, 'values': smooth(cur_values),
                             'range': f"{start_date} – {end_date}"},
            'previous_week': {'labels': prev_labels, 'values': smooth(prev_values),
                              'range': f"{prev_start} – {prev_end}"},
            'last_year': {'labels': ly_labels, 'values': smooth(ly_values),
                          'range': f"{ly_start} – {ly_end}"},
            'historical_range': {'min': hist_min, 'max': hist_max, 'avg': hist_avg,
                                 'years': '2020-2025'}
        })

    except Exception as e:
        return api_error("get_solar_weekly_data", e)


@cao_charts_bp.route('/get_demand_data')
@login_required
def get_demand_data():
    try:
        current_year = datetime.now().year  # 2026
        previous_year = current_year - 1    # 2025
        
        # Get current date to limit the data range
        current_date = datetime.now()
        
        # Use raw SQL to avoid ORM issues with missing columns
        query = text("""
            SELECT id, datetime, consumption 
            FROM demand_data
            WHERE (EXTRACT(year FROM datetime) = :current_year AND datetime <= :current_date)
               OR (EXTRACT(year FROM datetime) = :previous_year)
            ORDER BY datetime
        """)
        
        # Execute query
        result = db.session.execute(
            query, 
            {
                "current_year": current_year, 
                "current_date": current_date,
                "previous_year": previous_year
            }
        ).fetchall()
        
        # Process the data for the frontend
        current_year_data = []
        previous_year_data = []
        
        for row in result:
            data_point = {
                "datetime": row.datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "consumption": float(row.consumption)
            }
            
            if row.datetime.year == current_year:
                current_year_data.append(data_point)
            else:
                previous_year_data.append(data_point)
        
        # Convert to pandas DataFrame for resampling and metrics
        if current_year_data:
            df_current = pd.DataFrame(current_year_data)
            df_current['datetime'] = pd.to_datetime(df_current['datetime'])
            df_current.set_index('datetime', inplace=True)
            weekly_avg_current = df_current.resample('w').mean()
        else:
            weekly_avg_current = pd.DataFrame()
            
        if previous_year_data:
            df_previous = pd.DataFrame(previous_year_data)
            df_previous['datetime'] = pd.to_datetime(df_previous['datetime'])
            df_previous.set_index('datetime', inplace=True)
            weekly_avg_previous = df_previous.resample('w').mean()
        else:
            weekly_avg_previous = pd.DataFrame()
        
        # Calculate MTD/YTD metrics (average consumption), comparing to same period last year
        # IMPORTANT: EPİAŞ has 4-hour data lag, so we must compare like-for-like periods
        metrics = {}
        try:
            now = pd.to_datetime(current_date)
            # Use the actual last timestamp from database instead of assuming 4-hour lag
            # This handles cases where data might be delayed more than 4 hours
            if current_year_data:
                data_available_until = df_current.index.max()
            else:
                # Fallback to 4-hour lag if no current year data
                data_available_until = now - pd.Timedelta(hours=4)
            
            # Month-to-date masks (both years compare to data_available_until)
            if current_year_data:
                mtd_start = data_available_until.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                df_cur_mtd = df_current.loc[(df_current.index >= mtd_start) & (df_current.index <= data_available_until)]
            else:
                df_cur_mtd = pd.DataFrame(columns=['consumption'])

            if previous_year_data:
                # Use same hour-of-day for previous year comparison
                prev_data_available = data_available_until.replace(year=previous_year)
                mtd_start_prev = prev_data_available.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                df_prev_mtd = df_previous.loc[(df_previous.index >= mtd_start_prev) & (df_previous.index <= prev_data_available)]
            else:
                df_prev_mtd = pd.DataFrame(columns=['consumption'])

            # Year-to-date masks (both years compare to data_available_until at same hour)
            # IMPORTANT: Handle leap years - if comparing across leap year boundary, skip Feb 29
            if current_year_data:
                ytd_start = data_available_until.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                df_cur_ytd = df_current.loc[(df_current.index >= ytd_start) & (df_current.index <= data_available_until)]
            else:
                df_cur_ytd = pd.DataFrame(columns=['consumption'])

            if previous_year_data:
                # Compare to same hour last year (accounting for 4-hour lag)
                prev_ytd_end = data_available_until.replace(year=previous_year)
                ytd_start_prev = prev_ytd_end.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                df_prev_ytd = df_previous.loc[(df_previous.index >= ytd_start_prev) & (df_previous.index <= prev_ytd_end)]
                
                # Handle leap year: if previous year was leap year and current is not (or vice versa),
                # exclude Feb 29 from the leap year to ensure fair comparison
                import calendar
                prev_is_leap = calendar.isleap(previous_year)
                curr_is_leap = calendar.isleap(current_year)
                
                if prev_is_leap and not curr_is_leap:
                    # Remove Feb 29 from previous year data
                    feb29_prev = pd.Timestamp(year=previous_year, month=2, day=29)
                    df_prev_ytd = df_prev_ytd[~((df_prev_ytd.index.month == 2) & (df_prev_ytd.index.day == 29))]
                elif curr_is_leap and not prev_is_leap and data_available_until.month > 2:
                    # If we're past Feb 29 in current leap year, remove Feb 29 from current year
                    df_cur_ytd = df_cur_ytd[~((df_cur_ytd.index.month == 2) & (df_cur_ytd.index.day == 29))]
            else:
                df_prev_ytd = pd.DataFrame(columns=['consumption'])

            def total(series: pd.Series) -> float:
                return float(series.sum()) if series is not None and not series.empty else 0.0

            mtd_cur = total(df_cur_mtd['consumption'])
            mtd_prev = total(df_prev_mtd['consumption'])
            ytd_cur = total(df_cur_ytd['consumption'])
            ytd_prev = total(df_prev_ytd['consumption'])

            def delta(cur: float, prev: float):
                diff = cur - prev
                pct = (diff / prev * 100.0) if prev not in [0, None] else None
                return diff, pct

            mtd_diff, mtd_pct = delta(mtd_cur, mtd_prev)
            ytd_diff, ytd_pct = delta(ytd_cur, ytd_prev)

            metrics = {
                'mtd': {
                    'current_year': round(mtd_cur, 2),
                    'previous_year': round(mtd_prev, 2),
                    'diff': round(mtd_diff, 2),
                    'pct': round(mtd_pct, 2) if mtd_pct is not None else None,
                    'month_name': now.strftime('%B')
                },
                'ytd': {
                    'current_year': round(ytd_cur, 2),
                    'previous_year': round(ytd_prev, 2),
                    'diff': round(ytd_diff, 2),
                    'pct': round(ytd_pct, 2) if ytd_pct is not None else None
                }
            }
        except Exception as e:
            current_app.logger.error("Year-over-year metric calculation failed: %s", e, exc_info=True)
            metrics = {}

        # Format the response as expected by the frontend
        result = {'consumption': {}, 'metrics': metrics}
        
        if not weekly_avg_current.empty:
            result['consumption'][str(current_year)] = weekly_avg_current['consumption'].tolist()
            
        if not weekly_avg_previous.empty:
            result['consumption'][str(previous_year)] = weekly_avg_previous['consumption'].tolist()
        
        return jsonify(result)
        
    except Exception as e:
        return api_error("get_demand_data", e)


@cao_charts_bp.route('/get_monthly_demand_data')
@login_required
def get_monthly_demand_data():
    try:
        current_year = datetime.now().year  # 2026
        previous_year = current_year - 1    # 2025
        
        # Get current date to limit the data range
        current_date = datetime.now()
        
        # Use raw SQL to get monthly averages
        query = text("""
            SELECT 
                EXTRACT(year FROM datetime) as year,
                EXTRACT(month FROM datetime) as month,
                AVG(consumption) as avg_consumption
            FROM demand_data
            WHERE (EXTRACT(year FROM datetime) = :current_year AND datetime <= :current_date)
               OR (EXTRACT(year FROM datetime) = :previous_year)
            GROUP BY EXTRACT(year FROM datetime), EXTRACT(month FROM datetime)
            ORDER BY year, month
        """)
        
        # Execute query
        result = db.session.execute(
            query, 
            {
                "current_year": current_year, 
                "current_date": current_date,
                "previous_year": previous_year
            }
        ).fetchall()
        
        # Process the data for the frontend
        monthly_data = {
            str(current_year): [0] * 12,
            str(previous_year): [0] * 12
        }
        
        for row in result:
            year_str = str(int(row.year))
            month_idx = int(row.month) - 1  # Convert to 0-based index
            if year_str in monthly_data:
                monthly_data[year_str][month_idx] = float(row.avg_consumption) if row.avg_consumption else 0
        
        return jsonify({'monthly_consumption': monthly_data})
        
    except Exception as e:
        return api_error("get_monthly_demand_data", e)
