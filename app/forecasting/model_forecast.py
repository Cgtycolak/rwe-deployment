import numpy as np
import pandas as pd
from darts import TimeSeries
import io
import pytz
from datetime import datetime
from .utils import ts_to_df

def _safe_quantiles_df(series: TimeSeries, quantiles=None) -> pd.DataFrame:
    """Return a DataFrame of quantiles for a Darts TimeSeries, with fallbacks.

    If the underlying Darts version does not expose quantiles_df, fallback to
    using the deterministic values for all requested quantiles.
    """
    if quantiles is None:
        quantiles = [0.05, 0.5, 0.95]
    
    # Try quantiles_df (plural) first — this is the API used in the notebook
    try:
        result = series.quantiles_df(quantiles)
        return result
    except AttributeError:
        pass
    except Exception as e:
        print(f"quantiles_df failed with: {e}")
    
    # Try quantile_df (singular) for newer Darts versions
    try:
        result = series.quantile_df(quantiles)
        return result
    except AttributeError:
        pass
    except Exception as e:
        print(f"quantile_df failed with: {e}")
    
    # Fallback: extract from stochastic samples or use deterministic values
    try:
        base_df = ts_to_df(series)
        print(f"Fallback: DataFrame shape={base_df.shape}, columns={base_df.columns.tolist()[:10]}")
        
        # For stochastic series, columns might be like: component_sample_0, component_sample_1, etc.
        # Extract component name from first column
        first_col = str(base_df.columns[0])
        
        # Try to identify the base component name
        if '_sample_' in first_col or '_sample' in first_col:
            # Extract component name before '_sample'
            parts = first_col.split('_sample')
            target_col = parts[0]
        elif 'system_direction' in first_col:
            target_col = 'system_direction'
        else:
            # Use the first column name, stripping any numeric suffix
            import re
            match = re.match(r'^(.+?)(_\d+)?$', first_col)
            target_col = match.group(1) if match else first_col
        
        # Check if this is a stochastic series (multiple columns with similar names)
        # All columns should be samples of the same component
        if len(base_df.columns) > 1:
            print(f"Stochastic series detected with {len(base_df.columns)} samples, target_col={target_col}")
            # Compute quantiles from all columns (each column is a sample)
            out = pd.DataFrame(index=base_df.index)
            sample_data = base_df.values  # All columns are samples
            for q in quantiles:
                out[f"{target_col}_{q}"] = np.quantile(sample_data, q, axis=1)
            print(f"Created quantile DataFrame with columns: {out.columns.tolist()}")
            return out
        else:
            # Deterministic series: single column, use same value for all quantiles
            print(f"Deterministic series detected, target_col={target_col}")
            out = pd.DataFrame(index=base_df.index)
            for q in quantiles:
                out[f"{target_col}_{q}"] = base_df.iloc[:, 0].values
            print(f"Created quantile DataFrame with columns: {out.columns.tolist()}")
            return out
    except Exception as e:
        import traceback
        print(f"Fallback failed: {e}")
        print(traceback.format_exc())
        raise RuntimeError(f"Could not extract quantiles from TimeSeries: {e}")

