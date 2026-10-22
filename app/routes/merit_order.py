"""Merit Order tab."""
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app, send_file
from ..functions import login_required
import pandas as pd
import pytz
from sqlalchemy import text, bindparam
import os
from ..services.epias import epias_session
from .common import api_error
from ..database.supabase import get_supabase_engine

merit_order_bp = Blueprint('merit_order', __name__)


# Default section boundaries: h00–h07, h08–h15 and h16–h23.
MERIT_ORDER_DEFAULT_BOUNDARIES = (8, 16)


def _parse_merit_order_splits(args):
    """Turn the b1/b2 boundaries from request args or a JSON body into sections.

    b1 and b2 are hours in [0, 24] where a new section starts, so the day splits
    into [0, b1), [b1, b2) and [b2, 24). Sections left empty are dropped: moving
    a boundary onto an edge or onto the other boundary merges sections, and
    with both at the edges the whole day is a single section. Returns
    inclusive (from_hour, to_hour) pairs; raises ValueError on bad boundaries.
    """
    b1 = int(args.get('b1', MERIT_ORDER_DEFAULT_BOUNDARIES[0]))
    b2 = int(args.get('b2', MERIT_ORDER_DEFAULT_BOUNDARIES[1]))
    if not (0 <= b1 <= b2 <= 24):
        raise ValueError('Section boundaries must satisfy 0 <= b1 <= b2 <= 24')
    edges = [0, b1, b2, 24]
    return [(start, end - 1) for start, end in zip(edges, edges[1:]) if end > start]


def _parse_merit_order_ref_dates(args, sections):
    """Map each hour label ('HH:MM') to the reference date of its section.

    gen_dates carries one date per section (comma-separated, or a list in a JSON
    body). A single gen_date is still accepted and applied to the whole day.
    Returns (dates per section, {hour label: date}).
    """
    raw = args.get('gen_dates')
    if raw:
        dates = raw if isinstance(raw, list) else raw.split(',')
    elif args.get('gen_date'):
        dates = [args.get('gen_date')] * len(sections)
    else:
        raise ValueError('gen_dates is required')

    if len(dates) != len(sections):
        raise ValueError(f'gen_dates needs one date per section ({len(sections)})')

    parsed = [datetime.strptime(str(d).strip(), '%Y-%m-%d').date() for d in dates]
    ref_by_hour = {}
    for (from_hour, to_hour), ref_date in zip(sections, parsed):
        for h in range(from_hour, to_hour + 1):
            ref_by_hour[f'{h:02d}:00'] = ref_date
    return parsed, ref_by_hour


def _rows_for_ref_dates(df, ref_by_hour, day_col):
    """Keep, for every hour, only the rows that come from that hour's reference date.

    The reference queries load all the section dates at once; this stitches the
    day back together so each section is compared against its own date.
    """
    row_dates = pd.to_datetime(df[day_col]).dt.date
    return df[row_dates.values == df['hour'].map(ref_by_hour).values]


def _calculate_merit_order_price(supply_demand_df, capacity_deltas):
    """Calculate merit order prices by shifting supply/demand intersection by capacity deltas.
    
    Args:
        supply_demand_df: DataFrame with columns [date, hour, price, supply, demand, capacity(Δ)]
        capacity_deltas: list of capacity delta values, one per hour
    
    Returns:
        list of forecast price points
    """
    forecast_data = []
    hours_unique = supply_demand_df['hour'].unique()
    
    for hour_code, hour_idx in zip(hours_unique, range(len(hours_unique))):
        if hour_idx >= len(capacity_deltas):
            break
            
        hourly_data = supply_demand_df[supply_demand_df['hour'] == hour_code].sort_values(by='price')
        
        if hourly_data.empty:
            continue
        
        trade_capacity = hourly_data.loc[hourly_data['capacity(Δ)'].abs().idxmin(), 'capacity(Δ)']
        required_capacity = capacity_deltas[hour_idx]
        
        try:
            if (trade_capacity - required_capacity) < hourly_data['capacity(Δ)'].min():
                new_price_point = hourly_data[hourly_data['capacity(Δ)'] >= (trade_capacity - required_capacity)].iloc[-1]
            else:
                new_price_point = hourly_data[hourly_data['capacity(Δ)'] <= (trade_capacity - required_capacity)].iloc[0]
            
            forecast_data.append(new_price_point)
        except (IndexError, KeyError):
            # If no matching price point found, use the closest one
            forecast_data.append(hourly_data.loc[hourly_data['capacity(Δ)'].sub(trade_capacity - required_capacity).abs().idxmin()])
    
    return forecast_data


