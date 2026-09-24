"""Fetch daily generation for the mapped hydro plants into hydro_daily_generation.

EPIAS returns hourly rows and accepts a date range of up to 90 days per request,
so one call covers a plant's whole quarter. Cost is therefore one request per
plant per quarter, and the pace is set by the gateway's per-minute quota rather
than by the size of the range. Must run from the scheduler or a CLI, never inside
a web request.
"""
import argparse
import os
import sys
import time
import threading
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import requests

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(parent_dir)

from app.database.config import db
from app.models.hydro_map import HydroDailyGeneration, HydroPlant

MAX_RANGE_DAYS = 90       # EPIAS rejects 100+ days with HTTP 400
MAX_ATTEMPTS = 6

# Measured ceiling: hammering serially with no delay sustains ~88 successful
# requests/minute. Concurrency does not raise it — 5 and 12 workers both came in
# slightly LOWER (84 and 81/min) while generating thousands of rejections, so the
# quota is enforced server-side and extra workers only add noise. Sitting just
# under the ceiling keeps throughput without a storm of 429s.
REQUESTS_PER_MINUTE = 85

# A single thread is latency-bound rather than quota-bound: 12 sequential requests
# per plant at 0.5-1.3 s each only reaches ~55/min, well under the ceiling. Workers
# overlap that waiting so the shared budget becomes the limit instead of the round
# trip. They cannot overshoot the quota — the budget gates every request — so this
# is sized generously enough to keep it saturated.
FETCH_WORKERS = 6

# The quota refills continuously rather than resetting on a fixed boundary: after
# a 429 the next request succeeds within a second or two, so a long sleep wastes
# far more time than it saves.
RATE_LIMIT_WAIT = 2.0
FLUSH_EVERY_PLANTS = 25   # rows are bulk-upserted in batches, not one by one


class RateBudget:
    """Allow at most `per_minute` requests in any rolling 60-second window.

    Shared across worker threads, so the quota is respected in aggregate rather
    than per worker.
    """

    def __init__(self, per_minute=REQUESTS_PER_MINUTE):
        self.per_minute = per_minute
        self.stamps = deque()
        self.lock = threading.Lock()

    def take(self):
        while True:
            with self.lock:
                now = time.monotonic()
                while self.stamps and now - self.stamps[0] >= 60:
                    self.stamps.popleft()
                if len(self.stamps) < self.per_minute:
                    self.stamps.append(now)
                    return
                wait = 60 - (now - self.stamps[0]) + 0.05
            if wait > 0:
                time.sleep(min(wait, 1.0))

    def throttle(self):
        """Ease off after a 429: shed 10% of the budget, with a floor.

        Dropping the rate beats sleeping out the window, because the quota
        refills continuously — the point is to stop overshooting, not to stop.
        """
        with self.lock:
            self.per_minute = max(40, int(self.per_minute * 0.9))


def date_chunks(start_date, end_date):
    """Split an inclusive range into pieces EPIAS will accept."""
    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(cursor + timedelta(days=MAX_RANGE_DAYS - 1), end_date)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def fetch_plant_range(app, session, headers, epias_id, start_date, end_date, budget):
    """Daily {date: [river, dammed, total]} for one plant, or None if it failed."""
    daily = defaultdict(lambda: [0.0, 0.0, 0.0])
    for chunk_start, chunk_end in date_chunks(start_date, end_date):
        payload = {
            "startDate": f"{chunk_start}T00:00:00+03:00",
            "endDate": f"{chunk_end}T23:00:00+03:00",
            "powerPlantId": str(epias_id),
        }
        for _ in range(MAX_ATTEMPTS):
            budget.take()
            try:
                r = session.post(app.config['REALTIME_URL'], json=payload,
                                 headers=headers, timeout=120)
            except Exception as e:
                app.logger.warning(f"hydro map: request failed for {epias_id}: {e}")
                time.sleep(3)
                continue
            if r.status_code == 200:
                for item in r.json().get('items', []):
                    day = str(item.get('date', ''))[:10]
                    if not day:
                        continue
                    bucket = daily[day]
                    bucket[0] += item.get('river', 0) or 0
                    bucket[1] += item.get('dammedHydro', 0) or 0
                    bucket[2] += item.get('total', 0) or 0
                break
            if r.status_code == 429:
                budget.throttle()
                time.sleep(RATE_LIMIT_WAIT)
                continue
            app.logger.warning(f"hydro map: HTTP {r.status_code} for plant {epias_id}")
            return None
        else:
            return None
    return daily


def upsert_rows(rows):
    """Bulk insert/update. One statement per batch, because the ORM's row-by-row
    path costs a database round trip per row — punishing over a long link."""
    if not rows:
        return 0
    from psycopg2.extras import execute_values
    raw = db.session.connection().connection
    with raw.cursor() as cur:
        execute_values(cur, """
            INSERT INTO hydro_daily_generation
                (date, epias_id, plant_name, river_mwh, dammed_mwh, total_mwh, updated_at)
            VALUES %s
            ON CONFLICT (date, epias_id) DO UPDATE SET
                plant_name = EXCLUDED.plant_name,
                river_mwh  = EXCLUDED.river_mwh,
                dammed_mwh = EXCLUDED.dammed_mwh,
                total_mwh  = EXCLUDED.total_mwh,
                updated_at = EXCLUDED.updated_at
        """, rows, page_size=1000)
    db.session.commit()
    return len(rows)


