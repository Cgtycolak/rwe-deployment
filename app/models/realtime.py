from ..database.config import db

class HydroRealtimeData(db.Model):
    __tablename__ = 'hydro_realtime_data'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    plant_name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float)
    
    __table_args__ = (
        db.UniqueConstraint('date', 'hour', 'plant_name', name='unique_hydro_realtime_record'),
    )

class NaturalGasRealtimeData(db.Model):
    __tablename__ = 'natural_gas_realtime_data'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    plant_name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float)
    
    __table_args__ = (
        db.UniqueConstraint('date', 'hour', 'plant_name', name='unique_natural_gas_realtime_record'),
    )

class LigniteRealtimeData(db.Model):
    __tablename__ = 'lignite_realtime_data'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    plant_name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float)
    
    __table_args__ = (
        db.UniqueConstraint('date', 'hour', 'plant_name', name='unique_lignite_realtime_record'),
    ) 