@merit_order_bp.route('/merit-order-data')
@login_required
def get_merit_order_data():
    """Get merit order comparison data for a prediction date.

    The day is split into up to three sections (b1/b2 boundaries) and each section
    is compared against its own reference date (gen_dates), so the result table is
    stitched together from up to three different historical days.
    """
    try:
        pred_date = request.args.get('pred_date')

        if not pred_date:
            return jsonify({'code': 400, 'message': 'pred_date is required'}), 400

        try:
            pred_date_parsed = datetime.strptime(pred_date, '%Y-%m-%d').date()
            sections = _parse_merit_order_splits(request.args)
            ref_dates, ref_by_hour = _parse_merit_order_ref_dates(request.args, sections)
        except ValueError as e:
            return jsonify({'code': 400, 'message': str(e)}), 400

        engine = get_supabase_engine()

        # Reference query — historical forecast data
        ref_query = text("""
        SELECT
            hf.date AS date,
            DATE(hf.date) AS day,
            TO_CHAR(hf.date, 'HH24:MI') AS hour,
            ptf.price AS mcp_ref,
            hf.demand_forecast AS demand,
            hf.wind_forecast AS wind,
            hf.licensed_solar_forecast + hf.unlicensed_solar_forecast AS solar,
            hf.runofriver_forecast AS river
        FROM meteologica.historical_forecast hf
        JOIN epias.ptf ptf ON ptf.date = hf.date
        WHERE DATE(hf.date) IN :gen_dates
        ORDER BY hf.date
        """).bindparams(bindparam('gen_dates', expanding=True))

        # Prediction query — current forecast data
        pred_query = text("""
        SELECT
            CAST(d."From-yyyy-mm-dd-hh-mm" AS TIMESTAMP) AS date,
            DATE(CAST(d."From-yyyy-mm-dd-hh-mm" AS TIMESTAMP)) AS day,
            TO_CHAR(CAST(d."From-yyyy-mm-dd-hh-mm" AS TIMESTAMP), 'HH24:MI') AS hour,
            p.price_forecast AS mcp_pred,
            d.demand_forecast AS demand,
            w.wind_forecast AS wind,
            ls.licensed_forecast + us.unlicensed_forecast AS solar,
            ror.runofriver_forecast AS river
        FROM meteologica.demand d
        JOIN meteologica.price p ON TO_TIMESTAMP(d."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI') = TO_TIMESTAMP(p."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI')
        JOIN meteologica.wind w ON TO_TIMESTAMP(d."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI') = TO_TIMESTAMP(w."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI')
        JOIN meteologica.licensed_solar ls ON TO_TIMESTAMP(d."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI') = TO_TIMESTAMP(ls."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI')
        JOIN meteologica.unlicensed_solar us ON TO_TIMESTAMP(d."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI') = TO_TIMESTAMP(us."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI')
        JOIN meteologica.runofriver_hydro ror ON TO_TIMESTAMP(d."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI') = TO_TIMESTAMP(ror."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI')
        WHERE DATE(CAST(d."From-yyyy-mm-dd-hh-mm" AS TIMESTAMP)) = :pred_date
        ORDER BY date
        """)

        # Supply/demand curve for reference date (for merit order price calculation)
        supply_demand_query = text("""
        SELECT date, TO_CHAR(date, 'HH24:MI') AS hour, price, supply, demand
        FROM epias.supply_demand
        WHERE DATE(date) IN :gen_dates
        ORDER BY date, price
        """).bindparams(bindparam('gen_dates', expanding=True))

        with engine.connect() as conn:
            unique_ref_dates = sorted(set(ref_dates))
            ref_df = pd.read_sql(ref_query, con=conn, params={"gen_dates": unique_ref_dates})
            pred_df = pd.read_sql(pred_query, con=conn, params={"pred_date": pred_date_parsed})
            pred_df['day'] = pd.to_datetime(pred_df['day'])
            pred_df['mcp_pred'] = pred_df['mcp_pred'].round(2)
            supply_demand_df = pd.read_sql(supply_demand_query, con=conn, params={"gen_dates": unique_ref_dates})

        ref_df = _rows_for_ref_dates(ref_df, ref_by_hour, 'day')
        # The query orders by date, which interleaves sections once they come from
        # different days; the price calculation walks the curves in hour order.
        supply_demand_df = (_rows_for_ref_dates(supply_demand_df, ref_by_hour, 'date')
                            .sort_values(['hour', 'price']).reset_index(drop=True))

        missing = sorted({d.isoformat() for d in ref_dates} - {d.isoformat() for d in pd.to_datetime(ref_df['day']).dt.date})
        if missing:
            return jsonify({'code': 404, 'message': f'No reference data found for {", ".join(missing)}'}), 404

        if pred_df.empty:
            return jsonify({'code': 404, 'message': f'No prediction data found for {pred_date}'}), 404

        # Merge on hour. Sorted so row order lines up with the hour order that
        # _calculate_merit_order_price walks the supply/demand curves in.
        cols = ['demand', 'river', 'wind', 'solar']
        df_diff = pd.merge(ref_df, pred_df, on='hour', suffixes=('_ref', '_pred'))
        df_diff = df_diff.sort_values('hour').reset_index(drop=True)
        
        # Calculate deltas
        for col in cols:
            df_diff[f'{col}_delta'] = df_diff[f'{col}_pred'] - df_diff[f'{col}_ref']
        
        # Calculate capacity delta
        df_diff['capacity_delta'] = (df_diff['demand_delta'] 
                                     - df_diff['river_delta'] - df_diff['wind_delta'] 
                                     - df_diff['solar_delta'])
        
        # Calculate merit order price from supply/demand curves
        mcp_merit_values = []
        if not supply_demand_df.empty:
            supply_demand_df['capacity(Δ)'] = supply_demand_df['demand'] + supply_demand_df['supply']
            capacity_deltas = df_diff['capacity_delta'].tolist()
            forecast_points = _calculate_merit_order_price(supply_demand_df, capacity_deltas)
            
            if len(forecast_points) == len(df_diff):
                forecast_prices_df = pd.concat(forecast_points, axis=1).T
                mcp_merit_values = forecast_prices_df['price'].tolist()
            
        # Build result rows
        result_rows = []
        for idx, row in df_diff.iterrows():
            result_rows.append({
                'date_ref': str(row['date_ref']),
                'date_pred': str(row['date_pred']),
                'mcp_ref': float(row['mcp_ref']) if pd.notna(row.get('mcp_ref')) else None,
                'mcp_merit': float(mcp_merit_values[idx]) if idx < len(mcp_merit_values) else None,
                'mcp_pred': float(row['mcp_pred']) if pd.notna(row.get('mcp_pred')) else None,
                'capacity_delta': float(row['capacity_delta']) if pd.notna(row['capacity_delta']) else None,
                'demand_ref': float(row['demand_ref']) if pd.notna(row['demand_ref']) else None,
                'demand_pred': float(row['demand_pred']) if pd.notna(row['demand_pred']) else None,
                'demand_delta': float(row['demand_delta']) if pd.notna(row['demand_delta']) else None,
                'river_ref': float(row['river_ref']) if pd.notna(row['river_ref']) else None,
                'river_pred': float(row['river_pred']) if pd.notna(row['river_pred']) else None,
                'river_delta': float(row['river_delta']) if pd.notna(row['river_delta']) else None,
                'wind_ref': float(row['wind_ref']) if pd.notna(row['wind_ref']) else None,
                'wind_pred': float(row['wind_pred']) if pd.notna(row['wind_pred']) else None,
                'wind_delta': float(row['wind_delta']) if pd.notna(row['wind_delta']) else None,
                'solar_ref': float(row['solar_ref']) if pd.notna(row['solar_ref']) else None,
                'solar_pred': float(row['solar_pred']) if pd.notna(row['solar_pred']) else None,
                'solar_delta': float(row['solar_delta']) if pd.notna(row['solar_delta']) else None,
            })
        
        # Summary row (totals - exclude mcp columns from sum)
        numeric_cols = ['capacity_delta', 'demand_ref', 'demand_pred', 'demand_delta',
                       'river_ref', 'river_pred', 'river_delta',
                       'wind_ref', 'wind_pred', 'wind_delta', 
                       'solar_ref', 'solar_pred', 'solar_delta']
        
        summary_row = {}
        for col in numeric_cols:
            summary_row[col] = float(df_diff[col].sum()) if col in df_diff.columns else None
        
        # Build supply/demand curve data for client-side MCP recalculation
        supply_demand_curves = {}
        if not supply_demand_df.empty:
            for hour_code in supply_demand_df['hour'].unique():
                hourly = supply_demand_df[supply_demand_df['hour'] == hour_code].sort_values(by='price')
                supply_demand_curves[hour_code] = {
                    'prices': hourly['price'].tolist(),
                    'capacities': hourly['capacity(Δ)'].tolist()
                }

        # Base capacity deltas (before any AIC adjustments)
        base_capacity_deltas = {}
        for _, row in df_diff.iterrows():
            base_capacity_deltas[row['hour']] = float(row['capacity_delta']) if pd.notna(row['capacity_delta']) else 0

        return jsonify({
            'code': 200,
            'data': {
                'gen_dates': [d.isoformat() for d in ref_dates],
                'sections': [{'from_hour': lo, 'to_hour': hi} for lo, hi in sections],
                'pred_date': pred_date,
                'columns': numeric_cols,
                'rows': result_rows,
                'summary_row': summary_row,
                'supply_demand_curves': supply_demand_curves,
                'base_capacity_deltas': base_capacity_deltas
            }
        })

    except Exception as e:
        return api_error("get_merit_order_data", e)