def populate_hydro_generation(app, start_date, end_date=None, refresh=False,
                              per_minute=REQUESTS_PER_MINUTE):
    """Fetch and store generation for every mapped plant over an inclusive range.

    Plants already holding every day in the range are skipped, so an interrupted
    run (rate limit, restart, laptop sleep) resumes instead of starting over.
    Pass refresh=True to re-pull days whose numbers may have been revised.
    """
    end_date = end_date or start_date
    if end_date < start_date:
        raise ValueError("end_date is before start_date")

    plants = HydroPlant.query.order_by(HydroPlant.epias_id).all()
    wanted_days = (end_date - start_date).days + 1
    total_plants = len(plants)

    if not refresh:
        have = defaultdict(int)
        rows = db.session.query(
            HydroDailyGeneration.epias_id, db.func.count()
        ).filter(
            HydroDailyGeneration.date.between(start_date, end_date)
        ).group_by(HydroDailyGeneration.epias_id).all()
        for epias_id, count in rows:
            have[epias_id] = count
        pending = [p for p in plants if have.get(p.epias_id, 0) < wanted_days]
        if len(pending) != len(plants):
            app.logger.info(f"hydro map: {len(plants) - len(pending)} plants already complete, "
                            f"{len(pending)} to fetch")
        plants = pending

    chunks = len(list(date_chunks(start_date, end_date)))
    app.logger.info(f"hydro map: {len(plants)} plants x {wanted_days} days "
                    f"({start_date} to {end_date}), {len(plants) * chunks} requests, "
                    f"~{len(plants) * chunks / max(per_minute, 1):.0f} min at {per_minute}/min")

    budget = RateBudget(per_minute)
    now = datetime.utcnow()
    pending_rows, stored, failed = [], 0, 0
    started = time.monotonic()

    headers = {"TGT": get_token(app), "Accept": "application/json",
               "Content-Type": "application/json"}
    local = threading.local()

    # Hand workers plain tuples, never ORM objects: committing a batch expires the
    # instances, and a worker touching an expired attribute triggers a lazy reload
    # that needs the Flask app context it does not have.
    targets = [(p.epias_id, p.name) for p in plants]

    def fetch_one(target):
        epias_id, name = target
        # one Session per worker thread; Session is not safe to share
        if not hasattr(local, 'session'):
            local.session = requests.Session()
        return target, fetch_plant_range(app, local.session, headers, epias_id,
                                         start_date, end_date, budget)

    # Workers only do HTTP. Rows come back to this thread for writing, because the
    # SQLAlchemy session must not be touched concurrently.
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        for i, ((epias_id, plant_name), daily) in enumerate(pool.map(fetch_one, targets), 1):
            if daily is None:
                failed += 1
            else:
                for day_str, (river, dammed, total) in daily.items():
                    day = datetime.strptime(day_str, '%Y-%m-%d').date()
                    pending_rows.append((day, epias_id, plant_name,
                                         river, dammed, total, now))

            if i % FLUSH_EVERY_PLANTS == 0:
                stored += upsert_rows(pending_rows)
                pending_rows = []
                rate = i / max(time.monotonic() - started, 1) * 60
                left = (len(plants) - i) / max(rate, 0.01)
                app.logger.info(f"hydro map: {i}/{len(plants)} plants, {stored:,} rows, "
                                f"{rate:.1f} plants/min, ~{left:.0f} min left")

    stored += upsert_rows(pending_rows)
    app.logger.info(f"hydro map: {start_date}..{end_date} finished — "
                    f"{stored:,} rows stored, {failed} plants failed")
    return stored, failed


def get_token(app):
    from app.functions import get_tgt_token
    return get_tgt_token(app.config.get('USERNAME'), app.config.get('PASSWORD'))


def main():
    from app.factory import create_app
    parser = argparse.ArgumentParser(description='Populate daily hydro generation for the map')
    parser.add_argument('--date', help='single day, YYYY-MM-DD (default: yesterday)')
    parser.add_argument('--start-date', help='range start, YYYY-MM-DD')
    parser.add_argument('--end-date', help='range end, YYYY-MM-DD (default: yesterday)')
    parser.add_argument('--refresh', action='store_true', help='re-fetch days already stored')
    parser.add_argument('--per-minute', type=int, default=REQUESTS_PER_MINUTE,
                        help=f'request budget per minute (default {REQUESTS_PER_MINUTE})')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        yesterday = (datetime.now() - timedelta(days=1)).date()
        if args.start_date:
            start = datetime.strptime(args.start_date, '%Y-%m-%d').date()
            end = datetime.strptime(args.end_date, '%Y-%m-%d').date() if args.end_date else yesterday
        elif args.date:
            start = end = datetime.strptime(args.date, '%Y-%m-%d').date()
        else:
            start = end = yesterday
        stored, failed = populate_hydro_generation(app, start, end,
                                                   refresh=args.refresh,
                                                   per_minute=args.per_minute)
        print(f"{start}..{end}: {stored:,} rows stored, {failed} plants failed")


if __name__ == '__main__':
    main()
