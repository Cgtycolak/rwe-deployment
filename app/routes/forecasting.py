from flask import Blueprint, request, jsonify, current_app
import pandas as pd
import numpy as np
import traceback
import uuid
import os
import base64
import requests as http_requests
from datetime import datetime

from ..forecasting.utils import (
    get_database_connection,
    fetch_generation_data,
    fetch_dgp_data,
    process_excel_data,
    build_chronos_features,
    CONTEXT_LENGTHS,
)
from ..forecasting.model_testing import compute_confusion_matrix
from ..forecasting.model_forecast import to_excel_bytes

forecasting_bp = Blueprint('forecasting', __name__, url_prefix='/api/forecasting')

# In-memory cache for forecast results
forecast_cache = {}

VALID_MODELS = {"Model 1", "Model 2"}

MODEL_DISPLAY_NAMES = {
    "Model 1": "Long Term — Without Recently Direction",
    "Model 2": "Short Term — With Recently Direction",
}


def _get_modal_url():
    url = os.getenv("MODAL_CHRONOS_URL", "").rstrip("/")
    if not url:
        raise RuntimeError(
            "MODAL_CHRONOS_URL environment variable is not set. "
            "Deploy modal_chronos.py and add the endpoint URL to Render env vars."
        )
    return url



def _build_system_direction_series(engine, excel_data):
    """Fetch system direction + generation data for the Recent Data tab only."""
    dgp_df = fetch_dgp_data(engine)

    if excel_data is not None:
        today_df = process_excel_data(excel_data)
        if not today_df.empty:
            dgp_df = (
                pd.concat([dgp_df, today_df])
                .drop_duplicates(subset=['date'], keep='last')
                .sort_values('date')
                .reset_index(drop=True)
            )

    generation_df = fetch_generation_data(engine)
    merged = pd.merge(generation_df, dgp_df, on='date', how='right')
    merged = merged.sort_values('date').reset_index(drop=True)
    return merged


def _call_modal(train_df, cov_df, prediction_length, model_name):
    """POST feature-engineered DataFrames to Modal endpoint, return {dates, lower, median, upper}."""
    import json, math
    url = _get_modal_url()

    def _json_default(obj):
        """Fallback serializer: converts numpy/pandas types and NaN → JSON-safe values."""
        import numpy as np
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            v = float(obj)
            return None if not math.isfinite(v) else v
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        if isinstance(obj, float) and not math.isfinite(obj):
            return None
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def df_to_records(df):
        out = df.copy()
        for col in out.select_dtypes(include=['datetime64[ns]', 'datetimetz']).columns:
            out[col] = out[col].astype(str)
        return out.to_dict(orient='records')

    payload = {
        "train":             df_to_records(train_df),
        "covariates":        df_to_records(cov_df),
        "prediction_length": int(prediction_length),
        "quantile_levels":   [0.1, 0.5, 0.9],
        "model":             model_name,
    }

    # Use custom encoder to handle numpy dtypes and NaN
    body = json.dumps(payload, default=_json_default)
    current_app.logger.info(f"Sending to Modal: train={len(payload['train'])} rows, cov={len(payload['covariates'])} rows, n={prediction_length}")

    resp = http_requests.post(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        timeout=300,
    )
    if not resp.ok:
        current_app.logger.error(f"Modal {resp.status_code}: {resp.text[:1000]}")
    resp.raise_for_status()
    return resp.json()


def _clean_cache():
    current_time = datetime.now()
    stale = [
        k for k, v in forecast_cache.items()
        if (current_time - datetime.fromisoformat(v['timestamp'])).total_seconds() > 900
    ]
    for k in stale:
        del forecast_cache[k]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@forecasting_bp.route('/recent-data', methods=['POST'])
