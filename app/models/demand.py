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

class DemandRevision(db.Model):
    """One row each time EPIAS changes an hour that demand_data already held.

    EPIAS keeps revising realtime consumption for weeks after the hour. This log
    shows how late those revisions arrive, so the re-check window in
    app/services/demand_sync.py can be set from evidence rather than guessed.
    """
    __tablename__ = 'demand_revisions'

    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False, index=True)  # the hour that changed
    old_consumption = db.Column(db.Float, nullable=False)
    new_consumption = db.Column(db.Float, nullable=False)
    detected_at = db.Column(db.DateTime, nullable=False, default=func.now())
