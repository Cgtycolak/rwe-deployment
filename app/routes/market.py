"""Market prices: the home page tables, SFC Price and Supply Demand Price tabs."""
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from ..functions import login_required
import pandas as pd
import pytz
from sqlalchemy import text
from ..services.epias import epias_session
from .common import api_error
from ..database.supabase import get_supabase_engine

market_bp = Blueprint('market', __name__)


@market_bp.route('/get_sfc_chart_data', methods=['POST'])
@login_required
def get_sfc_chart_data():
    """SFC (Secondary Frequency Capacity) price for the line chart + heatmap views.

    Source is the same EPİAS transparency endpoint as /get_sfc_data, but fetched
    for an arbitrary date range so we can render the Databricks-style visuals
    natively. Returns both a flat time series (for the line chart) and an
    hour x date pivot matrix (for the heatmap).
    Body: {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"} or {"days": 14}.
    """
    try:
        tz = pytz.timezone('Europe/Istanbul')
        now = datetime.now(tz)
        body = request.get_json(silent=True) or {}

        # Resolve date range: explicit start/end wins, else last N days (default 14)
        if body.get('start_date') and body.get('end_date'):
            start_dt = datetime.strptime(body['start_date'], '%Y-%m-%d')
            end_dt = datetime.strptime(body['end_date'], '%Y-%m-%d')
        else:
            days = int(body.get('days', 14))
            end_dt = now
            start_dt = now - timedelta(days=days - 1)

        start_date = start_dt.strftime("%Y-%m-%dT00:00:00+03:00")
        end_date = end_dt.strftime("%Y-%m-%dT23:59:59+03:00")

        with epias_session(total=3, backoff_factor=0.5) as session:
            response = session.post(
                'https://seffaflik.epias.com.tr/electricity-service/v1/markets/ancillary-services/data/secondary-frequency-capacity-price',
                json={"startDate": start_date, "endDate": end_date},
                timeout=60,
            )
            response.raise_for_status()

        payload = response.json()
        items = payload.get('items', [])

        hours = [f"{str(h).zfill(2)}:00" for h in range(24)]
        series = []
        pivot = {}        # 'YYYY-MM-DD' -> {hour_int: price}
        date_order = []   # chronological list of date keys

        for item in items:
            dt = datetime.strptime(item['date'], '%Y-%m-%dT%H:%M:%S+03:00')
            date_key = dt.strftime('%Y-%m-%d')
            hour_int = dt.hour
            price = item.get('price')
            series.append({
                'datetime': f"{date_key} {str(hour_int).zfill(2)}:00",
                'value': price
            })
            if date_key not in pivot:
                pivot[date_key] = {}
                date_order.append(date_key)
            pivot[date_key][hour_int] = price

        # Heatmap matrix: 24 rows (hours) x N columns (dates, chronological)
        values = [[pivot.get(d, {}).get(h) for d in date_order] for h in range(24)]
        date_labels = [datetime.strptime(d, '%Y-%m-%d').strftime('%d %b %Y') for d in date_order]

        # Also fetch MCP (Market Clearing Price / PTF) for the same range — shown as
        # the line chart next to the SFC heatmap. Wrapped separately so an MCP failure
        # doesn't take down the SFC heatmap.
        mcp_series = []
        try:
            with epias_session(total=3, backoff_factor=0.5) as mcp_session:
                mcp_response = mcp_session.post(
                    'https://seffaflik.epias.com.tr/electricity-service/v1/markets/dam/data/mcp',
                    # The MCP endpoint reads endDate as a day; an end-of-day time such as
                    # 23:59:59 on today is rejected before 14:00 (SEF1124), midnight is not
                    json={"startDate": start_date, "endDate": end_dt.strftime("%Y-%m-%dT00:00:00+03:00")},
                        timeout=60,
                )
                mcp_response.raise_for_status()
            for item in mcp_response.json().get('items', []):
                dt = datetime.strptime(item['date'], '%Y-%m-%dT%H:%M:%S+03:00')
                mcp_series.append({
                    'datetime': f"{dt.strftime('%Y-%m-%d')} {str(dt.hour).zfill(2)}:00",
                    'value': item.get('price')
                })
        except Exception as mcp_err:
            current_app.logger.warning(f"MCP fetch failed in get_sfc_chart_data: {mcp_err}")

        return jsonify({
            'code': 200,
            'data': {
                'series': series,
                'mcp_series': mcp_series,
                'heatmap': {
                    'hours': hours,
                    'dates': date_labels,
                    'values': values
                },
                'average': payload.get('statistics', {}).get('priceAvg', 0)
            }
        })
    except Exception as e:
        return api_error("get_sfc_chart_data", e)


