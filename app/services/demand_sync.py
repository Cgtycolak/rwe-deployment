"""Keep demand_data in step with EPIAS realtime consumption.

EPIAS publishes realtime consumption within hours, then keeps revising it for weeks:
an October 2026 audit found almost every hour from October 2025 on differed from
EPIAS's current value, by up to 13% for single hours. So syncing is not only
"add new hours" but also "overwrite hours EPIAS has changed since".

sync_demand() does both for any range: it fetches EPIAS one calendar month per
request, adds missing hours, overwrites changed ones and logs each change to
demand_revisions. The scheduler calls it with a short window every hour and a long
one every night (see app/tasks/scheduler.py).
"""
import time
from datetime import date, datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from urllib3.util.retry import Retry

from app.database.config import db
from app.services.epias import epias_token
from app.models.demand import DemandData, DemandRevision

URL = 'https://seffaflik.epias.com.tr/electricity-service/v1/consumption/data/realtime-consumption'

# Changes smaller than this are rounding noise, not revisions
TOLERANCE_MWH = 0.5


def _month_chunks(start: date, end: date):
    """(first, last) day pairs, one per calendar month, covering start..end."""
    d = start
    while d <= end:
        next_month = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield d, min(next_month - timedelta(days=1), end)
        d = next_month


def _fetch(session, tgt, first: date, last: date):
    """{naive Istanbul hour: consumption} from EPIAS for first..last inclusive."""
    payload = {
        'startDate': f'{first}T00:00:00+03:00',
        'endDate': f'{last}T23:59:59+03:00',
        'region': 'TR1',
    }
    response = session.post(URL, json=payload, timeout=60,
                            headers={'TGT': tgt, 'Accept': 'application/json'})
    response.raise_for_status()
    hours = {}
    for item in response.json().get('items', []):
        # "2026-06-01T00:00:00+03:00": the table stores Istanbul wall-clock time
        hour = datetime.fromisoformat(item['date']).replace(tzinfo=None)
        if item.get('consumption') is not None:
            hours[hour] = float(item['consumption'])
    return hours


def sync_demand(start: date, end: date):
    """Add missing and overwrite revised hours between start and end (inclusive).

    Returns {'checked', 'added', 'revised', 'by_month': {'2026-06': revised, ...}}.
    """
    tgt = epias_token()
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=Retry(
        total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['POST'])))

    stats = {'checked': 0, 'added': 0, 'revised': 0, 'by_month': {}}
    now = datetime.now()

    chunks = list(_month_chunks(start, end))
    for i, (first, last) in enumerate(chunks):
        # EPIAS rate-limits per account, and every dashboard feature shares ours,
        # so long runs (the monthly full-history check) pace themselves
        if i and len(chunks) > 3:
            time.sleep(1)
        epias = _fetch(session, tgt, first, last)
        if not epias:
            continue

        stored = dict(db.session.execute(
            text('SELECT datetime, consumption FROM demand_data WHERE datetime >= :a AND datetime < :b'),
            {'a': datetime.combine(first, datetime.min.time()),
             'b': datetime.combine(last + timedelta(days=1), datetime.min.time())},
        ).fetchall())

        upserts, revisions = [], []
        for hour, value in epias.items():
            old = stored.get(hour)
            if old is None:
                upserts.append({'datetime': hour, 'consumption': value, 'created_at': now})
            elif abs(old - value) > TOLERANCE_MWH:
                upserts.append({'datetime': hour, 'consumption': value, 'created_at': now})
                revisions.append({'datetime': hour, 'old_consumption': old,
                                  'new_consumption': value, 'detected_at': now})

        # One multi-row statement per table: row-by-row inserts take minutes against
        # the remote database for a month of revisions
        if upserts:
            stmt = insert(DemandData.__table__).values(upserts)
            db.session.execute(stmt.on_conflict_do_update(
                index_elements=['datetime'],
                set_={'consumption': stmt.excluded.consumption, 'created_at': stmt.excluded.created_at}))
        if revisions:
            db.session.execute(insert(DemandRevision.__table__).values(revisions))
        db.session.commit()

        stats['checked'] += len(epias)
        stats['added'] += len(upserts) - len(revisions)
        stats['revised'] += len(revisions)
        if revisions:
            stats['by_month'][f'{first:%Y-%m}'] = len(revisions)

    return stats
