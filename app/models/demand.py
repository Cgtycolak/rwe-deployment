from app.database.config import db
from datetime import datetime

class DemandData(db.Model):
    __tablename__ = 'demand_data'
    
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False, unique=True)
    consumption = db.Column(db.Float, nullable=False)
    
    # Fix the created_at column by using a function reference correctly
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow(), nullable=True)
    
    def __repr__(self):
        return f"<DemandData(datetime='{self.datetime}', consumption={self.consumption})>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'datetime': self.datetime,
            'consumption': self.consumption
        } 