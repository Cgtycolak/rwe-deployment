from ..database.config import db
from datetime import datetime, timezone

class LicensedSolarData(db.Model):
    __tablename__ = 'licensed_solar_data'
    
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False, unique=True)
    licensed_solar = db.Column(db.Float, nullable=False)
    installed_capacity = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<LicensedSolarData {self.datetime}: {self.licensed_solar}>' 