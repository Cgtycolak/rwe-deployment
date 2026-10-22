"""Forecast Performance tab."""
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, send_file
from ..functions import login_required
import pandas as pd
import numpy as np
from sqlalchemy import text
from .common import api_error
from ..database.supabase import get_supabase_engine

forecast_performance_bp = Blueprint('forecast_performance', __name__)


@forecast_performance_bp.route('/forecast-performance-data')
@login_required
def get_forecast_performance_data():
    try:
        # Get period parameter from request
        period_days = request.args.get('period', '30', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        forecast_horizon = request.args.get('horizon', 'd+1')  # Default to D+1, can be 'd+1' or 'd+2'
        
        engine = get_supabase_engine()

        # Resolve date range before querying so we can push it into SQL
        if start_date and end_date:
            start_dt = pd.to_datetime(start_date)
            end_dt   = pd.to_datetime(end_date)
            period_info = f"{start_date} to {end_date}"
        else:
            end_dt   = pd.Timestamp.now()
            start_dt = end_dt - pd.Timedelta(days=period_days)
            period_info = f"Last {period_days} Days"

        sq = {"start_dt": start_dt, "end_dt": end_dt}

        if forecast_horizon.lower() == 'd+2':
            met_table   = 'public."meteologica_forecast_d+2"'
            model_table = 'public.model_forecast_sfc'
            cemre_table = 'public."cemre_ptf_d+2"'
        else:
            met_table   = 'public.meteologica_forecast'
            model_table = 'public.model_forecast_ptf'
            cemre_table = 'public."cemre_ptf_d+1"'

        def _parse_dates(df):
            if not pd.api.types.is_datetime64_any_dtype(df['date']):
                df['date'] = df['date'].apply(
                    lambda x: str(x).split('+')[0].replace('T', ' ') if isinstance(x, str) else x
                )
            df['date'] = pd.to_datetime(df['date'])
            return df

        with engine.connect() as conn:
            ptf_df = pd.read_sql(text(
                "SELECT date, price AS actual_price FROM epias.ptf"
                " WHERE date >= :start_dt AND date <= :end_dt"
            ), con=conn, params=sq)

            if ptf_df.empty:
                return jsonify({'error': 'No PTF data available'}), 404

            meteologica_forecast = pd.read_sql(text(
                f"SELECT date, min_price AS meteologica_min,"
                f" avg_price AS meteologica_avg, max_price AS meteologica_max"
                f" FROM {met_table}"
                f" WHERE date::timestamp >= :start_dt AND date::timestamp <= :end_dt"
            ), con=conn, params=sq)

            try:
                model_forecast = pd.read_sql(text(
                    f"SELECT date, best_price FROM {model_table}"
                    f" WHERE date::timestamp >= :start_dt AND date::timestamp <= :end_dt"
                ), con=conn, params=sq)
            except Exception as e:
                current_app.logger.warning(
                    "Forecast query SELECT date,best_price failed for %r (%s); falling back to SELECT *",
                    model_table, e,
                )
                conn.rollback()
                model_forecast = pd.read_sql(text(
                    f"SELECT * FROM {model_table}"
                    f" WHERE date::timestamp >= :start_dt AND date::timestamp <= :end_dt"
                ), con=conn, params=sq)
                price_cols = [c for c in model_forecast.columns
                              if 'price' in c.lower() or 'forecast' in c.lower()]
                if price_cols:
                    model_forecast = model_forecast[['date', price_cols[0]]].rename(
                        columns={price_cols[0]: 'best_price'})
                else:
                    num_cols = model_forecast.select_dtypes(include=['number']).columns.tolist()
                    if num_cols:
                        model_forecast = model_forecast[['date', num_cols[0]]].rename(
                            columns={num_cols[0]: 'best_price'})

            cemre_forecast = pd.read_sql(text(
                f"SELECT date, forecasted_price AS cemre_forecast FROM {cemre_table}"
                f" WHERE date >= :start_dt AND date <= :end_dt"
            ), con=conn, params=sq)

        ptf_df              = _parse_dates(ptf_df)
        meteologica_forecast = _parse_dates(meteologica_forecast)
        model_forecast      = _parse_dates(model_forecast) if not model_forecast.empty else model_forecast
        cemre_forecast      = _parse_dates(cemre_forecast) if not cemre_forecast.empty else cemre_forecast

        ptf_df['actual_price'] = ptf_df['actual_price'].apply(lambda x: 1 if x <= 0 else x)

        price_df = pd.merge(ptf_df, meteologica_forecast, on='date', how='outer').sort_values(by='date')
        price_df = pd.merge(price_df, model_forecast, on='date', how='left')
        if not cemre_forecast.empty:
            price_df = pd.merge(price_df, cemre_forecast, on='date', how='left')
        
        # Remove rows with missing actual prices for evaluation
        evaluation_df = price_df.dropna(subset=['actual_price']).copy()
        
        if evaluation_df.empty:
            return jsonify({
                'error': 'No data available with actual prices for evaluation period'
            }), 404
        
        # Calculate forecast metrics using numpy only
        def calculate_darts_metrics(actual_series, forecast_series):
            try:
                actual_clean = actual_series.dropna()
                forecast_clean = forecast_series[actual_clean.index].dropna()
                if len(forecast_clean) == 0 or len(actual_clean) == 0:
                    return {'wmape': 0, 'rmse': 0, 'r2': 0}
                common_indices = actual_clean.index.intersection(forecast_clean.index)
                if len(common_indices) == 0:
                    return {'wmape': 0, 'rmse': 0, 'r2': 0}
                a = actual_clean[common_indices].values.astype(float)
                f = forecast_clean[common_indices].values.astype(float)
                denom = np.sum(np.abs(a))
                wmape_score = float(np.sum(np.abs(a - f)) / denom * 100) if denom != 0 else 0
                rmse_score  = float(np.sqrt(np.mean((a - f) ** 2)))
                ss_res = np.sum((a - f) ** 2)
                ss_tot = np.sum((a - np.mean(a)) ** 2)
                r2_score_value = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0
                return {
                    'wmape': round(wmape_score, 2),
                    'rmse':  round(rmse_score, 2),
                    'r2':    round(r2_score_value, 2),
                }
            except Exception as e:
                current_app.logger.error(f"Error in calculate_darts_metrics: {e}", exc_info=True)
                return {'wmape': 0, 'rmse': 0, 'r2': 0}
        
        # Prepare response data
        response_data = {
            'dates': evaluation_df['date'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            'actual_price': evaluation_df['actual_price'].fillna(0).tolist(),
            'meteologica_min': evaluation_df['meteologica_min'].fillna(0).tolist(),
            'meteologica_avg': evaluation_df['meteologica_avg'].fillna(0).tolist(),
            'meteologica_max': evaluation_df['meteologica_max'].fillna(0).tolist(),
            'model_forecast': evaluation_df['best_price'].fillna(0).tolist() if 'best_price' in evaluation_df.columns else [],
            'cemre_forecast': evaluation_df['cemre_forecast'].fillna(0).tolist() if 'cemre_forecast' in evaluation_df.columns else [],
            'period_info': period_info,
            'data_points': len(evaluation_df),
            'forecast_horizon': forecast_horizon
        }
        
        # Calculate metrics only for series with data
        metrics = {}
        actual_series = evaluation_df['actual_price']
        
        if not actual_series.dropna().empty:
            # Define models to evaluate - automatically detect available columns
            models_to_evaluate = [
                ('meteologica_min', 'Meteologica Min'),
                ('meteologica_avg', 'Meteologica Avg'),
                ('meteologica_max', 'Meteologica Max'),
                ('best_price', 'Model Forecast'),
                ('cemre_forecast', 'Cemre Forecast'),
                # Add new models here - format: ('column_name', 'Display Name')
                # Example: ('xgboost_price', 'XGBoost Model'),
                # Example: ('prophet_price', 'Prophet Model'),
                # Example: ('ensemble_price', 'Ensemble Model'),
            ]
            
            for col, name in models_to_evaluate:
                if col in evaluation_df.columns and not evaluation_df[col].dropna().empty:
                    try:
                        metrics[name] = calculate_darts_metrics(actual_series, evaluation_df[col])
                    except Exception as e:
                        current_app.logger.warning(f"Error calculating metrics for {name}: {e}")
                        metrics[name] = {'wmape': 0, 'rmse': 0, 'r2': 0}
        
        response_data['metrics'] = metrics
        
        return jsonify({
            'code': 200,
            'data': response_data
        })
        
    except Exception as e:
        return api_error("get_forecast_performance_data", e)


@forecast_performance_bp.route('/download-forecast-performance-excel')
@login_required
def download_forecast_performance_excel():
    """Download forecast performance data as Excel file"""
    try:
        from io import BytesIO
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        
        # Get parameters from request
        period_days = request.args.get('period', '30', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        forecast_horizon = request.args.get('horizon', 'd+1')
        
        engine = get_supabase_engine()

        if start_date and end_date:
            start_dt = pd.to_datetime(start_date)
            end_dt   = pd.to_datetime(end_date)
        else:
            end_dt   = pd.Timestamp.now()
            start_dt = end_dt - pd.Timedelta(days=period_days)

        sq = {"start_dt": start_dt, "end_dt": end_dt}

        if forecast_horizon.lower() == 'd+2':
            met_table   = 'public."meteologica_forecast_d+2"'
            model_table = 'public.model_forecast_sfc'
            cemre_table = 'public."cemre_ptf_d+2"'
        else:
            met_table   = 'public.meteologica_forecast'
            model_table = 'public.model_forecast_ptf'
            cemre_table = 'public."cemre_ptf_d+1"'

        def _parse_dates(df):
            if not df.empty and not pd.api.types.is_datetime64_any_dtype(df['date']):
                df['date'] = df['date'].apply(
                    lambda x: str(x).split('+')[0].replace('T', ' ') if isinstance(x, str) else x
                )
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
            return df

        with engine.connect() as conn:
            ptf_df = pd.read_sql(text(
                "SELECT date, price AS actual_price FROM epias.ptf"
                " WHERE date >= :start_dt AND date <= :end_dt"
            ), con=conn, params=sq)

            if ptf_df.empty:
                return jsonify({'error': 'No PTF data available'}), 404

            meteologica_forecast = pd.read_sql(text(
                f"SELECT date, min_price AS meteologica_min,"
                f" avg_price AS meteologica_avg, max_price AS meteologica_max"
                f" FROM {met_table} WHERE date::timestamp >= :start_dt AND date::timestamp <= :end_dt"
            ), con=conn, params=sq)

            try:
                model_forecast = pd.read_sql(text(
                    f"SELECT date, best_price FROM {model_table}"
                    f" WHERE date::timestamp >= :start_dt AND date::timestamp <= :end_dt"
                ), con=conn, params=sq)
            except Exception as e:
                current_app.logger.warning(
                    "Forecast query SELECT date,best_price failed for %r (%s); falling back to SELECT *",
                    model_table, e,
                )
                conn.rollback()
                model_forecast = pd.read_sql(text(
                    f"SELECT * FROM {model_table}"
                    f" WHERE date::timestamp >= :start_dt AND date::timestamp <= :end_dt"
                ), con=conn, params=sq)
                price_cols = [c for c in model_forecast.columns
                              if 'price' in c.lower() or 'forecast' in c.lower()]
                if price_cols:
                    model_forecast = model_forecast[['date', price_cols[0]]].rename(
                        columns={price_cols[0]: 'best_price'})

            cemre_forecast = pd.read_sql(text(
                f"SELECT date, forecasted_price AS cemre_forecast FROM {cemre_table}"
                f" WHERE date >= :start_dt AND date <= :end_dt"
            ), con=conn, params=sq)

        ptf_df              = _parse_dates(ptf_df)
        meteologica_forecast = _parse_dates(meteologica_forecast)
        model_forecast      = _parse_dates(model_forecast)
        cemre_forecast      = _parse_dates(cemre_forecast)

        ptf_df['actual_price'] = ptf_df['actual_price'].apply(lambda x: 1 if x <= 0 else x)

        price_df = pd.merge(ptf_df, meteologica_forecast, on='date', how='outer').sort_values(by='date')
        price_df = pd.merge(price_df, model_forecast, on='date', how='left')
        if not cemre_forecast.empty:
            price_df = pd.merge(price_df, cemre_forecast, on='date', how='left')

        # Prepare data for Excel
        evaluation_df = price_df.dropna(subset=['actual_price']).copy()
        
        # Create Excel workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Forecast Performance"
        
        # Define styles
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Write headers
        headers = ['Date', 'Realized Price (TL/MWh)', 'Meteologica Min', 'Meteologica Avg', 
                   'Meteologica Max', 'Model Forecast', 'Cemre Forecast']
        
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = border
        
        # Write data
        for row_num, row_data in enumerate(evaluation_df.itertuples(index=False), 2):
            ws.cell(row=row_num, column=1, value=row_data.date.strftime('%Y-%m-%d %H:%M:%S')).border = border
            ws.cell(row=row_num, column=2, value=round(row_data.actual_price, 2) if pd.notna(row_data.actual_price) else 0).border = border
            ws.cell(row=row_num, column=3, value=round(row_data.meteologica_min, 2) if pd.notna(row_data.meteologica_min) else 0).border = border
            ws.cell(row=row_num, column=4, value=round(row_data.meteologica_avg, 2) if pd.notna(row_data.meteologica_avg) else 0).border = border
            ws.cell(row=row_num, column=5, value=round(row_data.meteologica_max, 2) if pd.notna(row_data.meteologica_max) else 0).border = border
            ws.cell(row=row_num, column=6, value=round(row_data.best_price, 2) if 'best_price' in evaluation_df.columns and pd.notna(row_data.best_price) else 0).border = border
            ws.cell(row=row_num, column=7, value=round(row_data.cemre_forecast, 2) if 'cemre_forecast' in evaluation_df.columns and pd.notna(row_data.cemre_forecast) else 0).border = border
        
        # Auto-adjust column widths
        for col_num in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col_num)].width = 20
        
        # Save to BytesIO
        excel_file = BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)
        
        # Generate filename
        filename = f"forecast_performance_{forecast_horizon}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return send_file(
            excel_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return api_error("download_forecast_performance_excel", e)