# How far back to look for comparable reference days, and how many to suggest.
MERIT_ORDER_SIMILAR_WINDOW_DAYS = 30
MERIT_ORDER_SIMILAR_LIMIT = 5


@merit_order_bp.route('/merit-order-similar-days')
@login_required
def get_merit_order_similar_days():
    """Suggest, for each section of the day, the reference dates whose hourly
    capacity profile is closest to the prediction date's over that section.

    Capacity is demand minus the must-run renewables (wind, solar, run-of-river) —
    the load the dispatchable fleet has to cover, i.e. the same expression behind
    ref_capacity/pred_capacity in the merit order queries.

    Days are ranked by the mean absolute hourly difference, not by the gap between
    daily averages: two days can average the same while one peaks in the morning
    and the other in the evening, and those produce quite different merit order
    curves. Comparing hour by hour matches the shape of the day, not just its level.

    The ranking is done separately per section (b1/b2 boundaries), because the
    day that matches the night best is often not the one that matches the solar
    hours or the evening peak. Candidates are limited to the same day type as the
    prediction date (weekday vs weekend), whose load profiles differ structurally.
    """
    try:
        pred_date = request.args.get('pred_date')
        if not pred_date:
            return jsonify({'code': 400, 'message': 'pred_date is required'}), 400

        try:
            pred_date_parsed = datetime.strptime(pred_date, '%Y-%m-%d').date()
            sections = _parse_merit_order_splits(request.args)
        except ValueError as e:
            return jsonify({'code': 400, 'message': str(e)}), 400

        start_date = pred_date_parsed - timedelta(days=MERIT_ORDER_SIMILAR_WINDOW_DAYS)

        engine = get_supabase_engine()

        # Hourly capacity for the prediction date. Kept to a single day: these joins
        # match on TO_TIMESTAMP of text columns, so no index applies and widening the
        # range makes the query unusably slow.
        pred_query = text("""
        SELECT
            TO_CHAR(CAST(d."From-yyyy-mm-dd-hh-mm" AS TIMESTAMP), 'HH24:MI') AS hour,
            d.demand_forecast - w.wind_forecast - ls.licensed_forecast
                - us.unlicensed_forecast - ror.runofriver_forecast AS pred_capacity
        FROM meteologica.demand d
        JOIN meteologica.wind w ON TO_TIMESTAMP(d."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI') = TO_TIMESTAMP(w."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI')
        JOIN meteologica.licensed_solar ls ON TO_TIMESTAMP(d."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI') = TO_TIMESTAMP(ls."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI')
        JOIN meteologica.unlicensed_solar us ON TO_TIMESTAMP(d."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI') = TO_TIMESTAMP(us."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI')
        JOIN meteologica.runofriver_hydro ror ON TO_TIMESTAMP(d."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI') = TO_TIMESTAMP(ror."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI')
        WHERE DATE(CAST(d."From-yyyy-mm-dd-hh-mm" AS TIMESTAMP)) = :pred_date
        ORDER BY 1
        """)

        # Hourly capacity across the window, restricted to days that actually carry
        # all 24 hours — a partially loaded day would otherwise be compared on a
        # handful of hours and rank spuriously well.
        # The prediction date is excluded from its own candidates: it would always
        # rank first and picking it as the reference makes every delta collapse to
        # zero, which tells you nothing about the merit order.
        # A day also needs its full PTF and supply/demand curves. The forecast for
        # tomorrow lands well before the day-ahead auction results, and a day
        # suggested without curves leaves MCP MERIT empty. This is a data check,
        # not a time cutoff, so tomorrow becomes a candidate as soon as its curves
        # are loaded.
        ref_query = text("""
        SELECT
            DATE(hf.date) AS day,
            TO_CHAR(hf.date, 'HH24:MI') AS hour,
            hf.demand_forecast - hf.wind_forecast - hf.licensed_solar_forecast
                - hf.unlicensed_solar_forecast - hf.runofriver_forecast AS ref_capacity
        FROM meteologica.historical_forecast hf
        WHERE DATE(hf.date) >= :start_date AND DATE(hf.date) < :pred_date
          AND DATE(hf.date) IN (
              SELECT DATE(date) FROM meteologica.historical_forecast
              WHERE DATE(date) >= :start_date AND DATE(date) < :pred_date
              GROUP BY DATE(date) HAVING COUNT(*) = 24
          )
          AND DATE(hf.date) IN (
              SELECT DATE(date) FROM epias.ptf
              WHERE DATE(date) >= :start_date AND DATE(date) < :pred_date
              GROUP BY DATE(date) HAVING COUNT(*) = 24
          )
          AND DATE(hf.date) IN (
              SELECT DATE(date) FROM epias.supply_demand
              WHERE DATE(date) >= :start_date AND DATE(date) < :pred_date
              GROUP BY DATE(date) HAVING COUNT(DISTINCT date) = 24
          )
        ORDER BY day, hour
        """)

        with engine.connect() as conn:
            pred_df = pd.read_sql(pred_query, con=conn, params={"pred_date": pred_date_parsed})
            ref_df = pd.read_sql(
                ref_query, con=conn,
                params={"start_date": start_date, "pred_date": pred_date_parsed}
            )

        if pred_df.empty or pred_df['pred_capacity'].isna().all():
            return jsonify({'code': 404, 'message': f'No prediction data found for {pred_date}'}), 404

        if ref_df.empty:
            return jsonify({
                'code': 404,
                'message': f'No complete reference days between {start_date} and {pred_date}'
            }), 404

        is_weekend = pred_date_parsed.weekday() >= 5
        ref_df = ref_df[(pd.to_datetime(ref_df['day']).dt.weekday >= 5) == is_weekend]

        if ref_df.empty:
            return jsonify({
                'code': 404,
                'message': f'No complete {"weekend" if is_weekend else "weekday"} reference days '
                           f'between {start_date} and {pred_date}'
            }), 404

        # Align on the hour label rather than row order, so a missing or reordered
        # hour cannot silently shift the comparison by one slot.
        merged = ref_df.merge(pred_df, on='hour', how='inner')
        merged['abs_diff'] = (merged['pred_capacity'] - merged['ref_capacity']).abs()
        merged['hour_num'] = merged['hour'].str[:2].astype(int)
        pred_df['hour_num'] = pred_df['hour'].str[:2].astype(int)

        section_results = []
        days_considered = 0
        for from_hour, to_hour in sections:
            n_hours = to_hour - from_hour + 1
            in_section = merged[merged['hour_num'].between(from_hour, to_hour)]

            per_day = in_section.groupby('day').agg(
                mean_diff=('abs_diff', 'mean'),
                ref_capacity=('ref_capacity', 'mean'),
                hours=('abs_diff', 'size'),
            ).reset_index()
            per_day = per_day[per_day['hours'] == n_hours]
            days_considered = max(days_considered, len(per_day))

            closest = per_day.nsmallest(MERIT_ORDER_SIMILAR_LIMIT, 'mean_diff')
            pred_section = pred_df[pred_df['hour_num'].between(from_hour, to_hour)]

            section_results.append({
                'from_hour': from_hour,
                'to_hour': to_hour,
                'pred_capacity_mean': float(pred_section['pred_capacity'].mean()),
                'days': [
                    {
                        'day': row['day'].isoformat(),
                        'ref_capacity': float(row['ref_capacity']),
                        'mean_diff': float(row['mean_diff']),
                    }
                    for _, row in closest.iterrows()
                ],
            })

        if not any(sec['days'] for sec in section_results):
            return jsonify({
                'code': 404,
                'message': f'No reference day overlaps the hours of {pred_date}'
            }), 404

        return jsonify({
            'code': 200,
            'data': {
                'pred_date': pred_date,
                'pred_capacity_mean': float(pred_df['pred_capacity'].mean()),
                'day_type': 'weekend' if is_weekend else 'weekday',
                'window_start': start_date.isoformat(),
                'window_days': MERIT_ORDER_SIMILAR_WINDOW_DAYS,
                'days_considered': int(days_considered),
                'sections': section_results,
            }
        })

    except Exception as e:
        return api_error("get_merit_order_similar_days", e)


