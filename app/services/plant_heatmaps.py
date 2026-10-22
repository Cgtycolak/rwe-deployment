"""Hour x plant matrices for the per-fuel DPP heatmap tabs (natural gas, import coal, hydro, lignite).

Each fuel reads its stored rows first; the scheduler fills those tables (see
app/scripts/dpp_charts/). A day that is not stored is fetched from EPIAS plant by
plant. Planned (DPP) values are only returned, never stored. Realtime values for
a finished day are stored, so the next visit is instant; today's are not,
because the day is still incomplete.
"""
import time
from dataclasses import dataclass
from datetime import datetime

import pytz
import requests
from flask import current_app

from ..database.config import db
from ..mappings import hydro_mapping, import_coal_mapping, lignite_mapping, plant_mapping
from ..models.heatmap import HydroHeatmapData, ImportedCoalHeatmapData, LigniteHeatmapData, NaturalGasHeatmapData
from ..models.realtime import HydroRealtimeData, LigniteRealtimeData, NaturalGasRealtimeData
from .epias import epias_session

HOURS = [f"{h:02d}:00" for h in range(24)]
EPIAS_PAUSE_SECONDS = 0.5  # between plants, to stay inside EPIAS's rate limit


@dataclass(frozen=True)
class Fuel:
    mapping: dict
    plan_model: type
    realtime_model: type = None
    # DPP field for this fuel; the plant total ('toplam') is used when it is empty
    plan_field: str = None
    label_key: str = 'plant_names'
    label_format: str = '{name} ({capacity} MW)'

    @property
    def names(self):
        return self.mapping['plant_names']

    def labels(self):
        return [self.label_format.format(name=n, capacity=c)
                for n, c in zip(self.mapping[self.label_key], self.mapping['capacities'])]


FUELS = {
    'natural_gas': Fuel(plant_mapping, NaturalGasHeatmapData, NaturalGasRealtimeData, label_key='display_names'),
    'import_coal': Fuel(import_coal_mapping, ImportedCoalHeatmapData, plan_field='ithalKomur'),
    'hydro': Fuel(hydro_mapping, HydroHeatmapData, HydroRealtimeData, plan_field='barajli'),
    'lignite': Fuel(lignite_mapping, LigniteHeatmapData, LigniteRealtimeData, plan_field='linyit',
                    label_format='{name}--{capacity} MW'),
}


def _istanbul_today():
    return datetime.now(pytz.timezone('Europe/Istanbul')).date()


def _matrix(rows, names):
    """24 x len(names) values from stored rows. Rows for plants no longer in the mapping are ignored."""
    column = {name: i for i, name in enumerate(names)}
    values = [[0.0] * len(names) for _ in HOURS]
    for row in rows:
        if row.plant_name in column and 0 <= row.hour < 24:
            values[row.hour][column[row.plant_name]] = row.value or 0
    return values


def plan_values(fuel, day, version):
    """DPP matrix for one day and version ('first' or 'current')."""
    rows = fuel.plan_model.query.filter_by(date=day, version=version).all()
    if rows:
        return _matrix(rows, fuel.names)

    current_app.logger.info("No %s DPP stored for %s (%s), fetching from EPIAS", fuel.plan_model.__tablename__, day, version)
    url = current_app.config['DPP_FIRST_VERSION_URL' if version == 'first' else 'DPP_URL']
    values = [[0.0] * len(fuel.names) for _ in HOURS]
    with epias_session() as session:
        for col, (name, org_id, uevcb_id) in enumerate(zip(fuel.names, fuel.mapping['o_ids'], fuel.mapping['uevcb_ids'])):
            try:
                response = session.post(url, timeout=30, json={
                    'startDate': f'{day}T00:00:00+03:00', 'endDate': f'{day}T00:00:00+03:00',
                    'region': 'TR1', 'organizationId': int(org_id), 'uevcbId': int(uevcb_id)})
                response.raise_for_status()
                items = response.json().get('items', [])
            except (requests.RequestException, ValueError) as e:
                current_app.logger.warning("DPP fetch failed for %s: %s", name, e)
                items = []
            for item in items:
                value = item.get(fuel.plan_field) if fuel.plan_field else None
                if value is None:
                    value = item.get('toplam')
                try:
                    values[int(item.get('time', '00:00').split(':')[0])][col] = float(value)
                except (TypeError, ValueError, IndexError):
                    continue
            time.sleep(EPIAS_PAUSE_SECONDS)
    return values


def realtime_values(fuel, day):
    """Realtime generation matrix for one day."""
    rows = fuel.realtime_model.query.filter_by(date=day).all()
    if rows:
        return _matrix(rows, fuel.names)

    current_app.logger.info("No %s stored for %s, fetching from EPIAS", fuel.realtime_model.__tablename__, day)
    values, records = _fetch_realtime(fuel, day)
    if records and day < _istanbul_today():
        db.session.bulk_insert_mappings(fuel.realtime_model, records)
        db.session.commit()
    return values


def _fetch_realtime(fuel, day):
    """(matrix, rows to store). Plants sharing a power plant id split its output evenly;
    plants without a valid id get zeros."""
    columns_by_plant = {}
    for col, p_id in enumerate(fuel.mapping['p_ids']):
        columns_by_plant.setdefault(p_id, []).append(col)

    values = [[0.0] * len(fuel.names) for _ in HOURS]
    records = []

    def keep(cols, hourly):
        for col in cols:
            for hour, value in enumerate(hourly):
                values[hour][col] = value
                records.append({'date': day, 'hour': hour, 'plant_name': fuel.names[col], 'value': value})

    with epias_session() as session:
        for p_id, cols in columns_by_plant.items():
            if not p_id or p_id <= 0:
                keep(cols, [0.0] * 24)
                continue
            try:
                response = session.post(current_app.config['REALTIME_URL'], timeout=30, json={
                    'startDate': f'{day}T00:00:00+03:00', 'endDate': f'{day}T23:59:59+03:00',
                    'powerPlantId': str(p_id)})
                response.raise_for_status()
                hourly = [0] * 24
                for item in response.json().get('items', []):
                    hourly[int(item.get('hour', '00:00').split(':')[0])] = item.get('total', 0)
                keep(cols, [v / len(cols) for v in hourly])
            except Exception as e:  # one plant failing leaves its columns at zero
                current_app.logger.warning("Realtime fetch failed for power plant %s: %s", p_id, e)
            time.sleep(EPIAS_PAUSE_SECONDS)
    return values, records
