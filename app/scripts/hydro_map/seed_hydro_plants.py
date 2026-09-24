"""Seed the hydro_plants table from the static build artifact.

hydro_plants.json is the versioned output of the offline matching pipeline
(licence file + EPIAS powerplant list + district geocoding). This loads it into
the database, which is what the app actually queries. Re-running is safe: rows
are matched on epias_id and updated in place.
"""
import argparse
import json
import os
import sys
from datetime import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(parent_dir)

from app.database.config import db
from app.models.hydro_map import HydroPlant

# hydro_plants.json still carries the Turkish field names the pipeline produced
FIELD_MAP = {
    'name': 'tesis',
    'epias_name': 'epias_ad',
    'province': 'il',
    'district': 'ilce',
    'installed_mw': 'kurulu_mwm',
    'operating_mw': 'isletmede_mwm',
    'plant_type': 'sinif',
    'latitude': 'lat',
    'longitude': 'lon',
    'location_source': 'konum_kaynak',
}
TYPE_MAP = {'akarsu': 'river', 'barajli': 'dammed'}


def load_regions(app):
    """Province -> NUTS1 region, used to roll districts up when the map zooms out."""
    path = os.path.join(app.static_folder, 'data', 'tr-province-regions.json')
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    return {_province_key(k): v['region_en'] for k, v in raw.items()}


def _province_key(name):
    text = str(name).upper()
    for a, b in [('\u0130', 'I'), ('I', 'I'), ('\u015e', 'S'), ('\u011e', 'G'),
                 ('\u00dc', 'U'), ('\u00d6', 'O'), ('\u00c7', 'C')]:
        text = text.replace(a, b)
    return text.strip()


def seed_hydro_plants(app):
    path = os.path.join(app.static_folder, 'data', 'hydro_plants.json')
    with open(path, encoding='utf-8') as f:
        plants = json.load(f)
    regions = load_regions(app)

    existing = {p.epias_id: p for p in HydroPlant.query.all()}
    added = updated = 0

    for item in plants:
        epias_id = int(item['epias_id'])
        row = existing.get(epias_id)
        if row is None:
            row = HydroPlant(epias_id=epias_id)
            db.session.add(row)
            added += 1
        else:
            updated += 1
        for column, source in FIELD_MAP.items():
            value = item.get(source)
            if column == 'plant_type':
                value = TYPE_MAP.get(value)
            setattr(row, column, value)
        row.region = regions.get(_province_key(item.get('il')))
        row.updated_at = datetime.utcnow()

    db.session.commit()
    return added, updated, len(plants)


def main():
    from app.factory import create_app
    argparse.ArgumentParser(description='Seed hydro_plants from hydro_plants.json').parse_args()
    app = create_app()
    with app.app_context():
        added, updated, total = seed_hydro_plants(app)
        print(f"{total} plants in file: {added} added, {updated} updated")


if __name__ == '__main__':
    main()