def get_recent_data():
    try:
        if 'file' not in request.files or request.files['file'].filename == '':
            return jsonify({'error': 'No file uploaded'}), 400

        excel_data = pd.read_excel(request.files['file'], header=2)
        hours = int(request.form.get('hours', 24))
        engine = get_database_connection()

        merged = _build_system_direction_series(engine, excel_data)
        recent = merged[merged['system_direction'].notna()].tail(hours)

        data_list = [
            {
                'date': row['date'].strftime('%Y-%m-%d %H:%M:%S'),
                'system_direction': float(row['system_direction']),
                'wind':  float(row['wind'])  if pd.notna(row.get('wind'))  else 0,
                'hydro': float(row['hydro']) if pd.notna(row.get('hydro')) else 0,
                'solar': float(row['solar']) if pd.notna(row.get('solar')) else 0,
            }
            for _, row in recent.iterrows()
        ]

        return jsonify({'success': True, 'data': data_list})

    except Exception as e:
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@forecasting_bp.route('/evaluate', methods=['POST'])
def evaluate():
    try:
        if 'file' not in request.files or request.files['file'].filename == '':
            return jsonify({'error': 'No file uploaded'}), 400

        excel_data      = pd.read_excel(request.files['file'], header=2)
        model_name      = request.form.get('model', 'Model 1')
        forecast_period = int(request.form.get('forecast_period', 168))

        if model_name not in VALID_MODELS:
            return jsonify({'error': f'Unknown model: {model_name}'}), 400

        engine  = get_database_connection()
        ctx_len = CONTEXT_LENGTHS.get(model_name, 168)

        full_df = build_chronos_features(engine, excel_data, model_name)
        known   = full_df[full_df['system_direction'].notna()].copy()

        if len(known) < forecast_period + ctx_len:
            return jsonify({'error': 'Not enough historical data for evaluation'}), 400

        # Split: last forecast_period as test, the ctx_len before that as training context
        test_rows  = known.tail(forecast_period)
        ctx_end    = len(known) - forecast_period
        train_df   = known.iloc[max(0, ctx_end - ctx_len):ctx_end].copy()
        cov_df     = test_rows.drop(columns=['system_direction'], errors='ignore').copy()

        chronos_result = _call_modal(train_df, cov_df, forecast_period, model_name)

        actual_vals    = test_rows['system_direction'].values
        predicted_vals = np.array(chronos_result['median'])[:len(actual_vals)]

        mae_score = float(np.round(np.mean(np.abs(actual_vals - predicted_vals)), 2))
        ss_res    = np.sum((actual_vals - predicted_vals) ** 2)
        ss_tot    = np.sum((actual_vals - np.mean(actual_vals)) ** 2)
        r2_value  = float(np.round(1 - ss_res / ss_tot if ss_tot > 0 else 0, 2))

        real_x     = [d.strftime('%Y-%m-%d %H:%M:%S') for d in pd.to_datetime(test_rows['date'])]
        forecast_x = chronos_result['dates']

        confusion_data = None
        try:
            confusion_data = compute_confusion_matrix(actual_vals, predicted_vals)
        except Exception:
            pass

        result = {
            'model_name': MODEL_DISPLAY_NAMES.get(model_name, model_name),
            'mae':        mae_score,
            'r2':         r2_value,
            'real_data':     {'x': real_x,     'y': actual_vals.tolist()},
            'forecast_data': {'x': forecast_x, 'y': predicted_vals.tolist()},
        }
        if confusion_data:
            result['confusion_matrix'] = confusion_data

        return jsonify({'success': True, 'result': result})

    except Exception as e:
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@forecasting_bp.route('/predict', methods=['POST'])
def predict():
    try:
        if 'file' not in request.files or request.files['file'].filename == '':
            return jsonify({'error': 'No file uploaded'}), 400

        excel_data      = pd.read_excel(request.files['file'], header=2)
        model_name      = request.form.get('model', 'Model 1')
        forecast_period = int(request.form.get('forecast_period', 24))

        if model_name not in VALID_MODELS:
            return jsonify({'error': f'Unknown model: {model_name}'}), 400

        engine  = get_database_connection()
        ctx_len = CONTEXT_LENGTHS.get(model_name, 168)

        full_df = build_chronos_features(engine, excel_data, model_name)
        known   = full_df[full_df['system_direction'].notna()]
        future  = full_df[full_df['system_direction'].isna()]

        if len(known) < 12:
            return jsonify({'error': 'Not enough historical data'}), 400

        train_df = known.tail(ctx_len).copy()
        cov_df   = future.drop(columns=['system_direction'], errors='ignore').head(forecast_period).copy()

        if len(cov_df) < forecast_period:
            return jsonify({'error': 'Not enough future covariate data in DB for requested forecast period'}), 400

        chronos_result = _call_modal(train_df, cov_df, forecast_period, model_name)

        timestamps = chronos_result['dates']
        forecast_data = {
            'x':               timestamps,
            'median':          chronos_result['median'],
            'lower':           chronos_result['lower'],
            'upper':           chronos_result['upper'],
            'model_name':      model_name,
            'forecast_period': forecast_period,
        }

        forecast_df = pd.DataFrame({
            'date':                  timestamps,
            'system_direction_0.1':  chronos_result['lower'],
            'system_direction_0.5':  chronos_result['median'],
            'system_direction_0.9':  chronos_result['upper'],
        })

        # Confusion matrix on last known window vs median prediction
        confusion_data = None
        try:
            if len(known) >= forecast_period:
                actual_vals    = known['system_direction'].values[-forecast_period:]
                predicted_vals = np.array(chronos_result['median'])[:len(actual_vals)]
                confusion_data = compute_confusion_matrix(actual_vals, predicted_vals)
        except Exception:
            pass

        forecast_id = str(uuid.uuid4())
        forecast_cache[forecast_id] = {
            'model_name':      model_name,
            'forecast_period': forecast_period,
            'forecast_result': {'forecast_data': forecast_data, 'forecast_df': forecast_df},
            'timestamp':       datetime.now().isoformat(),
        }
        _clean_cache()

        response_data = {
            'success':       True,
            'model_name':    model_name,
            'forecast_data': forecast_data,
            'forecast_id':   forecast_id,
        }
        if confusion_data:
            response_data['confusion_matrix'] = confusion_data

        return jsonify(response_data)

    except Exception as e:
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@forecasting_bp.route('/download-forecast', methods=['POST'])
def download_forecast():
    try:
        if 'file' not in request.files or request.files['file'].filename == '':
            return jsonify({'error': 'No file uploaded'}), 400

        reuse_results = request.form.get('reuse_results', 'false').lower() == 'true'
        forecast_id   = request.form.get('forecast_id')

        if reuse_results and forecast_id and forecast_id in forecast_cache:
            cached = forecast_cache[forecast_id]
            fr     = cached['forecast_result']
            excel_bytes = to_excel_bytes(fr['forecast_df'])
            first_date  = fr['forecast_data']['x'][0]
            last_date   = fr['forecast_data']['x'][-1]
            return jsonify({
                'success':    True,
                'excel_data': base64.b64encode(excel_bytes).decode('utf-8'),
                'filename':   f"direction_forecast_{cached['model_name']}_{first_date}_{last_date}.xlsx",
            })

        # Fallback: re-run prediction
        excel_data      = pd.read_excel(request.files['file'], header=2)
        model_name      = request.form.get('model', 'Model 1')
        forecast_period = int(request.form.get('forecast_period', 24))

        if model_name not in VALID_MODELS:
            return jsonify({'error': f'Unknown model: {model_name}'}), 400

        engine = get_database_connection()
        merged = _build_system_direction_series(engine, excel_data)
        context_values  = merged['system_direction'].dropna().tolist()
        chronos_result  = _call_modal(context_values, forecast_period, model_name)
        timestamps      = _make_forecast_timestamps(forecast_period)

        forecast_df = pd.DataFrame({
            'date':                  timestamps,
            'system_direction_0.1':  chronos_result['lower'],
            'system_direction_0.5':  chronos_result['median'],
            'system_direction_0.9':  chronos_result['upper'],
        })

        excel_bytes = to_excel_bytes(forecast_df)
        first_date  = timestamps[0].strftime('%Y-%m-%d %H:%M:%S')
        last_date   = timestamps[-1].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({
            'success':    True,
            'excel_data': base64.b64encode(excel_bytes).decode('utf-8'),
            'filename':   f'direction_forecast_{model_name}_{first_date}_{last_date}.xlsx',
        })

    except Exception as e:
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
