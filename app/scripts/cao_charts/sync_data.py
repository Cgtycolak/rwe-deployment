"""Sync the CAO chart tables with their sources for any date range.

The scheduler (app/tasks/scheduler.py) keeps these current; use this script for
backfills or to re-check history by hand. Every run adds missing hours and
overwrites changed ones, so it is safe to repeat.

    python app/scripts/cao_charts/sync_data.py production --start 2016-01-01
    python app/scripts/cao_charts/sync_data.py demand --start 2024-01-01 --end 2024-12-31
    python app/scripts/cao_charts/sync_data.py solar --start 2020-05-01

Long ranges take a while: EPIAS answers about one month per 10-20 seconds, and
Meteologica sends a 5-8 MB archive per month per solar table.
"""
import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from app import app  # noqa: E402  (importing the package builds the app)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('dataset', choices=['production', 'demand', 'solar'])
    parser.add_argument('--start', type=date.fromisoformat, required=True)
    parser.add_argument('--end', type=date.fromisoformat, default=date.today())
    args = parser.parse_args()

    with app.app_context():
        if args.dataset == 'production':
            from app.services.production_sync import sync_production
            stats = sync_production(args.start, args.end)
        elif args.dataset == 'demand':
            from app.services.demand_sync import sync_demand
            stats = sync_demand(args.start, args.end)
        else:
            from app.services.solar_sync import sync_solar
            stats = sync_solar(args.start, args.end, pause=1)
    print(stats)


if __name__ == '__main__':
    main()
