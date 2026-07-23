from flask import Blueprint, request, jsonify, current_app, session
import pandas as pd
import numpy as np
import traceback
import uuid
import os
import base64
import requests as http_requests
from datetime import datetime
from ..functions import login_required

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



EVAL_PERIOD = 168  # validation window shown before the forecast (1 week)

def _covariate_drop_cols(model_name, lagged_hour_selection=1):
    """Columns to remove from covariates (match notebook behavior).

    Model 1: lag/MA cols are NOT useful covariates — drop them all.
    Model 2: lag/MA cols ARE covariates (they carry recent direction info) — only drop system_direction.
    """
    if model_name == 'Model 2':
        return ['system_direction']
    # Model 1
    return [
        'system_direction',
        f'system_direction_lag{lagged_hour_selection}',
        'system_direction_ma2',
        'system_direction_ma3',
        'system_direction_ma6',
        'system_direction_ma12',
    ]


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


_ALL_QUANTILES = [round(q, 2) for q in np.arange(0.05, 1.0, 0.05).tolist()]


def _find_q_key(quantiles_dict, target_q):
    """Find the dict key closest to target_q (handles float formatting differences)."""
    keys_as_float = {float(k): k for k in quantiles_dict}
    nearest = min(keys_as_float.keys(), key=lambda x: abs(x - target_q))
    return keys_as_float[nearest]


def _call_modal(train_df, cov_df, prediction_length, model_name):
    """POST feature-engineered DataFrames to Modal endpoint, return {dates, quantiles}."""
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
        "quantile_levels":   _ALL_QUANTILES,
        "model":             model_name,
    }

    # Use custom encoder to handle numpy dtypes and NaN
    body = json.dumps(payload, default=_json_default)
    current_app.logger.info(f"Sending to Modal: train={len(payload['train'])} rows, cov={len(payload['covariates'])} rows, n={prediction_length}")

    last_exc = None
    for attempt in range(2):
        try:
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
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                import time as _time
                current_app.logger.warning(f"Modal attempt {attempt + 1} failed ({exc}), retrying in 5s…")
                _time.sleep(5)
    raise last_exc


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
@login_required
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

    except Exception:
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Internal server error'}), 500


@forecasting_bp.route('/evaluate', methods=['POST'])
@login_required
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

        full_df, _ = build_chronos_features(engine, excel_data, model_name, lagged_hour_selection=1)
        known      = full_df[full_df['system_direction'].notna()].copy()

        if len(known) < forecast_period + ctx_len:
            return jsonify({'error': 'Not enough historical data for evaluation'}), 400

        drop_cols  = _covariate_drop_cols(model_name, lagged_hour_selection=1)
        test_rows  = known.tail(forecast_period)
        ctx_end    = len(known) - forecast_period
        train_df   = known.iloc[max(0, ctx_end - ctx_len):ctx_end].copy()
        cov_df     = test_rows.drop(columns=drop_cols, errors='ignore').copy()

        chronos_result = _call_modal(train_df, cov_df, forecast_period, model_name)

        actual_vals    = test_rows['system_direction'].values
        q50_key        = _find_q_key(chronos_result['quantiles'], 0.5)
        predicted_vals = np.array(chronos_result['quantiles'][q50_key])[:len(actual_vals)]

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

    except Exception:
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Internal server error'}), 500


