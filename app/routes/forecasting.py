from flask import Blueprint, request, jsonify, current_app
import pandas as pd
import numpy as np
from io import BytesIO
import traceback
from ..forecasting.utils import get_database_connection, fetch_generation_data, fetch_dgp_data, prepare_data_for_modeling
from ..forecasting.model_testing import evaluate_model, evaluate_and_find_best
from ..forecasting.model_forecast import make_forecast, to_excel_bytes
from ..forecasting.models import get_model
import uuid
from datetime import datetime
from app.utils.ml_config import log_memory_usage, cleanup_memory, log_memory_with_label

forecasting_bp = Blueprint('forecasting', __name__, url_prefix='/api/forecasting')

# In-memory cache for forecast results
forecast_cache = {}

@forecasting_bp.route('/recent-data', methods=['POST'])
def get_recent_data():
    # Log memory at the beginning of heavy operations
    log_memory_usage()
    
    try:
        # Get uploaded Excel file
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Read Excel file
        excel_data = pd.read_excel(file, header=2)
        
        # Get database connection
        engine = get_database_connection()
        
        # Fetch data from database
        generation_df = fetch_generation_data(engine)
        dgp_df = fetch_dgp_data(engine)
        
        # Prepare data
        ts_df = prepare_data_for_modeling(generation_df, dgp_df, excel_data)
        
        # Get recent hours data
        hours = int(request.form.get('hours', 24))
        recent_data = ts_df.pd_dataframe()[ts_df.pd_dataframe()['system_direction'].notna()].tail(hours)
        
        # Convert to list for JSON response
        data_list = []
        for idx, row in recent_data.iterrows():
            data_list.append({
                'date': idx.strftime('%Y-%m-%d %H:%M:%S'),
                'system_direction': row['system_direction'],
                'wind': row.get('wind', 0),
                'hydro': row.get('hydro', 0),
                'solar': row.get('solar', 0)
            })
        
        # Clean up after heavy processing
        cleanup_memory()
        
        return jsonify({
            'success': True,
            'data': data_list
        })
    
    except Exception as e:
        current_app.logger.error(f"Error in get_recent_data: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@forecasting_bp.route('/evaluate', methods=['POST'])
def evaluate():
    # Log memory at the beginning of heavy operations
    log_memory_usage()
    
    try:
        # Get uploaded Excel file
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Read Excel file
        excel_data = pd.read_excel(file, header=2)
        
        # Get model name and forecast period
        model_name = request.form.get('model')
        forecast_period = int(request.form.get('forecast_period', 168))
        
        # Get database connection
        engine = get_database_connection()
        
        # Fetch data from database
        generation_df = fetch_generation_data(engine)
        dgp_df = fetch_dgp_data(engine)
        
        # Prepare data
        ts_df = prepare_data_for_modeling(generation_df, dgp_df, excel_data)
        
        # Split data
        covariates = ts_df.drop_columns(['system_direction'])
        train_val, test = ts_df[:-ts_df.pd_dataframe()['system_direction'].isnull().sum()], ts_df[-ts_df.pd_dataframe()['system_direction'].isnull().sum():]
        
        # Create train/validation split for evaluation (last week of training data)
        train, val = train_val.split_after(train_val.end_time() - pd.Timedelta(weeks=1))
        
        log_memory_with_label("Before model load")
        models = get_models()
        log_memory_with_label("After model load")
        
        # Handle "Best Model" selection
        if model_name == 'Best Model':
            # Find best model
            best_model_result = evaluate_and_find_best(models, forecast_period=forecast_period, 
                                                     train=train, val=val, covariates_data=covariates)
            model_name = best_model_result['best_model']
            
            # Include metrics for all models in response
            all_metrics = best_model_result['metrics']
        
        if model_name not in models:
            return jsonify({'error': f'Model {model_name} not found'}), 400
        
        # Evaluate model
        result = evaluate_model(models[model_name], forecast_period, train_val, train, val, covariates)
        
        # If we found a best model, add that info to the result
        if model_name == 'Best Model' and 'all_metrics' in locals():
            result['all_metrics'] = all_metrics
        
        # Clean up after heavy processing
        cleanup_memory()
        
        return jsonify({
            'success': True,
            'result': result
        })
    
    except Exception as e:
        current_app.logger.error(f"Error in evaluate: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@forecasting_bp.route('/predict', methods=['POST'])
def predict():
    # Log memory at the beginning
    log_memory_usage()
    
    try:
        # Get uploaded Excel file
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check file size (safely without using content_length)
        file_content = file.read()
        file_size = len(file_content)
        max_file_size = 5 * 1024 * 1024  # 5MB limit
        
        if file_size > max_file_size:
            cleanup_memory()
            return jsonify({'error': f'File too large ({file_size/1024/1024:.2f}MB). Max size is 5MB'}), 400
        
        # Reset file pointer after reading for size check
        file.seek(0)
        
        # Use BytesIO to avoid file IO issues
        from io import BytesIO
        file_buffer = BytesIO(file_content)
        
        # Read Excel with optimized memory settings
        excel_data = pd.read_excel(
            file_buffer, 
            header=2,
            engine='openpyxl'
        )
        
        # Free memory
        file_content = None
        file_buffer = None
        file = None
        
        model_name = request.form.get('model', 'Prophet')
        forecast_period = int(request.form.get('forecast_period', 24))
        
        # Get a single model instead of all models
        model = get_model(model_name)
        
        # Get database connection
        engine = get_database_connection()
        
        # Fetch data from database
        generation_df = fetch_generation_data(engine)
        dgp_df = fetch_dgp_data(engine)
        
        # Prepare data
        ts_df = prepare_data_for_modeling(generation_df, dgp_df, excel_data)
        
        # Split data
        covariates = ts_df.drop_columns(['system_direction'])
        train_val, test = ts_df[:-ts_df.pd_dataframe()['system_direction'].isnull().sum()], ts_df[-ts_df.pd_dataframe()['system_direction'].isnull().sum():]
        
        # Get models
        models = get_models()
        
        # Handle "Best Model" selection
        if model_name == 'Best Model':
            # Split train_val for evaluation
            train, val = train_val.split_after(train_val.end_time() - pd.Timedelta(weeks=1))
            
            # Find best model
            best_model_result = evaluate_and_find_best(models, forecast_period=24*7, train=train, val=val, covariates_data=covariates)
            model_name = best_model_result['best_model']
        
        if model_name not in models:
            return jsonify({'error': f'Model {model_name} not found'}), 400
        
        log_memory_with_label("Before model fit")
        model.fit(train_val['system_direction'], future_covariates=covariates)
        log_memory_with_label("After model fit")
        
        log_memory_with_label("Before predict")
        forecast_result = make_forecast(model, forecast_period, covariates_data=covariates)
        log_memory_with_label("After predict")
        
        # Generate a unique ID for this forecast and store in cache
        forecast_id = str(uuid.uuid4())
        forecast_cache[forecast_id] = {
            'model_name': model_name,
            'forecast_period': forecast_period,
            'forecast_result': forecast_result,
            'timestamp': datetime.now().isoformat()
        }
        
        # Clean up old cache entries (keep cache for 15 minutes)
        current_time = datetime.now()
        keys_to_remove = []
        for key, value in forecast_cache.items():
            cache_time = datetime.fromisoformat(value['timestamp'])
            if (current_time - cache_time).total_seconds() > 900:  # 15 minutes
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del forecast_cache[key]
        
        # Clean up after heavy processing
        cleanup_memory()
        
        return jsonify({
            'success': True,
            'model_name': model_name,
            'forecast_data': forecast_result['forecast_data'],
            'forecast_id': forecast_id  # Send the forecast ID to the client
        })
    
    except Exception as e:
        current_app.logger.error(f"Error in predict: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        
        # Always clean up memory, even after errors
        cleanup_memory()
        
        return jsonify({'error': str(e)}), 500

@forecasting_bp.route('/download-forecast', methods=['POST'])
def download_forecast():
    # Log memory at the beginning of heavy operations
    log_memory_usage()
    
    try:
        # This endpoint will generate an Excel file for download
        
        # Get uploaded Excel file
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check if we need to use cached results
        reuse_results = request.form.get('reuse_results', 'false').lower() == 'true'
        forecast_id = request.form.get('forecast_id')
        
        if reuse_results and forecast_id and forecast_id in forecast_cache:
            # Use cached forecast result
            cached_data = forecast_cache[forecast_id]
            model_name = cached_data['model_name']
            forecast_result = cached_data['forecast_result']
            
            # Convert forecast to Excel
            excel_bytes = to_excel_bytes(forecast_result['forecast_df'])
            
            # Get the first and last date from the forecast data for the filename
            first_date = forecast_result['forecast_data']['x'][0]
            last_date = forecast_result['forecast_data']['x'][-1]
            
            # Return base64 encoded Excel data
            import base64
            encoded_excel = base64.b64encode(excel_bytes).decode('utf-8')
            
            # Clean up after heavy processing
            cleanup_memory()
            
            return jsonify({
                'success': True,
                'excel_data': encoded_excel,
                'filename': f'direction_forecast_{model_name}_{first_date}_{last_date}.xlsx'
            })
        
        # If no cached result is available or reuse_results is false, continue with normal processing
        # Read Excel file
        excel_data = pd.read_excel(file, header=2)
        
        # Get model name and forecast period
        model_name = request.form.get('model')
        forecast_period = int(request.form.get('forecast_period', 24))
        
        # Get database connection
        engine = get_database_connection()
        
        # Fetch data from database
        generation_df = fetch_generation_data(engine)
        dgp_df = fetch_dgp_data(engine)
        
        # Prepare data - pass excel_data instead of file
        ts_df = prepare_data_for_modeling(generation_df, dgp_df, excel_data)
        
        # Split data
        covariates = ts_df.drop_columns(['system_direction'])
        train_val, test = ts_df[:-ts_df.pd_dataframe()['system_direction'].isnull().sum()], ts_df[-ts_df.pd_dataframe()['system_direction'].isnull().sum():]
        
        # Get models
        models = get_models()
        
        # Handle "Best Model" selection
        if model_name == 'Best Model':
            # Split train_val for evaluation
            train, val = train_val.split_after(train_val.end_time() - pd.Timedelta(weeks=1))
            
            # Find best model
            best_model_result = evaluate_and_find_best(models, forecast_period=24*7, train=train, val=val, covariates_data=covariates)
            model_name = best_model_result['best_model']
        
        if model_name not in models:
            return jsonify({'error': f'Model {model_name} not found'}), 400
        
        # Fit model and make forecast
        model = models[model_name].fit(train_val['system_direction'], future_covariates=covariates)
        forecast_result = make_forecast(model, forecast_period, covariates_data=covariates)
        
        # Convert forecast to Excel
        excel_bytes = to_excel_bytes(forecast_result['forecast_df'])
        
        # Get the first and last date from the forecast data for the filename
        first_date = forecast_result['forecast_data']['x'][0]
        last_date = forecast_result['forecast_data']['x'][-1]
        
        # Return base64 encoded Excel data
        import base64
        encoded_excel = base64.b64encode(excel_bytes).decode('utf-8')
        
        # Clean up after heavy processing
        cleanup_memory()
        
        return jsonify({
            'success': True,
            'excel_data': encoded_excel,
            'filename': f'direction_forecast_{model_name}_{first_date}_{last_date}.xlsx'
        })
    
    except Exception as e:
        current_app.logger.error(f"Error in download_forecast: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500 