AIC_URL = 'https://seffaflik.epias.com.tr/electricity-service/v1/generation/data/aic'


def _fetch_tracked_aic(session, uevcb, day_start):
    """Today's AIC rows for every unit in uevcb.xlsx, tagged with uevcbId. Returns (items, failed units)."""
    items, failures = [], 0
    for _, row in uevcb.iterrows():
        try:
            response = session.post(AIC_URL, timeout=15, headers={"Accept-Language": "en"}, json={
                "startDate": day_start.isoformat(),
                "endDate": day_start.isoformat(),
                "region": "TR1",
                "organizationId": int(row['organizationId']),
                "uevcbId": int(row['id'])
            })
            if response.status_code != 200:
                failures += 1
                continue
            unit_items = response.json().get("items", [])
            for item in unit_items:
                item["uevcbId"] = int(row['id'])
            items.extend(unit_items)
        except Exception as e:
            current_app.logger.warning(f"Error fetching AIC for {row['name']}: {e}")
            failures += 1
    return items, failures


@merit_order_bp.route('/merit-order-aic-data')
@login_required
def get_merit_order_aic_data():
    """Get AIC data for tracked power plants"""
    try:
        # Read the uevcb plant list
        uevcb_path = os.path.join(current_app.static_folder, 'data', 'uevcb.xlsx')
        if not os.path.exists(uevcb_path):
            return jsonify({'code': 404, 'error': 'UEVCB plant list file not found'}), 404
        
        uevcb = pd.read_excel(uevcb_path, sheet_name='Sheet2')
        
        # Use today's date for AIC
        tz = pytz.timezone('Europe/Istanbul')
        today_start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        
        with epias_session(total=3, backoff_factor=0.5) as session:
            org_response = session.post(
                'https://seffaflik.epias.com.tr/electricity-service/v1/generation/data/organization-list',
                json={
                    "startDate": today_start.isoformat(),
                    "endDate": today_start.isoformat()
                },
                headers={"Accept-Language": "en"},
                timeout=30
            )

            if org_response.status_code == 200:
                org_df = pd.DataFrame.from_records(org_response.json().get('items', []))
                if not org_df.empty:
                    uevcb = uevcb.merge(
                        org_df[['organizationId', 'organizationName']],
                        left_on="organizationId", right_on="organizationId", how="left"
                    )

            all_response, aic_fetch_failures = _fetch_tracked_aic(session, uevcb, today_start)

        if not all_response:
            return jsonify({'code': 404, 'message': 'No AIC data available'}), 404

        # Process AIC data into pivot table
        eak_df = pd.DataFrame.from_records(all_response)
        eak_df = eak_df[['date', 'uevcbId', 'toplam']].copy()
        eak_df = eak_df.merge(uevcb[["id", "name"]], left_on="uevcbId", right_on="id", how="left").drop(columns=['id', 'uevcbId'])

        eak_df['date'] = pd.to_datetime(eak_df['date'])
        eak_df['hour'] = eak_df['date'].dt.strftime('%H:%M')
        pivot_df = eak_df.pivot(index="name", columns="hour", values="toplam")
        pivot_df = pivot_df.fillna(0)

        base_date = today_start.strftime('%Y-%m-%d')

        return jsonify({
            'code': 200,
            'data': {
                'plants': pivot_df.index.tolist(),
                'hours': pivot_df.columns.tolist(),
                'values': pivot_df.values.tolist(),
                'base_date': base_date,
                'fetch_failures': aic_fetch_failures,
            }
        })
        
    except Exception as e:
        return api_error("get_merit_order_aic_data", e)


