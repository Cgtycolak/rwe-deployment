"""Backfill the Generation by Source heatmap tables.

    python app/scripts/dpp_charts/populate_source_heatmap.py --start-date 2024-01-01 --end-date 2026-10-15

Fills source_heatmap_data (system-wide DPP, first and current versions) and
unlicensed_generation_data (EPIAS metered unlicensed generation). Both are
fetched a month per call and replace what is stored for the days returned, so
re-running over a range is safe.
"""
import os
import sys
import argparse
from datetime import datetime

# Project root (three levels up: dpp_charts -> scripts -> app -> root), so the
# script runs from any working directory.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

from app.factory import create_app
from app.functions import get_tgt_token
from app.services.source_heatmap import populate_source_plan, populate_unlicensed_generation


def main():
    parser = argparse.ArgumentParser(description='Backfill the Generation by Source heatmap')
    parser.add_argument('--start-date', required=True, help='YYYY-MM-DD')
    parser.add_argument('--end-date', required=True, help='YYYY-MM-DD')
    parser.add_argument('--skip-plan', action='store_true', help='Skip the DPP first/current versions')
    parser.add_argument('--skip-unlicensed', action='store_true', help='Skip EPIAS metered unlicensed generation')
    args = parser.parse_args()

    start = datetime.strptime(args.start_date, '%Y-%m-%d').date()
    end = datetime.strptime(args.end_date, '%Y-%m-%d').date()
    if start > end:
        sys.exit('End date must be after start date')

    app = create_app()
    with app.app_context():
        token = get_tgt_token(app.config.get('USERNAME'), app.config.get('PASSWORD'))
        if not args.skip_plan:
            rows = populate_source_plan(start, end, token=token)
            print(f'Source DPP: {rows} rows stored for {start} to {end}')
        if not args.skip_unlicensed:
            rows = populate_unlicensed_generation(start, end, token=token)
            print(f'Unlicensed generation: {rows} rows stored for {start} to {end}')


if __name__ == '__main__':
    main()
