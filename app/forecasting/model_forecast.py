import numpy as np
import pandas as pd
from darts import TimeSeries
import io

def make_forecast(model, forecast_period, covariates_data=None, num_simulations=100):
    """Make a forecast using the specified model."""
    if covariates_data is None:
        raise ValueError('covariates_data variable must not be None!')
    
    model_name = model.__class__.__name__
    
    new_covariates = covariates_data.pd_dataframe().copy()
    new_covariates = TimeSeries.from_dataframe(new_covariates)
    
    if forecast_period > 1:
        for loop in range(1, forecast_period):
            probabilistic_forecast = model.predict(1*loop, num_samples=num_simulations, future_covariates=new_covariates)
            probabilistic_forecast = probabilistic_forecast.quantiles_df([0.05,0.5,0.95]).iloc[-1:]
            
            long_forecast = probabilistic_forecast.rename(columns={'system_direction_0.5':'system_direction_lag1'})
            long_forecast.index = long_forecast.index + pd.Timedelta(hours=1)
            new_covariates = new_covariates.pd_dataframe()
            new_covariates.update(long_forecast['system_direction_lag1'])
            new_covariates = TimeSeries.from_dataframe(new_covariates)
        
        probabilistic_forecast = model.predict(forecast_period, num_samples=num_simulations, future_covariates=new_covariates)
        probabilistic_forecast = probabilistic_forecast.quantiles_df([0.05,0.5,0.95])
    
    else:
        probabilistic_forecast = model.predict(forecast_period, num_samples=num_simulations, future_covariates=new_covariates)
        probabilistic_forecast = probabilistic_forecast.quantiles_df([0.05,0.5,0.95])
    
    # Prepare plot data
    forecast_data = {
        'x': probabilistic_forecast.index.tolist(),
        'upper': probabilistic_forecast['system_direction_0.95'].tolist(),
        'lower': probabilistic_forecast['system_direction_0.05'].tolist(),
        'median': probabilistic_forecast['system_direction_0.5'].tolist(),
        'model_name': model_name,
        'forecast_period': forecast_period
    }
    
    # Reset index and rename the index column to 'index'
    forecast_df = probabilistic_forecast.reset_index().rename(columns={'index': 'date'})
    
    return {
        'forecast_data': forecast_data,
        'forecast_df': forecast_df
    }

def to_excel_bytes(df):
    """Convert a DataFrame to Excel bytes for download."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Veri')
    
    return output.getvalue() 