@merit_order_bp.route('/merit-order-failure-data')
@login_required
def get_merit_order_failure_data():
    """Get current power plant failure data from market messages"""
    try:
        engine = get_supabase_engine()

        failure_query = """
        SELECT 
            "uevcbName", 
            "caseStartDate", 
            "caseEndDate", 
            "operatorPower", 
            "capacityAtCaseTime",
            ROUND("operatorPower" - "capacityAtCaseTime") AS "failureAmount"
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY "uevcbName"
                       ORDER BY "caseEndDate" ASC
                   ) as row_num
            FROM epias.market_messages
            WHERE "caseEndDate" >= (CURRENT_TIMESTAMP + INTERVAL '3' HOUR)
        ) t
        WHERE t.row_num = 1
        ORDER BY "failureAmount" DESC
        """
        
        with engine.connect() as conn:
            failure_df = pd.read_sql(text(failure_query), con=conn)
        
        if failure_df.empty:
            return jsonify({'code': 200, 'data': {'rows': []}})
        
        # Convert to JSON-safe format
        rows = []
        for _, row in failure_df.iterrows():
            rows.append({
                'uevcbName': str(row['uevcbName']) if pd.notna(row['uevcbName']) else '',
                'caseStartDate': row['caseStartDate'].isoformat() if pd.notna(row['caseStartDate']) else None,
                'caseEndDate': row['caseEndDate'].isoformat() if pd.notna(row['caseEndDate']) else None,
                'operatorPower': float(row['operatorPower']) if pd.notna(row['operatorPower']) else None,
                'capacityAtCaseTime': float(row['capacityAtCaseTime']) if pd.notna(row['capacityAtCaseTime']) else None,
                'failureAmount': float(row['failureAmount']) if pd.notna(row['failureAmount']) else None,
            })
        
        return jsonify({
            'code': 200,
            'data': {
                'rows': rows
            }
        })
        
    except Exception as e:
        return api_error("get_merit_order_failure_data", e)