@market_bp.route('/get_all_table_data', methods=['GET'])
@login_required
def get_all_table_data():
    try:
        # Get current time in Turkey timezone
        tz = pytz.timezone('Europe/Istanbul')
        current_time = datetime.now(tz)
        
        # Prepare dates for different endpoints
        yesterday = current_time - timedelta(days=1)
        tomorrow = current_time + timedelta(days=1)
        two_days_after = current_time + timedelta(days=2)

        with epias_session(total=3, backoff_factor=0.5) as session:

            order_summary_response = session.post(
                'https://seffaflik.epias.com.tr/electricity-service/v1/markets/bpm/data/order-summary-up',
                json={
                    "startDate": yesterday.strftime("%Y-%m-%dT00:00:00+03:00"),
                    "endDate": tomorrow.strftime("%Y-%m-%dT23:59:59+03:00")
                },
                timeout=30,
            )

            smp_response = session.post(
                'https://seffaflik.epias.com.tr/electricity-service/v1/markets/bpm/data/system-marginal-price',
                json={
                    "startDate": yesterday.strftime("%Y-%m-%dT00:00:00+03:00"),
                    "endDate": yesterday.strftime("%Y-%m-%dT23:59:59+03:00")
                },
                timeout=30,
            )

            pfc_response = session.post(
                'https://seffaflik.epias.com.tr/electricity-service/v1/markets/ancillary-services/data/primary-frequency-capacity-price',
                json={
                    "startDate": current_time.strftime("%Y-%m-%dT00:00:00+03:00"),
                    "endDate": two_days_after.strftime("%Y-%m-%dT23:59:59+03:00")
                },
                timeout=30,
            )

            sfc_response = session.post(
                'https://seffaflik.epias.com.tr/electricity-service/v1/markets/ancillary-services/data/secondary-frequency-capacity-price',
                json={
                    "startDate": current_time.strftime("%Y-%m-%dT00:00:00+03:00"),
                    "endDate": two_days_after.strftime("%Y-%m-%dT23:59:59+03:00")
                },
                timeout=30,
            )
        
        # Process order summary data
        order_data = order_summary_response.json().get('items', [])
        cutoff_time = current_time - timedelta(hours=4)
        order_summary = []
        
        for item in order_data:
            item_datetime = datetime.strptime(item['date'], "%Y-%m-%dT%H:%M:%S+03:00")
            item_datetime = tz.localize(item_datetime)
            if item_datetime <= cutoff_time:
                order_summary.append({
                    'datetime': f"{item_datetime.strftime('%Y-%m-%d')} {item['hour']}",
                    'value': item['net']
                })
        
        # Process SMP data
        smp_data = smp_response.json()
        smp_processed = [{
            'datetime': f"{datetime.strptime(item['date'], '%Y-%m-%dT%H:%M:%S+03:00').strftime('%Y-%m-%d')} {datetime.strptime(item['date'], '%Y-%m-%dT%H:%M:%S+03:00').strftime('%H:%M')}",
            'value': item['systemMarginalPrice']
        } for item in smp_data.get('items', [])]
        
        # Process PFC data
        pfc_data = pfc_response.json()
        pfc_processed = [{
            'datetime': f"{datetime.strptime(item['date'], '%Y-%m-%dT%H:%M:%S+03:00').strftime('%Y-%m-%d')} {str(item['hour']).zfill(2)}:00",
            'value': item['price']
        } for item in pfc_data.get('items', [])]
        
        # Process SFC data
        sfc_data = sfc_response.json()
        sfc_processed = [{
            'datetime': f"{datetime.strptime(item['date'], '%Y-%m-%dT%H:%M:%S+03:00').strftime('%Y-%m-%d')} {str(item['hour']).zfill(2)}:00",
            'value': item['price']
        } for item in sfc_data.get('items', [])]
        
        return jsonify({
            'code': 200,
            'data': {
                'orderSummary': order_summary,
                'smp': {
                    'data': smp_processed,
                    'average': smp_data.get('statistics', {}).get('smpArithmeticalAverage', 0)
                },
                'pfc': {
                    'data': pfc_processed,
                    'average': pfc_data.get('statistics', {}).get('priceAvg', 0)
                },
                'sfc': {
                    'data': sfc_processed,
                    'average': sfc_data.get('statistics', {}).get('priceAvg', 0)
                }
            }
        })
        
    except Exception as e:
        return api_error("get_all_table_data", e)


