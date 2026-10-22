"""Keep licensed_solar_data and unlicensed_solar_data in step with Meteologica.

Meteologica has no measured photovoltaic feed for Turkey, only forecasts, so each
hour stores the shortest-horizon forecast: the value for that hour from the last
forecast issued before the hour began.

Meteologica serves one ZIP per content per month of issue time, with one JSON file
per forecast update. Two details matter, and the old button route got both wrong
(an October 2026 audit found every stored hour 2 hours late against EPIAS's
measured licensed solar, plus about 1,000 near-zero midday dips):
- File names carry the issue time in Istanbul time, and the first entry is for the
  next hour. The hour each value belongs to is its "From" field, never the file name.
- "*_post_<MODEL>.json" files are per-model updates issued hours after their run
  time, so their first entry is several hours later than the name suggests.
Taking the entry whose From matches each hour avoids both.

Stored datetimes are UTC (the columns are timestamptz); readers convert to Istanbul.
"""
import io
import json
import os
import time
import zipfile
from datetime import date, datetime, timedelta, timezone

import requests
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from app.database.config import db
from app.models.licensed_solar import LicensedSolarData
from app.models.unlicensed_solar import UnlicensedSolarData

API = 'https://api-markets.meteologica.com/api/v1'

# name: (Meteologica content id, model, value column)
CONTENTS = {
    'licensed': (1429, LicensedSolarData, 'licensed_solar'),
    'unlicensed': (1430, UnlicensedSolarData, 'unlicensed_solar'),
}

# Only the first few hours of each forecast can be the latest one issued before an
# hour; reading all ~350 entries per file would only cost time
LEAD_HOURS = 6

TOLERANCE_MW = 0.5


class _Client:
    """Meteologica session that logs in again once when the token expires."""

    def __init__(self):
        self.user = os.getenv('XTRADERS_USERNAME')
        self.password = os.getenv('XTRADERS_PASSWORD')
        if not self.user or not self.password:
            raise RuntimeError('XTRADERS_USERNAME / XTRADERS_PASSWORD are not set')
        self.token = self._login()

    def _login(self):
        r = requests.post(f'{API}/login', json={'user': self.user, 'password': self.password}, timeout=30)
        r.raise_for_status()
        return r.json()['token']

    def month_zip(self, content_id, year, month):
        """The month's archive as a ZipFile, or None when Meteologica has nothing for it."""
        url = f'{API}/contents/{content_id}/historical_data/{year}/{month}'
        for attempt in range(4):
            r = requests.get(url, params={'token': self.token}, timeout=120)
            if r.status_code == 401:
                self.token = self._login()
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code == 404:
                return None
            r.raise_for_status()
            if not r.content.startswith(b'PK'):
                return None
            return zipfile.ZipFile(io.BytesIO(r.content))
        raise RuntimeError(f'Meteologica {content_id} {year}-{month:02d}: gave up after retries')


def _utc(local: str, offset: str | None) -> datetime:
    """'2026-09-02 23:00' plus 'UTC+0300' -> aware UTC datetime. Turkey is UTC+3 all year."""
    sign, hh, mm = 1, 3, 0
    if offset and offset.startswith('UTC') and len(offset) == 8:
        sign = -1 if offset[3] == '-' else 1
        hh, mm = int(offset[4:6]), int(offset[6:8])
    naive = datetime.strptime(local, '%Y-%m-%d %H:%M')
    return (naive - sign * timedelta(hours=hh, minutes=mm)).replace(tzinfo=timezone.utc)


def _issue_time(name: str, doc: dict) -> datetime:
    """When a forecast file was issued, in UTC."""
    issued = doc.get('issue_date')
    if issued:
        return datetime.strptime(issued[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    # Older files without issue_date: update_id / file name are Istanbul time
    stamp = str(doc.get('update_id') or name.split('_')[1][:12])
    return _utc(f'{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[8:10]}:{stamp[10:12]}', None)


def add_nowcasts(best: dict, archive: zipfile.ZipFile):
    """Fold one month archive into best = {utc hour: (issued, value)}.

    Keeps, for every hour, the value from the latest forecast issued before it began.
    """
    for name in archive.namelist():
        if not name.endswith('.json'):
            continue
        try:
            doc = json.loads(archive.read(name))
            issued = _issue_time(name, doc)
        except (ValueError, KeyError, IndexError):
            continue
        for entry in (doc.get('data') or [])[:LEAD_HOURS]:
            try:
                hour = _utc(entry['From yyyy-mm-dd hh:mm'], entry.get('UTC offset from (UTC+/-hhmm)'))
                value = float(entry['forecast'])
            except (KeyError, ValueError, TypeError):
                continue
            if issued >= hour:
                continue
            held = best.get(hour)
            if held is None or issued > held[0]:
                best[hour] = (issued, value)


def _months(start: date, end: date):
    d = start.replace(day=1)
    while d <= end:
        yield d.year, d.month
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def build_nowcasts(client: _Client, content_id: int, start: date, end: date, pause: float = 0):
    """{utc hour: value} for start..end (UTC dates), from the archives that can hold them."""
    best = {}
    # A month's first hours come from forecasts issued the previous evening, which
    # sit in the previous month's archive
    for i, (y, m) in enumerate(_months(start - timedelta(days=1), end)):
        if i and pause:
            time.sleep(pause)
        archive = client.month_zip(content_id, y, m)
        if archive is not None:
            add_nowcasts(best, archive)
    lo = datetime.combine(start, datetime.min.time(), timezone.utc)
    hi = datetime.combine(end + timedelta(days=1), datetime.min.time(), timezone.utc)
    return {h: v for h, (_, v) in best.items() if lo <= h < hi}


def write_hours(model, column: str, values: dict):
    """Upsert {utc hour: value}; returns (added, changed)."""
    if not values:
        return 0, 0
    lo, hi = min(values), max(values)
    stored = {
        row[0].astimezone(timezone.utc): row[1]
        for row in db.session.execute(
            text(f'SELECT datetime, {column} FROM {model.__tablename__} WHERE datetime >= :a AND datetime <= :b'),
            {'a': lo, 'b': hi})
    }
    now = datetime.now(timezone.utc)
    rows, added, changed = [], 0, 0
    for hour, value in values.items():
        old = stored.get(hour)
        if old is None:
            added += 1
        elif abs(old - value) > TOLERANCE_MW:
            changed += 1
        else:
            continue
        rows.append({'datetime': hour, column: value, 'created_at': now})
    # Chunked multi-row upserts: a full rebuild is ~57k rows per table
    for i in range(0, len(rows), 2000):
        stmt = insert(model.__table__).values(rows[i:i + 2000])
        db.session.execute(stmt.on_conflict_do_update(
            index_elements=['datetime'],
            set_={column: stmt.excluded[column], 'created_at': stmt.excluded.created_at}))
    db.session.commit()
    return added, changed


def sync_solar(start: date, end: date, pause: float = 0):
    """Rebuild both solar tables for start..end from Meteologica's archives.

    Returns {'licensed': {'hours', 'added', 'changed'}, 'unlicensed': {...}}.
    """
    client = _Client()
    stats = {}
    for name, (content_id, model, column) in CONTENTS.items():
        values = build_nowcasts(client, content_id, start, end, pause)
        added, changed = write_hours(model, column, values)
        stats[name] = {'hours': len(values), 'added': added, 'changed': changed}
    return stats
