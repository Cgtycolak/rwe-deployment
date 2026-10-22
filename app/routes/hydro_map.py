"""Hydro Map tab."""
import time
from datetime import datetime
from flask import Blueprint, request, jsonify
from ..functions import login_required
from ..database.config import db
from .common import api_error

hydro_map_bp = Blueprint('hydro_map', __name__)


# The map payload for a given day never changes once the 06:00 job has written
# it, but building it costs four database round trips — ~1.7 s when the app is
# far from the Render database. Cache the finished payload per (date, type);
# the short TTL on the "latest date" lookup is what lets a new day appear.
_HYDRO_MAP_CACHE = {}
_HYDRO_MAP_LATEST = {'date': None, 'checked_at': 0.0}
_HYDRO_LATEST_TTL = 300      # seconds
_HYDRO_CACHE_MAX = 12        # payloads kept, ~115 KB each


def _hydro_latest_date(model):
    """Newest stored day, re-checked at most every _HYDRO_LATEST_TTL seconds."""
    now = time.time()
    if _HYDRO_MAP_LATEST['date'] is None or now - _HYDRO_MAP_LATEST['checked_at'] > _HYDRO_LATEST_TTL:
        _HYDRO_MAP_LATEST['date'] = db.session.query(db.func.max(model.date)).scalar()
        _HYDRO_MAP_LATEST['checked_at'] = now
    return _HYDRO_MAP_LATEST['date']


@hydro_map_bp.route('/hydro-map-data', methods=['GET'])
@login_required
def get_hydro_map_data():
    """District-level hydro generation for the map.

    Plants are placed by district centroid, not their own coordinates — the EPDK
    licence file only carries province/district — so they are aggregated per
    district rather than drawn individually, which would imply a precision we do
    not have.

    `fill` is the capacity factor (MWh generated / (MW installed x 24)); it is
    what fills the bubble.
    """
    try:
        from ..models.hydro_map import HydroPlant, HydroDailyGeneration

        plant_type = request.args.get('type', 'river')
        if plant_type not in ('river', 'dammed', 'all'):
            return jsonify({'code': 400, 'message': "type must be river, dammed or all"}), 400

        date_str = request.args.get('date')
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'code': 400, 'message': 'Date must be YYYY-MM-DD'}), 400
        else:
            date = _hydro_latest_date(HydroDailyGeneration)
            if date is None:
                return jsonify({'code': 404, 'message': 'No hydro generation data loaded yet'}), 404

        cached = _HYDRO_MAP_CACHE.get((date, plant_type))
        if cached is not None:
            return jsonify(cached)

        query = HydroPlant.query.filter(HydroPlant.latitude.isnot(None))
        if plant_type != 'all':
            query = query.filter(HydroPlant.plant_type == plant_type)
        plants = query.all()
        if not plants:
            return jsonify({'code': 404, 'message': f'No plants classified as {plant_type}'}), 404

        generation = {
            row.epias_id: row
            for row in HydroDailyGeneration.query.filter_by(date=date).all()
        }
        # An explicitly requested day with no rows must not render as a map full of
        # empty bubbles — that is indistinguishable from a real day of zero output.
        if not generation:
            stored = [
                d.isoformat() for (d,) in db.session.query(HydroDailyGeneration.date)
                .distinct().order_by(HydroDailyGeneration.date.desc()).limit(60).all()
            ]
            hint = (f' Loaded days: {stored[-1]} to {stored[0]}.' if stored
                    else ' No days are loaded yet.')
            return jsonify({
                'code': 404,
                'message': f'No hydro generation data stored for {date.isoformat()}.{hint}',
                'available_dates': stored,
            }), 404

        districts = {}
        for p in plants:
            key = (p.province, p.district)
            d = districts.setdefault(key, {
                'region': p.region, 'province': p.province, 'district': p.district,
                'lat': p.latitude, 'lon': p.longitude,
                'capacity_mw': 0.0, 'generation_mwh': 0.0, 'plants': [],
            })
            capacity = p.operating_mw or 0.0
            row = generation.get(p.epias_id)
            # river and dammed are reported separately; sum only what this filter shows
            if row is None:
                produced = None
            elif plant_type == 'river':
                produced = row.river_mwh
            elif plant_type == 'dammed':
                produced = row.dammed_mwh
            else:
                produced = row.total_mwh

            d['capacity_mw'] += capacity
            if produced is not None:
                d['generation_mwh'] += produced
            d['plants'].append({
                'name': p.name, 'capacity_mw': round(capacity, 1),
                'generation_mwh': None if produced is None else round(produced, 1),
                'type': p.plant_type,
            })

        out = []
        for d in districts.values():
            ceiling = d['capacity_mw'] * 24
            d['fill'] = round(min(d['generation_mwh'] / ceiling, 1.0), 4) if ceiling > 0 else 0.0
            d['capacity_mw'] = round(d['capacity_mw'], 1)
            d['generation_mwh'] = round(d['generation_mwh'], 1)
            d['plants'].sort(key=lambda x: x['capacity_mw'], reverse=True)
            out.append(d)
        out.sort(key=lambda x: x['capacity_mw'], reverse=True)

        # Bounds come from the full table, not the truncated list below: capping the
        # list at 60 days would otherwise make the date picker reject days that are
        # actually stored.
        first_day, last_day = db.session.query(
            db.func.min(HydroDailyGeneration.date), db.func.max(HydroDailyGeneration.date)
        ).one()
        available = [
            d.isoformat() for (d,) in db.session.query(HydroDailyGeneration.date)
            .distinct().order_by(HydroDailyGeneration.date.desc()).limit(120).all()
        ]

        payload = {
            'code': 200,
            'data': {
                'date': date.isoformat(),
                'type': plant_type,
                'available_dates': available,
                'date_range': {'min': first_day.isoformat(), 'max': last_day.isoformat()},
                'districts': out,
                'summary': {
                    'plants': sum(len(d['plants']) for d in out),
                    'districts': len(out),
                    'capacity_mw': round(sum(d['capacity_mw'] for d in out), 1),
                    'generation_mwh': round(sum(d['generation_mwh'] for d in out), 1),
                },
            },
        }

        if len(_HYDRO_MAP_CACHE) >= _HYDRO_CACHE_MAX:
            _HYDRO_MAP_CACHE.clear()
        _HYDRO_MAP_CACHE[(date, plant_type)] = payload
        return jsonify(payload)

    except Exception as e:
        return api_error("get_hydro_map_data", e)