@merit_order_bp.route('/download-merit-order-excel', methods=['GET', 'POST'])
@login_required
def download_merit_order_excel():
    """Download merit order data as a multi-sheet Excel file.
    Accepts GET (no custom deltas) or POST with JSON body
    {gen_dates, b1, b2, pred_date, capacity_deltas}; see get_merit_order_data for
    how the sections and their reference dates combine.
    """
    try:
        from io import BytesIO

        if request.method == 'POST':
            args = request.get_json(force=True) or {}
            custom_capacity_deltas = args.get('capacity_deltas') or {}
        else:
            args = request.args
            custom_capacity_deltas = {}
        pred_date = args.get('pred_date')

        if not pred_date:
            return jsonify({'error': 'pred_date is required'}), 400

        try:
            pred_date_parsed = datetime.strptime(pred_date, '%Y-%m-%d').date()
            sections = _parse_merit_order_splits(args)
            ref_dates, ref_by_hour = _parse_merit_order_ref_dates(args, sections)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        unique_ref_dates = sorted(set(ref_dates))

        engine = get_supabase_engine()

        # --- Sheet 1: Results ---
        ref_query = text("""
        SELECT
            hf.date AS date,
            DATE(hf.date) AS day,
            TO_CHAR(hf.date, 'HH24:MI') AS hour,
            p.price_forecast AS mcp_ref,
            hf.demand_forecast AS demand,
            hf.wind_forecast AS wind,
            hf.licensed_solar_forecast + hf.unlicensed_solar_forecast AS solar,
            hf.runofriver_forecast AS river
        FROM meteologica.historical_forecast hf
        JOIN meteologica.price p ON TO_TIMESTAMP(p."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI:SI') = hf.date
        WHERE DATE(hf.date) IN :gen_dates
        ORDER BY hf.date
        """).bindparams(bindparam('gen_dates', expanding=True))

        pred_query = text("""
        SELECT
            CAST(d."From-yyyy-mm-dd-hh-mm" AS TIMESTAMP) AS date,
            DATE(CAST(d."From-yyyy-mm-dd-hh-mm" AS TIMESTAMP)) AS day,
            TO_CHAR(CAST(d."From-yyyy-mm-dd-hh-mm" AS TIMESTAMP), 'HH24:MI') AS hour,
            p.price_forecast AS mcp_pred,
            d.demand_forecast AS demand,
            w.wind_forecast AS wind,
            ls.licensed_forecast + us.unlicensed_forecast AS solar,
            ror.runofriver_forecast AS river
        FROM meteologica.demand d
        JOIN meteologica.price p ON TO_TIMESTAMP(d."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI') = TO_TIMESTAMP(p."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI')
        JOIN meteologica.wind w ON TO_TIMESTAMP(d."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI') = TO_TIMESTAMP(w."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI')
        JOIN meteologica.licensed_solar ls ON TO_TIMESTAMP(d."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI') = TO_TIMESTAMP(ls."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI')
        JOIN meteologica.unlicensed_solar us ON TO_TIMESTAMP(d."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI') = TO_TIMESTAMP(us."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI')
        JOIN meteologica.runofriver_hydro ror ON TO_TIMESTAMP(d."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI') = TO_TIMESTAMP(ror."From-yyyy-mm-dd-hh-mm", 'YYYY-MM-DD HH24:MI')
        WHERE DATE(CAST(d."From-yyyy-mm-dd-hh-mm" AS TIMESTAMP)) = :pred_date
        ORDER BY date
        """)

        supply_demand_query = text("""
        SELECT date, TO_CHAR(date, 'HH24:MI') AS hour, price, supply, demand
        FROM epias.supply_demand
        WHERE DATE(date) IN :gen_dates
        ORDER BY date, price
        """).bindparams(bindparam('gen_dates', expanding=True))

        with engine.connect() as conn:
            ref_df = pd.read_sql(ref_query, con=conn, params={"gen_dates": unique_ref_dates})
            pred_df = pd.read_sql(pred_query, con=conn, params={"pred_date": pred_date_parsed})
            pred_df['mcp_pred'] = pred_df['mcp_pred'].round(2)
            supply_demand_df = pd.read_sql(supply_demand_query, con=conn, params={"gen_dates": unique_ref_dates})

        ref_df = _rows_for_ref_dates(ref_df, ref_by_hour, 'day')
        supply_demand_df = (_rows_for_ref_dates(supply_demand_df, ref_by_hour, 'date')
                            .sort_values(['hour', 'price']).reset_index(drop=True))

        # Merge and calculate deltas
        cols = ['demand', 'river', 'wind', 'solar']
        df_diff = pd.merge(ref_df, pred_df, on='hour', suffixes=('_ref', '_pred'))
        df_diff = df_diff.sort_values('hour').reset_index(drop=True)
        
        for col in cols:
            df_diff[f'{col}(Δ)'] = df_diff[f'{col}_pred'] - df_diff[f'{col}_ref']
        
        if custom_capacity_deltas:
            df_diff['capacity(Δ)'] = df_diff['hour'].map(
                lambda h: float(custom_capacity_deltas.get(h, 0))
            )
        else:
            df_diff['capacity(Δ)'] = (df_diff['demand(Δ)']
                                       - df_diff['river(Δ)'] - df_diff['wind(Δ)']
                                       - df_diff['solar(Δ)'])

        # Calculate merit order price
        mcp_merit_values = [None] * len(df_diff)
        if not supply_demand_df.empty:
            supply_demand_df['capacity(Δ)'] = supply_demand_df['demand'] + supply_demand_df['supply']
            capacity_deltas = df_diff['capacity(Δ)'].tolist()
            forecast_points = _calculate_merit_order_price(supply_demand_df, capacity_deltas)
            if len(forecast_points) == len(df_diff):
                forecast_prices_df = pd.concat(forecast_points, axis=1).T
                mcp_merit_values = forecast_prices_df['price'].tolist()
        
        df_diff['mcp_merit'] = mcp_merit_values
        
        # Organize columns (matching notebook: date_ref, date_pred, mcp_ref, mcp_merit, mcp_pred, capacity, ...)
        new_order = ['date_ref', 'date_pred', 'mcp_ref', 'mcp_merit', 'mcp_pred', 'capacity(Δ)']
        for col in cols:
            new_order.extend([f'{col}_ref', f'{col}_pred', f'{col}(Δ)'])
        
        df_diff.drop(columns=['hour', 'day_ref', 'day_pred'], inplace=True, errors='ignore')
        df_diff = df_diff[new_order]
        
        # Add totals row (exclude mcp columns from sum)
        total_row = df_diff.drop(columns=['mcp_ref', 'mcp_merit', 'mcp_pred']).sum(numeric_only=True)
        df_diff.loc[len(df_diff)] = total_row
        df_diff.set_index(['date_ref', 'date_pred', 'mcp_ref', 'mcp_merit', 'mcp_pred'], inplace=True)
        
        # --- Sheet 3: Failure ---
        failure_query = """
        SELECT 
            "uevcbName", 
            "caseStartDate", 
            "caseEndDate", 
            "operatorPower", 
            "capacityAtCaseTime",
            ROUND("operatorPower" - "capacityAtCaseTime") AS "outageAmount"
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY "uevcbName"
                       ORDER BY "caseEndDate" ASC
                   ) as row_num
            FROM epias.market_messages
            WHERE "caseEndDate" >= (CURRENT_TIMESTAMP + INTERVAL '3' HOUR)
        ) t
        WHERE t.row_num = 1
        ORDER BY "outageAmount" DESC
        """
        
        with engine.connect() as conn:
            failure_df = pd.read_sql(text(failure_query), con=conn)
        
        if not failure_df.empty:
            failure_df.set_index('uevcbName', inplace=True)
        
        # --- Sheet 2: AIC ---
        uevcb_path = os.path.join(current_app.static_folder, 'data', 'uevcb.xlsx')
        aic_pivot_df = pd.DataFrame()
        
        if os.path.exists(uevcb_path):
            try:
                uevcb = pd.read_excel(uevcb_path, sheet_name='Sheet2')
                tz = pytz.timezone('Europe/Istanbul')
                today_start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
                
                with epias_session(total=3, backoff_factor=0.5) as session_api:
                    all_aic, _ = _fetch_tracked_aic(session_api, uevcb, today_start)
                
                if all_aic:
                    eak_df = pd.DataFrame.from_records(all_aic)
                    eak_df = eak_df[['date', 'uevcbId', 'toplam']].copy()
                    eak_df = eak_df.merge(uevcb[["id", "name"]], left_on="uevcbId", right_on="id", how="left").drop(columns=['id', 'uevcbId'])
                    eak_df['date'] = pd.to_datetime(eak_df['date'])
                    eak_df['hour'] = eak_df['date'].dt.strftime('%H:%M')
                    aic_pivot_df = eak_df.pivot(index="name", columns="hour", values="toplam").fillna(0)
            except Exception as e:
                current_app.logger.warning(f"AIC processing error: {str(e)}")
        
        # --- Write Excel ---
        output = BytesIO()

        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df_diff.to_excel(writer, sheet_name='Results')
        workbook = writer.book
        worksheet = writer.sheets['Results']
        bold_format = workbook.add_format({'bold': True})
        
        num_idx_cols = len(df_diff.index.names)  # 5: date_ref, date_pred, mcp_ref, mcp_merit, mcp_pred
        num_rows = len(df_diff) - 1
        
        if 'capacity(Δ)' in df_diff.columns:
            capacity_col_idx = df_diff.columns.get_loc('capacity(Δ)') + num_idx_cols
            col_letter = chr(64 + capacity_col_idx + 1)
            
            worksheet.conditional_format(f'{col_letter}2:{col_letter}{num_rows + 1}', {
                'type': '3_color_scale',
                'min_color': "#F8696B",
                'mid_color': "#FFEB84",
                'max_color': "#63BE7B"
            })
        
        worksheet.set_row(num_rows + 1, None, bold_format)
        
        for i, col in enumerate(df_diff.columns):
            max_len = max(df_diff[col].astype(str).map(len).max(), len(str(col))) + 3
            worksheet.set_column(i + num_idx_cols, i + num_idx_cols, max_len)
        
        num_cols = len(df_diff.columns)
        for col_num in range(num_idx_cols, num_cols + num_idx_cols):
            cell_value = df_diff.iloc[-1, col_num - num_idx_cols]
            worksheet.write(num_rows + 1, col_num, cell_value, bold_format)
        
        worksheet.set_column(0, 1, 20)
        
        # Reorder sheets: Results first
        workbook.worksheets_objs.sort(key=lambda x: x.name != 'Results')
        
        # Sheet 2: AIC
        if not aic_pivot_df.empty:
            aic_pivot_df.to_excel(writer, sheet_name='AIC')
            aic_worksheet = writer.sheets['AIC']
            aic_worksheet.set_column(0, 0, 40)
        
        # Sheet 3: Outages
        if not failure_df.empty:
            failure_df.to_excel(writer, sheet_name='Outages')
            failure_worksheet = writer.sheets['Outages']
            failure_worksheet.set_column(0, 0, 55)
            failure_worksheet.set_column(1, 1, 18)
            failure_worksheet.set_column(2, 2, 18)
            failure_worksheet.set_column(3, 3, 13)
            failure_worksheet.set_column(4, 4, 17)
            failure_worksheet.set_column(5, 5, 12.5)
        
        writer.close()
        output.seek(0)
        
        filename = f"merit_order_{'_'.join(d.isoformat() for d in unique_ref_dates)}_vs_{pred_date}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return api_error("download_merit_order_excel", e)
