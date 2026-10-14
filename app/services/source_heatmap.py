"""System-wide generation by source: DPP (KGÜP) first/final versions vs realtime.

The plan side is the EPIAS dpp / dpp-first-version endpoints called without a
plant filter, which return the whole system broken down by fuel. The realtime
side is read from production_data (EPIAS realtime generation, already stored),
except for solar: the plan's `gunes` covers licensed *and* unlicensed plants,
while realtime `sun` is licensed only. The unlicensed part comes from EPIAS
metered data where it has been published (monthly, a month or more late) and
from Meteologica's forecast otherwise, flagged as an estimate.
"""
from datetime import date, datetime, timedelta

import requests
from flask import current_app
from sqlalchemy import text

from ..database.config import db
from ..functions import get_tgt_token
from ..models.heatmap import SourceHeatmapData, UnlicensedGenerationData
from ..models.production import ProductionData

REALTIME_URL = 'https://seffaflik.epias.com.tr/electricity-service/v1/generation/data/realtime-generation'
UNLICENSED_URL = 'https://seffaflik.epias.com.tr/electricity-service/v1/renewables/data/unlicensed-generation-amount'

# (column label, DPP field, production_data columns summed for realtime).
# 'diger' has no documented realtime counterpart; asphaltite + waste heat is the
# closest match by magnitude, hence the label spelling the assumption out.
# 'gunes' realtime is sun + unlicensed solar, handled separately.
SOURCES = [
    ('Natural Gas', 'dogalgaz', ['naturalgas', 'lng']),
    ('Lignite', 'linyit', ['lignite']),
    ('Import Coal', 'ithalKomur', ['importcoal']),
    ('Hard Coal', 'tasKomur', ['blackcoal']),
    ('Dammed Hydro', 'barajli', ['dammedhydro']),
    ('Run-of-River', 'akarsu', ['river']),
    ('Wind', 'ruzgar', ['wind']),
    ('Solar', 'gunes', ['sun']),
    ('Geothermal', 'jeotermal', ['geothermal']),
    ('Biomass', 'biokutle', ['biomass']),
    ('Fuel Oil', 'fuelOil', ['fueloil']),
    ('Naphta', 'nafta', ['naphta']),
    ('Other (asphaltite, waste heat)', 'diger', ['asphaltitecoal', 'wasteheat']),
]
TOTAL_LABEL, TOTAL_FIELD = 'Total', 'toplam'
SOLAR_FIELD = 'gunes'

PLAN_FIELDS = [field for _, field, _ in SOURCES] + [TOTAL_FIELD]
LABELS = [label for label, _, _ in SOURCES] + [TOTAL_LABEL]
HOURS = [f'{h:02d}:00' for h in range(24)]

# EPIAS rejects very long ranges; a month per call is well within its limits.
CHUNK_DAYS = 31


def _epias_post(url, start, end, token, extra=None):
    body = {
        'startDate': f'{start:%Y-%m-%d}T00:00:00+03:00',
        'endDate': f'{end:%Y-%m-%d}T00:00:00+03:00',
    }
    body.update(extra or {})
    res = requests.post(url, json=body, headers={'TGT': token, 'Accept': 'application/json'}, timeout=120)
    res.raise_for_status()
    return res.json().get('items') or []


def _chunks(start, end):
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=CHUNK_DAYS - 1), end)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def _item_date_hour(item):
    # EPIAS dates are local ISO strings: 2026-10-14T12:00:00+03:00
    stamp = datetime.fromisoformat(item['date'])
    return stamp.date(), stamp.hour


