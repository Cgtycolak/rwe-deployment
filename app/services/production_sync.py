"""Keep production_data in step with EPIAS realtime generation.

Same problem as demand (see app/services/demand_sync.py): EPIAS publishes realtime
generation within the hour and revises it afterwards, while the old button route
only ever added hours it did not have. So the latest hour was stored half-complete
and never corrected, and later revisions never arrived.

sync_production() fetches EPIAS one calendar month per request, adds missing hours,
overwrites changed ones and logs each change of the total to production_revisions.
"""
import time
from datetime import date, datetime, timedelta

import requests
from flask import current_app
from requests.adapters import HTTPAdapter
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from urllib3.util.retry import Retry

from app.database.config import db
from app.functions import get_tgt_token
from app.models.production import ProductionData, ProductionRevision

URL = 'https://seffaflik.epias.com.tr/electricity-service/v1/generation/data/realtime-generation'

# production_data column: EPIAS field. gasoil and nuclear have no realtime field
# and stay 0, as they always have.
FIELDS = {
    'fueloil': 'fueloil', 'blackcoal': 'blackCoal', 'lignite': 'lignite', 'geothermal': 'geothermal',
    'naturalgas': 'naturalGas', 'river': 'river', 'dammedhydro': 'dammedHydro', 'lng': 'lng',
    'biomass': 'biomass', 'naphta': 'naphta', 'importcoal': 'importCoal', 'asphaltitecoal': 'asphaltiteCoal',
    'wind': 'wind', 'sun': 'sun', 'importexport': 'importExport', 'total': 'total', 'wasteheat': 'wasteheat',
}

TOLERANCE_MWH = 0.5


def _month_chunks(start: date, end: date):
    d = start
    while d <= end:
        next_month = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield d, min(next_month - timedelta(days=1), end)
        d = next_month


def _fetch(session, tgt, first: date, last: date):
    """{naive Istanbul hour: {column: value}} from EPIAS for first..last inclusive."""
    payload = {'startDate': f'{first}T00:00:00+03:00', 'endDate': f'{last}T23:59:59+03:00', 'region': 'TR1'}
    response = session.post(URL, json=payload, timeout=90,
                            headers={'TGT': tgt, 'Accept': 'application/json'})
    response.raise_for_status()
    hours = {}
    for item in response.json().get('items', []):
        hour = datetime.fromisoformat(item['date']).replace(tzinfo=None)
        hours[hour] = {col: float(item.get(key) or 0) for col, key in FIELDS.items()}
    return hours


def normalise_legacy_minutes():
    """Move rows stored at HH:04 (the 2016-2025 bulk load) onto HH:00.

    Syncing matches hours exactly, so a :04 row would sit next to a new :00 row for
    the same hour. Where both already exist the :00 row wins. Returns rows moved.
    """
    db.session.execute(text("""
        DELETE FROM production_data p USING production_data q
        WHERE EXTRACT(MINUTE FROM p.datetime) <> 0
          AND q.datetime = date_trunc('hour', p.datetime)"""))
    moved = db.session.execute(text("""
        UPDATE production_data SET datetime = date_trunc('hour', datetime)
        WHERE EXTRACT(MINUTE FROM datetime) <> 0""")).rowcount
    db.session.commit()
    return moved


def sync_production(start: date, end: date):
    """Add missing and overwrite revised hours between start and end (inclusive).

    Returns {'checked', 'added', 'revised', 'by_month': {'2026-06': revised, ...}}.
    """
    normalise_legacy_minutes()
    tgt = get_tgt_token(current_app.config.get('USERNAME'), current_app.config.get('PASSWORD'))
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=Retry(
        total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['POST'])))

    stats = {'checked': 0, 'added': 0, 'revised': 0, 'by_month': {}}
    now = datetime.now()
    columns = ', '.join(FIELDS)

    chunks = list(_month_chunks(start, end))
    for i, (first, last) in enumerate(chunks):
        # Shares the EPIAS account's rate limit with every other feature
        if i and len(chunks) > 3:
            time.sleep(1)
        epias = _fetch(session, tgt, first, last)
        if not epias:
            continue

        stored = {
            row[0]: row[1:]
            for row in db.session.execute(
                text(f'SELECT datetime, {columns} FROM production_data WHERE datetime >= :a AND datetime < :b'),
                {'a': datetime.combine(first, datetime.min.time()),
                 'b': datetime.combine(last + timedelta(days=1), datetime.min.time())})
        }

        upserts, revisions = [], []
        for hour, values in epias.items():
            old = stored.get(hour)
            if old is not None and all(abs((o or 0) - values[c]) <= TOLERANCE_MWH for o, c in zip(old, FIELDS)):
                continue
            upserts.append({'datetime': hour, **values, 'gasoil': 0, 'nuclear': 0, 'created_at': now})
            if old is not None:
                revisions.append({'datetime': hour, 'old_total': old[list(FIELDS).index('total')] or 0,
                                  'new_total': values['total'], 'detected_at': now})

        if upserts:
            stmt = insert(ProductionData.__table__).values(upserts)
            db.session.execute(stmt.on_conflict_do_update(
                index_elements=['datetime'],
                set_={c: stmt.excluded[c] for c in (*FIELDS, 'created_at')}))
        if revisions:
            db.session.execute(insert(ProductionRevision.__table__).values(revisions))
        db.session.commit()

        stats['checked'] += len(epias)
        stats['added'] += len(upserts) - len(revisions)
        stats['revised'] += len(revisions)
        if revisions:
            stats['by_month'][f'{first:%Y-%m}'] = len(revisions)

    return stats
