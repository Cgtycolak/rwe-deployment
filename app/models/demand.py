from app.database.config import db
from datetime import datetime
from sqlalchemy import func

class DemandData(db.Model):
    __tablename__ = 'demand_data'
    
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False, unique=True)
    consumption = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())
    
    def __repr__(self):
        return f"<DemandData(datetime='{self.datetime}', consumption={self.consumption})>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'datetime': self.datetime,
            'consumption': self.consumption,
            'created_at': self.created_at
        } 