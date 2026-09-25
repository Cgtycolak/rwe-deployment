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
from app.models.hydro_map import HydroDailyGeneration, HydroPlant

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


def load_aliases(app):
    """Hand-curated licence-name -> EPIAS id fixes.

    Name matching tops out well short of the full fleet because EPIAS files some
    plants under a different name entirely (Yedigöze appears as Sanibey). Those
    cannot be inferred, so they are recorded by hand here rather than papered over
    with a looser fuzzy match that would introduce wrong pairings elsewhere.
    """
    path = os.path.join(app.static_folder, 'data', 'hydro_plant_aliases.json')
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return json.load(f).get('aliases', [])


def apply_aliases(app, licence_rows):
    """Fold curated aliases into the licence-derived plant list."""
    aliases = load_aliases(app)
    if not aliases:
        return licence_rows, 0

    import pandas as pd
    licence_path = os.path.join(app.static_folder, 'data',
                                'Elektrik Üretim Lisanslar_ (2).xls')
    licence = pd.ExcelFile(licence_path).parse('Lisanslar')
    licence = licence[licence['Tesis Türü'] == 'Hidroelektrik'].drop_duplicates('Tesis Adı')
    by_name = licence.set_index('Tesis Adı')

    by_epias = {int(r['epias_id']): r for r in licence_rows}
    by_licence = {r['tesis']: r for r in licence_rows}
    aliased_names = {a['licence_name'] for a in aliases}
    added = 0

    for alias in aliases:
        name, epias_id = alias['licence_name'], int(alias['epias_id'])
        if name not in by_name.index:
            app.logger.warning(f"alias skipped, not in licence file: {name}")
            continue

        # An id automatic matching gave to the wrong licence is moved here, but only
        # when the displaced plant has its own alias entry — otherwise a typo would
        # silently strip a correct match.
        holder = by_epias.get(epias_id)
        if holder is not None and holder['tesis'] != name:
            if holder['tesis'] not in aliased_names:
                app.logger.warning(f"alias skipped, id {epias_id} already held by "
                                   f"{holder['tesis']} and no alias reassigns it")
                continue
            app.logger.info(f"alias moves epias id {epias_id}: "
                            f"{holder['tesis']} -> {name}")
            licence_rows.remove(holder)
            by_epias.pop(epias_id, None)
            by_licence.pop(holder['tesis'], None)

        existing = by_licence.get(name)
        if existing is not None:
            if int(existing['epias_id']) == epias_id:
                continue
            licence_rows.remove(existing)
            by_epias.pop(int(existing['epias_id']), None)

        row = by_name.loc[name]
        new_row = {
            'tesis': name,
            'epias_id': epias_id,
            'epias_ad': alias.get('epias_name'),
            'il': row['İl'],
            'ilce': row['İlçe'],
            'kurulu_mwm': float(row['Kurulu Güç (MWm)']),
            'isletmede_mwm': float(row['İşletmedeki Kapasite (MWm)'] or 0),
            'sinif': None,          # resolved from the first generation data fetched
            'lat': None,            # filled below from the district it shares
            'lon': None,
            'konum_kaynak': None,
        }
        licence_rows.append(new_row)
        by_epias[epias_id] = new_row
        by_licence[name] = new_row
        added += 1

    # aliased plants inherit coordinates from another plant in the same district
    coords = {(r['il'], r['ilce']): (r['lat'], r['lon'], r['konum_kaynak'])
              for r in licence_rows if r.get('lat') is not None}
    for r in licence_rows:
        if r.get('lat') is None:
            hit = coords.get((r['il'], r['ilce']))
            if hit:
                r['lat'], r['lon'], r['konum_kaynak'] = hit
    return licence_rows, added


def seed_hydro_plants(app):
    path = os.path.join(app.static_folder, 'data', 'hydro_plants.json')
    with open(path, encoding='utf-8') as f:
        plants = json.load(f)
    plants, aliased = apply_aliases(app, plants)
    if aliased:
        app.logger.info(f"seed: {aliased} plants added from the alias list")
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
            if column == 'plant_type':
                # deliberately not written here — classify_plants() derives it from
                # stored generation, which is authoritative and covers a far wider
                # window than the short sample hydro_plants.json was built from.
                # Writing the file's value would undo that on every re-seed.
                continue
            setattr(row, column, item.get(source))
        row.region = regions.get(_province_key(item.get('il')))
        row.updated_at = datetime.utcnow()

    db.session.commit()
    return added, updated, len(plants)


def classify_plants(app):
    """Set plant_type from stored generation: river vs dammed as EPIAS reports it.

    A plant with no output at all stays unclassified rather than being guessed
    from size — a 50 MW threshold was measured against reality and disagreed 20%
    of the time.
    """
    totals = {
        epias_id: (river or 0, dammed or 0)
        for epias_id, river, dammed in db.session.query(
            HydroDailyGeneration.epias_id,
            db.func.sum(HydroDailyGeneration.river_mwh),
            db.func.sum(HydroDailyGeneration.dammed_mwh),
        ).group_by(HydroDailyGeneration.epias_id).all()
    }

    counts = {'river': 0, 'dammed': 0, 'unclassified': 0}
    for plant in HydroPlant.query.all():
        river, dammed = totals.get(plant.epias_id, (0, 0))
        if river == 0 and dammed == 0:
            plant.plant_type = None
            counts['unclassified'] += 1
        else:
            plant.plant_type = 'river' if river > dammed else 'dammed'
            counts[plant.plant_type] += 1
    db.session.commit()
    return counts


def main():
    from app.factory import create_app
    argparse.ArgumentParser(description='Seed hydro_plants from hydro_plants.json').parse_args()
    app = create_app()
    with app.app_context():
        added, updated, total = seed_hydro_plants(app)
        counts = classify_plants(app)
        print(f"{total} plants: {added} added, {updated} updated")
        print(f"classified from generation: {counts['river']} river, "
              f"{counts['dammed']} dammed, {counts['unclassified']} unclassified")


if __name__ == '__main__':
    main()