def populate_source_plan(start, end, versions=('first', 'current'), token=None):
    """Fetch the system-wide DPP for [start, end] and replace what is stored.

    Must run inside an app context. Days EPIAS returns nothing for are left
    untouched rather than wiped, so a not-yet-published tomorrow cannot erase
    an earlier fetch. Returns the number of rows written.
    """
    token = token or get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
    written = 0
    for version in versions:
        url = current_app.config['DPP_FIRST_VERSION_URL'] if version == 'first' else current_app.config['DPP_URL']
        for chunk_start, chunk_end in _chunks(start, end):
            items = _epias_post(url, chunk_start, chunk_end, token, {'region': 'TR1'})
            rows = []
            for item in items:
                item_date, hour = _item_date_hour(item)
                for field in PLAN_FIELDS:
                    if item.get(field) is not None:
                        rows.append({'date': item_date, 'hour': hour, 'source': field,
                                     'value': float(item[field]), 'version': version})
            if not rows:
                continue
            days = sorted({r['date'] for r in rows})
            SourceHeatmapData.query.filter(
                SourceHeatmapData.date.in_(days),
                SourceHeatmapData.version == version,
            ).delete(synchronize_session=False)
            db.session.bulk_insert_mappings(SourceHeatmapData, rows)
            db.session.commit()
            written += len(rows)
    return written


def populate_unlicensed_generation(start, end, token=None):
    """Fetch EPIAS metered unlicensed generation for [start, end] and replace
    what is stored. Unpublished months come back empty and are skipped.
    Returns the number of rows written."""
    token = token or get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
    written = 0
    for chunk_start, chunk_end in _chunks(start, end):
        items = _epias_post(UNLICENSED_URL, chunk_start, chunk_end, token)
        rows = []
        for item in items:
            item_date, hour = _item_date_hour(item)
            for field, value in item.items():
                if field in ('date', 'time') or value is None:
                    continue
                rows.append({'date': item_date, 'hour': hour, 'source': field, 'value': float(value)})
        if not rows:
            continue
        days = sorted({r['date'] for r in rows})
        UnlicensedGenerationData.query.filter(
            UnlicensedGenerationData.date.in_(days)
        ).delete(synchronize_session=False)
        db.session.bulk_insert_mappings(UnlicensedGenerationData, rows)
        db.session.commit()
        written += len(rows)
    return written


def plan_matrix(day, version):
    """24 x len(LABELS) plan values for one day, or None if nothing is stored.

    Fetches from EPIAS on a miss (and stores it), like the other heatmaps do.
    """
    records = SourceHeatmapData.query.filter_by(date=day, version=version).all()
    if not records:
        populate_source_plan(day, day, versions=(version,))
        records = SourceHeatmapData.query.filter_by(date=day, version=version).all()
    if not records:
        return None

    index = {field: i for i, field in enumerate(PLAN_FIELDS)}
    values = [[None] * len(PLAN_FIELDS) for _ in range(24)]
    for r in records:
        if r.source in index and 0 <= r.hour < 24:
            values[r.hour][index[r.source]] = r.value
    return values


def _meteologica_unlicensed(day):
    """{hour: MW} from Meteologica's unlicensed PV forecast (Supabase). It tracks
    EPIAS metered data at ~0.997 correlation, close enough to stand in until
    EPIAS publishes."""
    from ..main import _get_supabase_engine  # main imports this module's callers

    query = text("""
        SELECT EXTRACT(HOUR FROM CAST("From-yyyy-mm-dd-hh-mm" AS TIMESTAMP))::int AS hour,
               unlicensed_forecast
        FROM meteologica.unlicensed_solar
        WHERE "From-yyyy-mm-dd-hh-mm" >= :start AND "From-yyyy-mm-dd-hh-mm" < :end
    """)
    with _get_supabase_engine().connect() as conn:
        rows = conn.execute(query, {
            'start': f'{day:%Y-%m-%d} 00:00',
            'end': f'{day + timedelta(days=1):%Y-%m-%d} 00:00',
        }).fetchall()
    return {int(h): float(v) for h, v in rows if v is not None}