@market_bp.route('/api/supply_demand_price', methods=['GET'])
@login_required
def get_supply_demand_price():
    try:
        selected_date = request.args.get('date')
        diff_filter_threshold = float(request.args.get('threshold', 50))

        if not selected_date:
            return jsonify({'error': 'Date parameter is required'}), 400

        try:
            selected_date_parsed = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Date must be in YYYY-MM-DD format'}), 400

        engine_sb = get_supabase_engine()

        query = text(
            """
            WITH base AS (
                SELECT *,
                       supply + demand AS total,
                       LAG(supply + demand, 1) OVER (ORDER BY date, price) AS lag_total,
                       (LAG(supply + demand, 1) OVER (ORDER BY date, price)) - (supply + demand) AS diff
                FROM epias.supply_demand
                ORDER BY date, price
            ),
            aggregated AS (
                SELECT
                    DATE(date) AS trade_date,
                    price,
                    EXTRACT(HOUR FROM date) AS hour,
                    AVG(total) AS avg_total,
                    AVG(diff) AS avg_diff
                FROM base
                WHERE DATE(date) = :selected_date
                GROUP BY DATE(date), price, EXTRACT(HOUR FROM date)
            )
            SELECT
                trade_date,
                price,
                SUM(CASE WHEN hour = 0  THEN avg_diff ELSE 0 END) AS "00:00",
                SUM(CASE WHEN hour = 1  THEN avg_diff ELSE 0 END) AS "01:00",
                SUM(CASE WHEN hour = 2  THEN avg_diff ELSE 0 END) AS "02:00",
                SUM(CASE WHEN hour = 3  THEN avg_diff ELSE 0 END) AS "03:00",
                SUM(CASE WHEN hour = 4  THEN avg_diff ELSE 0 END) AS "04:00",
                SUM(CASE WHEN hour = 5  THEN avg_diff ELSE 0 END) AS "05:00",
                SUM(CASE WHEN hour = 6  THEN avg_diff ELSE 0 END) AS "06:00",
                SUM(CASE WHEN hour = 7  THEN avg_diff ELSE 0 END) AS "07:00",
                SUM(CASE WHEN hour = 8  THEN avg_diff ELSE 0 END) AS "08:00",
                SUM(CASE WHEN hour = 9  THEN avg_diff ELSE 0 END) AS "09:00",
                SUM(CASE WHEN hour = 10 THEN avg_diff ELSE 0 END) AS "10:00",
                SUM(CASE WHEN hour = 11 THEN avg_diff ELSE 0 END) AS "11:00",
                SUM(CASE WHEN hour = 12 THEN avg_diff ELSE 0 END) AS "12:00",
                SUM(CASE WHEN hour = 13 THEN avg_diff ELSE 0 END) AS "13:00",
                SUM(CASE WHEN hour = 14 THEN avg_diff ELSE 0 END) AS "14:00",
                SUM(CASE WHEN hour = 15 THEN avg_diff ELSE 0 END) AS "15:00",
                SUM(CASE WHEN hour = 16 THEN avg_diff ELSE 0 END) AS "16:00",
                SUM(CASE WHEN hour = 17 THEN avg_diff ELSE 0 END) AS "17:00",
                SUM(CASE WHEN hour = 18 THEN avg_diff ELSE 0 END) AS "18:00",
                SUM(CASE WHEN hour = 19 THEN avg_diff ELSE 0 END) AS "19:00",
                SUM(CASE WHEN hour = 20 THEN avg_diff ELSE 0 END) AS "20:00",
                SUM(CASE WHEN hour = 21 THEN avg_diff ELSE 0 END) AS "21:00",
                SUM(CASE WHEN hour = 22 THEN avg_diff ELSE 0 END) AS "22:00",
                SUM(CASE WHEN hour = 23 THEN avg_diff ELSE 0 END) AS "23:00"
            FROM aggregated
            GROUP BY trade_date, price
            ORDER BY trade_date, price
            """
        )

        with engine_sb.connect() as conn:
            df = pd.read_sql(query, con=conn, params={"selected_date": selected_date_parsed})

        hour_cols = [col for col in df.columns if col.endswith(':00')]

        # Filter rows where any hourly diff > threshold
        filtered_df = df[(df[hour_cols] > diff_filter_threshold).any(axis=1)]

        if filtered_df.empty:
            return jsonify({'rows': [], 'hour_cols': hour_cols, 'threshold': diff_filter_threshold})

        prices = filtered_df['price'].tolist()
        min_price = min(prices)
        max_price = max(prices)

        rows = []
        for _, row in filtered_df.iterrows():
            hour_values = {}
            for col in hour_cols:
                val = float(row[col])
                hour_values[col] = round(val, 4)

            rows.append({
                'trade_date': str(row['trade_date']),
                'price': float(row['price']),
                'hours': hour_values
            })

        # Fetch PTF prices for the selected date
        ptf_query = text(
            f"""
            SELECT EXTRACT(HOUR FROM date) AS hour, AVG(price) AS ptf_price
            FROM epias.ptf
            WHERE DATE(date) = '{selected_date}'
            GROUP BY EXTRACT(HOUR FROM date)
            ORDER BY hour
            """
        )
        ptf_by_hour = {}
        try:
            with engine_sb.connect() as conn:
                ptf_df = pd.read_sql(ptf_query, con=conn)
            for _, r in ptf_df.iterrows():
                h = int(r['hour'])
                ptf_by_hour[f"{h:02d}:00"] = round(float(r['ptf_price']), 2)
        except Exception as ptf_err:
            current_app.logger.warning(f"PTF fetch warning: {ptf_err}")

        ptf_row = [ptf_by_hour.get(col, None) for col in hour_cols]

        return jsonify({
            'rows': rows,
            'hour_cols': hour_cols,
            'threshold': diff_filter_threshold,
            'min_price': min_price,
            'max_price': max_price,
            'ptf_row': ptf_row
        })

    except Exception as e:
        return api_error("get_supply_demand_price", e)
