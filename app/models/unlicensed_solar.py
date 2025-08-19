from ..database.config import db
from datetime import datetime, timezone

class UnlicensedSolarData(db.Model):
    __tablename__ = 'unlicensed_solar_data'
    
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False, unique=True)
    unlicensed_solar = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<UnlicensedSolarData {self.datetime}: {self.unlicensed_solar}>' 