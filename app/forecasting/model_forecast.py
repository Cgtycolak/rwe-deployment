import numpy as np
import pandas as pd
from darts import TimeSeries
import io
import pytz
from datetime import datetime
from .utils import ts_to_df

def _safe_quantiles_df(series: TimeSeries, quantiles=None) -> pd.DataFrame:
    """Return a DataFrame of quantiles for a Darts TimeSeries, with fallbacks.

    If the underlying Darts version does not expose quantile_df, fallback to
    using the deterministic values for all requested quantiles.
    """
    if quantiles is None:
        quantiles = [0.05, 0.5, 0.95]
    
    # Try common Darts APIs for quantile extraction
    # Note: quantile_df (singular) is the correct method name in recent Darts versions
    try:
        return series.quantile_df(quantiles)
    except AttributeError:
        pass
    except Exception:
        pass
    
    try:
        return series.quantile_df(q=quantiles)
    except AttributeError:
        pass
    except Exception:
        pass
    
    # Try legacy API
    try:
        return series.quantiles_df(quantiles)
    except AttributeError:
        pass
    except Exception:
        pass
    
    # Fallback: extract from stochastic samples or use deterministic values
    try:
        base_df = ts_to_df(series)
        # Determine the target column name
        target_col = 'system_direction' if 'system_direction' in base_df.columns else base_df.columns[0]
        
        # Check if this is a stochastic series (multiple sample columns)
        # Stochastic series often have columns like: component_sample0, component_sample1, ...
        sample_cols = [c for c in base_df.columns if 'sample' in str(c).lower()]
        
        if sample_cols:
            # Compute quantiles from samples
            out = pd.DataFrame(index=base_df.index)
            sample_data = base_df[sample_cols].values
            for q in quantiles:
                out[f"{target_col}_{q}"] = np.quantile(sample_data, q, axis=1)
            return out
        else:
            # Deterministic series: use same value for all quantiles
            out = pd.DataFrame(index=base_df.index)
            for q in quantiles:
                out[f"{target_col}_{q}"] = base_df[target_col].values
            return out
    except Exception as e:
        raise RuntimeError(f"Could not extract quantiles from TimeSeries: {e}")

def make_forecast(model, forecast_period, covariates_data=None, num_simulations=100):
    """Make a forecast using the specified model."""
    if covariates_data is None:
        raise ValueError('covariates_data variable must not be None!')
    
    model_name = model.__class__.__name__
    
    # Get current time in Turkey
    turkey_tz = pytz.timezone("Europe/Istanbul")
    now_tr = datetime.now(tz=turkey_tz)
    next_hour = now_tr.replace(minute=0, second=0, microsecond=0) + pd.Timedelta(hours=1)
    
    new_covariates = ts_to_df(covariates_data).copy()
    new_covariates = TimeSeries.from_dataframe(new_covariates)
    
    if forecast_period > 1:
        for loop in range(1, forecast_period):
            one_step_fc = model.predict(1*loop, num_samples=num_simulations, future_covariates=new_covariates)
            qdf_last = _safe_quantiles_df(one_step_fc, [0.05, 0.5, 0.95]).iloc[-1:]
            long_forecast = qdf_last.rename(columns={'system_direction_0.5':'system_direction_lag1'})
            long_forecast.index = long_forecast.index + pd.Timedelta(hours=1)
            new_covariates = ts_to_df(new_covariates)
            # If fallback changed column naming, handle general case
            if 'system_direction_lag1' not in long_forecast.columns:
                # Try to infer the median column name
                median_cols = [c for c in long_forecast.columns if c.endswith('_0.5')]
                if median_cols:
                    long_forecast['system_direction_lag1'] = long_forecast[median_cols[0]]
            new_covariates.update(long_forecast['system_direction_lag1'])
            new_covariates = TimeSeries.from_dataframe(new_covariates)
        full_fc = model.predict(forecast_period, num_samples=num_simulations, future_covariates=new_covariates)
        probabilistic_forecast = _safe_quantiles_df(full_fc, [0.05, 0.5, 0.95])
    else:
        full_fc = model.predict(forecast_period, num_samples=num_simulations, future_covariates=new_covariates)
        probabilistic_forecast = _safe_quantiles_df(full_fc, [0.05, 0.5, 0.95])
    
    # Adjust forecast times to start from the next hour
    # This is the key change - we're explicitly setting the index to start from the next hour
    forecast_start = next_hour
    forecast_index = pd.date_range(start=forecast_start, periods=forecast_period, freq='h')
    
    # Create a new DataFrame with the adjusted index
    adjusted_forecast = pd.DataFrame({
        'system_direction_0.05': probabilistic_forecast['system_direction_0.05'].values,
        'system_direction_0.5': probabilistic_forecast['system_direction_0.5'].values,
        'system_direction_0.95': probabilistic_forecast['system_direction_0.95'].values
    }, index=forecast_index)
    
    # Format timestamps as strings with explicit timezone info
    formatted_timestamps = [dt.strftime('%Y-%m-%d %H:%M:%S') for dt in adjusted_forecast.index]
    
    # Prepare plot data
    forecast_data = {
        'x': formatted_timestamps,
        'upper': adjusted_forecast['system_direction_0.95'].tolist(),
        'lower': adjusted_forecast['system_direction_0.05'].tolist(),
        'median': adjusted_forecast['system_direction_0.5'].tolist(),
        'model_name': model_name,
        'forecast_period': forecast_period
    }
    
    # Reset index and rename the index column to 'index'
    forecast_df = adjusted_forecast.reset_index().rename(columns={'index': 'date'})
    
    return {
        'forecast_data': forecast_data,
        'forecast_df': forecast_df
    }

def to_excel_bytes(df):
    """Convert a DataFrame to Excel bytes for download."""
    # Create a copy to avoid modifying the original dataframe
    df_copy = df.copy()
    
    # Check if 'date' column exists and has timezone info
    if 'date' in df_copy.columns and hasattr(df_copy['date'].dtype, 'tz'):
        # Convert timezone-aware datetimes to timezone-naive
        df_copy['date'] = df_copy['date'].dt.tz_localize(None)
    
    # Write to Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_copy.to_excel(writer, index=False, sheet_name='Veri')
    
    return output.getvalue() 