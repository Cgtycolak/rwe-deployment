"""DPP heatmap tabs: natural gas, import coal, hydro, lignite and generation by source.

The per-fuel matrices come from app/services/plant_heatmaps.py, the by-source ones
from app/services/source_heatmap.py.
"""
from datetime import datetime

from flask import Blueprint, jsonify, request

from ..database.config import db
from ..functions import login_required
from ..services.plant_heatmaps import FUELS, HOURS, plan_values, realtime_values
from .common import api_error

heatmaps_bp = Blueprint('heatmaps', __name__)


def _request_date():
    """The 'date' field of the JSON body as a date, or None when missing or malformed."""
    try:
        return datetime.strptime((request.get_json(silent=True) or {}).get('date') or '', '%Y-%m-%d').date()
    except ValueError:
        return None


def _matrix_response(fuel, values):
    return jsonify({'code': 200, 'data': {'hours': HOURS, 'plants': fuel.labels(), 'values': values}})


def _plan_response(fuel_key, route_name, default_version):
    day = _request_date()
    if day is None:
        return jsonify({'code': 400, 'message': 'A date in YYYY-MM-DD format is required'}), 400
    version = (request.get_json(silent=True) or {}).get('version') or default_version
    if version not in ('first', 'current'):
        return jsonify({'code': 400, 'message': "version must be 'first' or 'current'"}), 400
    try:
        fuel = FUELS[fuel_key]
        return _matrix_response(fuel, plan_values(fuel, day, version))
    except Exception as e:
        return api_error(route_name, e)


def _realtime_response(fuel_key, route_name):
    day = _request_date()
    if day is None:
        return jsonify({'code': 400, 'message': 'A date in YYYY-MM-DD format is required'}), 400
    try:
        fuel = FUELS[fuel_key]
        return _matrix_response(fuel, realtime_values(fuel, day))
    except Exception as e:
        db.session.rollback()
        return api_error(route_name, e)


@heatmaps_bp.route('/heatmap_data', methods=['POST'])
@login_required
def heatmap_data():
    return _plan_response('natural_gas', 'heatmap_data', default_version='first')


@heatmaps_bp.route('/realtime_heatmap_data', methods=['POST'])
@login_required
def realtime_heatmap_data():
    return _realtime_response('natural_gas', 'realtime_heatmap_data')


@heatmaps_bp.route('/import_coal_heatmap_data', methods=['POST'])
@login_required
def import_coal_heatmap_data():
    return _plan_response('import_coal', 'import_coal_heatmap_data', default_version='first')


@heatmaps_bp.route('/hydro_heatmap_data', methods=['POST'])
@login_required
def hydro_heatmap_data():
    return _plan_response('hydro', 'hydro_heatmap_data', default_version='first')


@heatmaps_bp.route('/hydro_realtime_heatmap_data', methods=['POST'])
@login_required
def hydro_realtime_heatmap_data():
    return _realtime_response('hydro', 'hydro_realtime_heatmap_data')


@heatmaps_bp.route('/lignite_heatmap_data', methods=['POST'])
@login_required
def lignite_heatmap_data():
    return _plan_response('lignite', 'lignite_heatmap_data', default_version='current')


@heatmaps_bp.route('/lignite_realtime_heatmap_data', methods=['POST'])
@login_required
def lignite_realtime_heatmap_data():
    return _realtime_response('lignite', 'lignite_realtime_heatmap_data')


@heatmaps_bp.route('/source_heatmap_data', methods=['POST'])
@login_required
def source_heatmap_data():
    """System-wide DPP by source for one date and version ('first' or 'current')."""
    from app.services.source_heatmap import plan_matrix, LABELS, HOURS
    try:
        data = request.get_json() or {}
        date_str = data.get('date')
        version = data.get('version', 'current')
        if not date_str:
            return jsonify({'code': 400, 'message': 'Date is required'}), 400
        if version not in ('first', 'current'):
            return jsonify({'code': 400, 'message': "version must be 'first' or 'current'"}), 400
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        values = plan_matrix(date_obj, version)
        if values is None:
            return jsonify({'code': 404, 'message': f'No {version} DPP published for {date_str} yet'})

        return jsonify({'code': 200, 'data': {'hours': HOURS, 'plants': LABELS, 'values': values}})

    except ValueError:
        return jsonify({'code': 400, 'message': 'Invalid date format'}), 400
    except Exception as e:
        db.session.rollback()
        return api_error("source_heatmap_data", e)


@heatmaps_bp.route('/source_realtime_heatmap_data', methods=['POST'])
@login_required
def source_realtime_heatmap_data():
    """Realtime generation by source for one date, aligned with /source_heatmap_data.

    Hours not yet available are null. solar_estimated flags the hours whose
    unlicensed solar is Meteologica's forecast instead of EPIAS metered data.
    """
    from app.services.source_heatmap import realtime_matrix, LABELS, HOURS
    try:
        data = request.get_json() or {}
        date_str = data.get('date')
        if not date_str:
            return jsonify({'code': 400, 'message': 'Date is required'}), 400
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        values, solar_estimated = realtime_matrix(date_obj)
        if all(v is None for row in values for v in row):
            return jsonify({'code': 404, 'message': f'No realtime generation stored for {date_str} yet'})

        return jsonify({'code': 200, 'data': {
            'hours': HOURS, 'plants': LABELS, 'values': values,
            'solar_estimated': solar_estimated,
        }})

    except ValueError:
        return jsonify({'code': 400, 'message': 'Invalid date format'}), 400
    except Exception as e:
        return api_error("source_realtime_heatmap_data", e)
