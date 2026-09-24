from datetime import datetime
from ..database.config import db


class HydroPlant(db.Model):
    """Licensed hydro plants matched to their EPIAS realtime-generation id.

    Reference data rebuilt by the offline matching pipeline and seeded from
    static/data/hydro_plants.json. It lives in the database rather than being
    read from that file per request so it can join against HydroDailyGeneration
    and be corrected (new matches, renamed plants) without a redeploy.

    Location is province/district only — the EPDK licence export carries no
    coordinates — so lat/lon are the district centroid and several plants share
    the same point. Consumers should aggregate by district rather than imply
    per-plant precision.
    """
    __tablename__ = 'hydro_plants'

    id = db.Column(db.Integer, primary_key=True)
    epias_id = db.Column(db.Integer, nullable=False, unique=True, index=True)
    name = db.Column(db.String(150), nullable=False)
    epias_name = db.Column(db.String(150))
    region = db.Column(db.String(40), index=True)     # NUTS1, e.g. 'East Black Sea'
    province = db.Column(db.String(60), nullable=False)
    district = db.Column(db.String(60), nullable=False)
    installed_mw = db.Column(db.Float, nullable=False, default=0)   # licensed capacity
    operating_mw = db.Column(db.Float, nullable=False, default=0)   # capacity actually in service
    plant_type = db.Column(db.String(10), index=True)               # 'river' | 'dammed' | None
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    location_source = db.Column(db.String(30))                      # district centroid vs province fallback
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class HydroDailyGeneration(db.Model):
    """Daily generation per licensed hydro plant, used by the hydro map.

    One row per plant per day (~673/day). river/dammed come straight from EPIAS'
    realtime-generation fuel breakdown, which is also what classifies a plant as
    run-of-river vs dammed — the licence file does not carry that distinction.
    """
    __tablename__ = 'hydro_daily_generation'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    epias_id = db.Column(db.Integer, nullable=False)
    plant_name = db.Column(db.String(150), nullable=False)
    river_mwh = db.Column(db.Float, nullable=False, default=0)
    dammed_mwh = db.Column(db.Float, nullable=False, default=0)
    total_mwh = db.Column(db.Float, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('date', 'epias_id', name='unique_hydro_daily_generation'),
    )