# EPIAS realtime field -> production_data column, as in update_rolling_data
PRODUCTION_FIELDS = {
    'fueloil': 'fueloil', 'blackCoal': 'blackcoal', 'lignite': 'lignite',
    'geothermal': 'geothermal', 'naturalGas': 'naturalgas', 'river': 'river',
    'dammedHydro': 'dammedhydro', 'lng': 'lng', 'biomass': 'biomass',
    'naphta': 'naphta', 'importCoal': 'importcoal', 'asphaltiteCoal': 'asphaltitecoal',
    'wind': 'wind', 'sun': 'sun', 'importExport': 'importexport', 'total': 'total',
    'wasteheat': 'wasteheat',
}


def fill_production_data(day):
    """Insert the hours of a past `day` that production_data is missing.

    Called by the 05:00/12:00 realtime jobs for the last week, and on demand by
    realtime_matrix, so production_data no longer depends on someone pressing
    the Update Database button. Existing hours are never overwritten.
    """
    present = {
        r[0] for r in db.session.execute(text(
            "SELECT DISTINCT EXTRACT(HOUR FROM datetime)::int FROM production_data "
            "WHERE datetime >= :start AND datetime < :end"
        ), {'start': day, 'end': day + timedelta(days=1)}).fetchall()
    }
    if len(present) == 24:
        return

    token = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
    items = _epias_post(REALTIME_URL, day, day, token, {'region': 'TR1'})
    for item in items:
        _, hour = _item_date_hour(item)
        if hour in present:
            continue
        record = {col: item.get(field) or 0 for field, col in PRODUCTION_FIELDS.items()}
        db.session.add(ProductionData(
            datetime=datetime.combine(day, datetime.min.time()) + timedelta(hours=hour),
            gasoil=0, nuclear=0, **record,
        ))
    db.session.commit()


def realtime_matrix(day):
    """24 x len(LABELS) realtime values for one day, aligned with plan_matrix.

    Hours without data are None (shown as pending, never as zero). Returns
    (values, solar_estimated) where solar_estimated[h] is True when that hour's
    unlicensed solar is Meteologica's forecast rather than EPIAS metered data.
    """
    if day < date.today():
        fill_production_data(day)

    columns = sorted({c for _, _, cols in SOURCES for c in cols})
    # Some rows are stamped hh:04 instead of hh:00; there is never more than one
    # per hour, so truncating is safe.
    query = text(f"""
        SELECT EXTRACT(HOUR FROM datetime)::int AS hour, {', '.join(columns)}
        FROM production_data
        WHERE datetime >= :start AND datetime < :end
    """)
    rows = db.session.execute(query, {'start': day, 'end': day + timedelta(days=1)}).mappings().all()
    by_hour = {r['hour']: r for r in rows}

    metered = {
        r.hour: r.value for r in UnlicensedGenerationData.query.filter_by(date=day, source=SOLAR_FIELD).all()
    }
    forecast = None if len(metered) == 24 else _meteologica_unlicensed(day)

    values = [[None] * len(PLAN_FIELDS) for _ in range(24)]
    solar_estimated = [False] * 24
    solar_idx = PLAN_FIELDS.index(SOLAR_FIELD)

    for hour in range(24):
        row = by_hour.get(hour)
        if row is None:
            continue
        for i, (_, field, cols) in enumerate(SOURCES):
            parts = [row[c] for c in cols]
            values[hour][i] = None if all(p is None for p in parts) else sum(p or 0 for p in parts)

        if hour in metered:
            unlicensed = metered[hour]
        elif forecast and hour in forecast:
            unlicensed = forecast[hour]
            solar_estimated[hour] = True
        else:
            unlicensed = None
        if values[hour][solar_idx] is not None and unlicensed is not None:
            values[hour][solar_idx] += unlicensed
        else:
            values[hour][solar_idx] = None

        known = [v for v in values[hour][:len(SOURCES)] if v is not None]
        values[hour][-1] = sum(known) if len(known) == len(SOURCES) else None

    return values, solar_estimated
