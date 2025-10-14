import numpy as np
import pandas as pd
from darts import TimeSeries
from darts.metrics import r2_score, mae
import plotly.graph_objects as go
from .utils import ts_to_df

def evaluate_model(model, forecast_period, train_val, train, val, covariates_data=None):
    """Evaluate a model and return metrics and plot data."""
    model_name = model.__class__.__name__
    
    if covariates_data is None:
        raise ValueError('covariates_data variable must not be None!')
    
    # Handle NaNs in train and val data
    train_df = ts_to_df(train).copy()
    train_df = train_df.fillna(0)
    train = TimeSeries.from_dataframe(train_df)
    
    val_df = ts_to_df(val).copy()
    val_df = val_df.fillna(0)
    val = TimeSeries.from_dataframe(val_df)
    
    train_val_df = ts_to_df(train_val).copy()
    train_val_df = train_val_df.fillna(0)
    train_val = TimeSeries.from_dataframe(train_val_df)
    
    # Handle NaNs in covariates
    covariates_df = ts_to_df(covariates_data).copy()
    covariates_df = covariates_df.fillna(0)
    covariates_data = TimeSeries.from_dataframe(covariates_df)
    
    model.fit(train['system_direction'], future_covariates=covariates_data)
    forecast = model.predict(forecast_period, future_covariates=covariates_data)
    adjusted_forecast = TimeSeries.from_dataframe(ts_to_df(forecast))
    
    mae_score = np.round(mae(val['system_direction'], adjusted_forecast), 2)
    r2_value = np.round(r2_score(val['system_direction'], adjusted_forecast), 2)
    
    # Create plot data
    real_data = {
        'x': ts_to_df(train_val).index[len(train):len(train)+forecast_period].tolist(),
        'y': ts_to_df(train_val)['system_direction'][len(train):len(train)+forecast_period].tolist(),
        'name': 'Real'
    }
    
    forecast_data = {
        'x': ts_to_df(adjusted_forecast).index.tolist(),
        'y': ts_to_df(adjusted_forecast)['system_direction'].tolist(),
        'name': 'Forecast'
    }
    
    return {
        'model_name': model_name,
        'mae': mae_score,
        'r2': r2_value,
        'real_data': real_data,
        'forecast_data': forecast_data
    }

def evaluate_and_find_best(models, forecast_period, train, val, covariates_data=None):
    """Evaluate multiple models and find the best one."""
    if covariates_data is None:
        raise ValueError('covariates_data variable must not be None!')
    
    # Handle NaNs in train and val data
    train_df = ts_to_df(train).copy()
    train_df = train_df.fillna(0)
    train = TimeSeries.from_dataframe(train_df)
    
    val_df = ts_to_df(val).copy()
    val_df = val_df.fillna(0)
    val = TimeSeries.from_dataframe(val_df)
    
    # Handle NaNs in covariates
    covariates_df = ts_to_df(covariates_data).copy()
    covariates_df = covariates_df.fillna(0)
    covariates_data = TimeSeries.from_dataframe(covariates_df)
    
    evaluation_results = {}
    model_metrics = []
    
    for model_name, model in models.items():
        model.fit(train['system_direction'], future_covariates=covariates_data)
        forecast = model.predict(forecast_period, future_covariates=covariates_data)
        adjusted_forecast = TimeSeries.from_dataframe(ts_to_df(forecast))
        mae_score = np.round(mae(val['system_direction'], adjusted_forecast), 2)
        
        evaluation_results[model_name] = mae_score
        model_metrics.append({
            'model_name': model_name,
            'mae': mae_score
        })
    
    best_model_name = min(evaluation_results, key=evaluation_results.get)
    
    return {
        'best_model': best_model_name,
        'metrics': model_metrics
    } 