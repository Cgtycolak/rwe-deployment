from datetime import datetime
from ..database.config import db

class HydroHeatmapData(db.Model):
    __tablename__ = 'hydro_heatmap_data'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    plant_name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float, nullable=False)
    version = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('date', 'hour', 'plant_name', 'version', name='hydro_heatmap_data_date_hour_plant_name_version_key'),
    )

class NaturalGasHeatmapData(db.Model):
    __tablename__ = 'natural_gas_heatmap_data'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    plant_name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float, nullable=False)
    version = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('date', 'hour', 'plant_name', 'version', name='natural_gas_heatmap_data_date_hour_plant_name_version_key'),
    )

class ImportedCoalHeatmapData(db.Model):
    __tablename__ = 'imported_coal_heatmap_data'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    plant_name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float, nullable=False)
    version = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('date', 'hour', 'plant_name', 'version', name='imported_coal_heatmap_data_date_hour_plant_name_version_key'),
    )

class LigniteHeatmapData(db.Model):
    __tablename__ = 'lignite_heatmap_data'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    plant_name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float, nullable=False)
    version = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('date', 'hour', 'plant_name', 'version', name='lignite_heatmap_data_date_hour_plant_name_version_key'),
    )