def make_forecast(model, forecast_period, covariates_data=None, num_simulations=100, df_history=None):
    """Make a forecast using the specified model.
    
    Args:
        model: Fitted Darts model
        forecast_period: Number of hours to forecast
        covariates_data: Future covariates TimeSeries
        num_simulations: Number of stochastic simulations
        df_history: DataFrame with historical data (for computing rolling averages)
    """
    if covariates_data is None:
        raise ValueError('covariates_data variable must not be None!')
    
    model_name = model.__class__.__name__
    
    # Get current time in Turkey
    turkey_tz = pytz.timezone("Europe/Istanbul")
    now_tr = datetime.now(tz=turkey_tz)
    next_hour = now_tr.replace(minute=0, second=0, microsecond=0) + pd.Timedelta(hours=1)
    
    new_covariates = ts_to_df(covariates_data).copy()
    new_covariates = TimeSeries.from_dataframe(new_covariates)
    
    # Build history list for rolling average computation
    if df_history is not None:
        history = df_history[df_history['system_direction'].notnull()]['system_direction'].tolist()
    else:
        history = []
    
    if forecast_period > 1:
        for loop in range(1, forecast_period):
            one_step_fc = model.predict(1 * loop, num_samples=num_simulations, future_covariates=new_covariates)
            qdf_last = _safe_quantiles_df(one_step_fc, [0.05, 0.5, 0.95]).iloc[-1:]
            
            # Get the median forecast value and add to history
            median_col = 'system_direction_0.5'
            if median_col not in qdf_last.columns:
                median_cols = [c for c in qdf_last.columns if c.endswith('_0.5')]
                if median_cols:
                    median_col = median_cols[0]
            
            if median_col in qdf_last.columns:
                history.append(qdf_last[median_col].iloc[0])
            
            # Compute moving averages from history
            ma_2h = sum(history[-2:]) / min(len(history), 2) if history else 0
            ma_3h = sum(history[-3:]) / min(len(history), 3) if history else 0
            ma_6h = sum(history[-6:]) / min(len(history), 6) if history else 0
            ma_12h = sum(history[-12:]) / min(len(history), 12) if history else 0
            
            long_forecast = qdf_last.rename(columns={median_col: 'system_direction_lag1'})
            long_forecast.index = long_forecast.index + pd.Timedelta(hours=1)
            new_covariates = ts_to_df(new_covariates)
            
            # Update lag1
            if 'system_direction_lag1' not in long_forecast.columns:
                median_cols = [c for c in long_forecast.columns if c.endswith('_0.5')]
                if median_cols:
                    long_forecast['system_direction_lag1'] = long_forecast[median_cols[0]]
            new_covariates.update(long_forecast['system_direction_lag1'])
            
            # Update moving average covariates
            if 'system_direction_ma2' in new_covariates.columns:
                new_covariates.loc[long_forecast.index, 'system_direction_ma2'] = ma_2h
            if 'system_direction_ma3' in new_covariates.columns:
                new_covariates.loc[long_forecast.index, 'system_direction_ma3'] = ma_3h
            if 'system_direction_ma6' in new_covariates.columns:
                new_covariates.loc[long_forecast.index, 'system_direction_ma6'] = ma_6h
            if 'system_direction_ma12' in new_covariates.columns:
                new_covariates.loc[long_forecast.index, 'system_direction_ma12'] = ma_12h
            
            new_covariates = TimeSeries.from_dataframe(new_covariates)
        
        full_fc = model.predict(forecast_period, num_samples=num_simulations, future_covariates=new_covariates)
        probabilistic_forecast = _safe_quantiles_df(full_fc, [0.05, 0.5, 0.95])
    else:
        full_fc = model.predict(forecast_period, num_samples=num_simulations, future_covariates=new_covariates)
        probabilistic_forecast = _safe_quantiles_df(full_fc, [0.05, 0.5, 0.95])
    
    # Adjust forecast times to start from the next hour
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

def generate_shap_plot(model):
    """Generate a SHAP summary plot and return it as a base64-encoded PNG image.
    
    Uses darts.explainability.ShapExplainer to create the beeswarm summary plot.
    Returns None if SHAP analysis fails (e.g., unsupported model type).
    """
    import base64
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend for server-side rendering
    import matplotlib.pyplot as plt
    
    try:
        from darts.explainability import ShapExplainer
        
        plt.close('all')
        
        shap_explainer = ShapExplainer(model=model)
        shap_explainer.summary_plot()
        
        # Grab the figure that summary_plot created
        fig = plt.gcf()
        
        # Remove duplicate colorbar axes — keep only the main plot (axes[0])
        # and the first colorbar (axes[1]), remove any extras
        all_axes = fig.get_axes()
        for ax in all_axes[2:]:
            fig.delaxes(ax)
        
        # Resize for proper display
        fig.set_size_inches(15, 8)
        
        # Save to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close('all')
        buf.seek(0)
        
        # Encode as base64
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return img_base64
        
    except Exception as e:
        print(f"SHAP explainer error: {e}")
        import traceback
        traceback.print_exc()
        plt.close('all')
        return None

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