@forecasting_bp.route('/predict', methods=['POST'])
@login_required
def predict():
    try:
        if 'file' not in request.files or request.files['file'].filename == '':
            return jsonify({'error': 'No file uploaded'}), 400

        excel_data            = pd.read_excel(request.files['file'], header=2)
        model_name            = request.form.get('model', 'Model 1')
        lagged_hour_selection = int(request.form.get('lagged_hour_selection', 1))
        lagged_hour_selection = max(1, min(5, lagged_hour_selection))  # clamp 1–5

        if model_name not in VALID_MODELS:
            return jsonify({'error': f'Unknown model: {model_name}'}), 400

        engine  = get_database_connection()
        ctx_len = CONTEXT_LENGTHS.get(model_name, 168)

        full_df, known_price_length = build_chronos_features(
            engine, excel_data, model_name, lagged_hour_selection
        )
        known  = full_df[full_df['system_direction'].notna()]
        future = full_df[full_df['system_direction'].isna()]

        if len(known) < EVAL_PERIOD + ctx_len:
            return jsonify({'error': 'Not enough historical data'}), 400
        if known_price_length == 0:
            return jsonify({'error': 'No future PTF price data available in DB'}), 400

        drop_cols = _covariate_drop_cols(model_name, lagged_hour_selection)

        # Validation slice (last EVAL_PERIOD known rows)
        eval_rows = known.tail(EVAL_PERIOD).copy()
        pre_eval  = known.iloc[:-EVAL_PERIOD]
        train_df  = pre_eval.tail(ctx_len).copy()

        # Covariates = eval period + future (both without system_direction cols)
        eval_cov   = eval_rows.drop(columns=drop_cols, errors='ignore')
        future_cov = future.drop(columns=drop_cols, errors='ignore').head(known_price_length)
        cov_df     = pd.concat([eval_cov, future_cov], ignore_index=True)

        total_length   = EVAL_PERIOD + known_price_length
        chronos_result = _call_modal(train_df, cov_df, total_length, model_name)

        quantiles_dict = chronos_result['quantiles']  # {q_str: [values]}
        all_dates      = chronos_result['dates']

        val_dates  = [d.strftime('%Y-%m-%d %H:%M:%S') for d in pd.to_datetime(eval_rows['date'])]
        val_actual = eval_rows['system_direction'].tolist()
        a = np.array(val_actual)

        # Find best quantile by RMSE on the validation portion (notebook: best_q)
        best_q_key  = None
        best_rmse   = float('inf')
        for q_key, vals in quantiles_dict.items():
            p = np.array(vals[:EVAL_PERIOD])
            rmse = float(np.sqrt(np.mean((a - p) ** 2)))
            if rmse < best_rmse:
                best_rmse = rmse
                best_q_key = q_key

        best_q     = float(best_q_key)
        q_low_val  = round(max(0.05, best_q - 0.25), 2)
        q_high_val = round(min(0.95, best_q + 0.25), 2)

        q_low_key  = _find_q_key(quantiles_dict, q_low_val)
        q_high_key = _find_q_key(quantiles_dict, q_high_val)

        val_predicted = quantiles_dict[best_q_key][:EVAL_PERIOD]
        future_median = quantiles_dict[best_q_key][EVAL_PERIOD:]
        future_lower  = quantiles_dict[q_low_key][EVAL_PERIOD:]
        future_upper  = quantiles_dict[q_high_key][EVAL_PERIOD:]
        future_dates  = all_dates[EVAL_PERIOD:]

        # MAE / R² on validation section using best_q
        p      = np.array(val_predicted)
        mae    = round(float(np.mean(np.abs(a - p))), 2)
        ss_res = np.sum((a - p) ** 2)
        ss_tot = np.sum((a - np.mean(a)) ** 2)
        r2     = round(float(1 - ss_res / ss_tot) if ss_tot > 0 else 0, 2)

        # Confusion matrix on validation section
        confusion_data = None
        try:
            confusion_data = compute_confusion_matrix(val_actual, val_predicted)
        except Exception:
            pass

        # Excel download DataFrame (forecast only)
        forecast_df = pd.DataFrame({
            'date':                          future_dates,
            f'system_direction_{q_low_val}': future_lower,
            f'system_direction_{best_q}':    future_median,
            f'system_direction_{q_high_val}': future_upper,
        })

        # Pre-compute Excel bytes here so any gunicorn worker can serve the download.
        # forecast_cache is per-process; without this, download-forecast fails ~50% of
        # the time because gunicorn round-robins the request to the other worker.
        _excel_bytes = to_excel_bytes(forecast_df)
        _first_date  = future_dates[0] if future_dates else ''
        _last_date   = future_dates[-1] if future_dates else ''
        _filename    = f"direction_forecast_{model_name}_{_first_date}_{_last_date}.xlsx"

        forecast_id = str(uuid.uuid4())
        forecast_cache[forecast_id] = {
            'model_name':        model_name,
            'known_price_length': known_price_length,
            'forecast_result':   {'forecast_df': forecast_df, 'future_dates': future_dates},
            'timestamp':         datetime.now().isoformat(),
        }
        _clean_cache()
        session.setdefault('forecast_downloads', {})[forecast_id] = {
            'excel_b64': base64.b64encode(_excel_bytes).decode('utf-8'),
            'filename':  _filename,
        }

        response_data = {
            'success':            True,
            'model_name':         MODEL_DISPLAY_NAMES.get(model_name, model_name),
            'known_price_length': known_price_length,
            'best_quantile':      best_q,
            'mae': mae, 'r2': r2,
            'validation': {'x': val_dates, 'actual': val_actual, 'predicted': val_predicted},
            'forecast':   {'x': future_dates, 'median': future_median,
                           'lower': future_lower, 'upper': future_upper},
            'forecast_id': forecast_id,
        }
        if confusion_data:
            response_data['confusion_matrix'] = confusion_data

        return jsonify(response_data)

    except Exception:
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Internal server error'}), 500


@forecasting_bp.route('/download-forecast', methods=['POST'])
@login_required
def download_forecast():
    try:
        if 'file' not in request.files or request.files['file'].filename == '':
            return jsonify({'error': 'No file uploaded'}), 400

        reuse_results = request.form.get('reuse_results', 'false').lower() == 'true'
        forecast_id   = request.form.get('forecast_id')

        # Same-worker fast path: in-process cache still holds the DataFrame
        if reuse_results and forecast_id and forecast_id in forecast_cache:
            cached      = forecast_cache[forecast_id]
            fr          = cached['forecast_result']
            excel_bytes = to_excel_bytes(fr['forecast_df'])
            dates       = fr['future_dates']
            first_date  = dates[0] if dates else ''
            last_date   = dates[-1] if dates else ''
            return jsonify({
                'success':    True,
                'excel_data': base64.b64encode(excel_bytes).decode('utf-8'),
                'filename':   f"direction_forecast_{cached['model_name']}_{first_date}_{last_date}.xlsx",
            })

        # Cross-worker fallback: Excel bytes were pre-computed in predict() and stored in the
        # filesystem-backed Flask session, which is readable by any worker on the same host.
        session_cache = session.get('forecast_downloads', {})
        if reuse_results and forecast_id and forecast_id in session_cache:
            entry = session_cache[forecast_id]
            return jsonify({
                'success':    True,
                'excel_data': entry['excel_b64'],
                'filename':   entry['filename'],
            })

        return jsonify({'error': 'Forecast session expired. Please run Predict again.'}), 400

    except Exception:
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Internal server error'}), 500
