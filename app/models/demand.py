from app.database.config import db
from datetime import datetime

class DemandData(db.Model):
    __tablename__ = 'demand_data'
    
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False, unique=True)
    consumption = db.Column(db.Float, nullable=False)
    
    # Make created_at optional to handle both schemas
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    
    def __repr__(self):
        return f"<DemandData(datetime='{self.datetime}', consumption={self.consumption})>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'datetime': self.datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'consumption': self.consumption,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        } 