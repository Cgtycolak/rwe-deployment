from datetime import datetime
from ..database.config import db

class UnlicensedSolar(db.Model):
    __tablename__ = 'meteologica_unlicensed_solar'
    __table_args__ = {'schema': 'meteologica'}
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    forecasted = db.Column(db.Float, nullable=True)
    hour_0 = db.Column(db.Float, nullable=True)
    hour_1 = db.Column(db.Float, nullable=True)
    hour_2 = db.Column(db.Float, nullable=True)
    hour_3 = db.Column(db.Float, nullable=True)
    hour_4 = db.Column(db.Float, nullable=True)
    hour_5 = db.Column(db.Float, nullable=True)
    hour_6 = db.Column(db.Float, nullable=True)
    hour_7 = db.Column(db.Float, nullable=True)
    hour_8 = db.Column(db.Float, nullable=True)
    hour_9 = db.Column(db.Float, nullable=True)
    hour_10 = db.Column(db.Float, nullable=True)
    hour_11 = db.Column(db.Float, nullable=True)
    hour_12 = db.Column(db.Float, nullable=True)
    update_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'forecasted': self.forecasted,
            'hour_0': self.hour_0,
            'hour_1': self.hour_1,
            'hour_2': self.hour_2,
            'hour_3': self.hour_3,
            'hour_4': self.hour_4,
            'hour_5': self.hour_5,
            'hour_6': self.hour_6,
            'hour_7': self.hour_7,
            'hour_8': self.hour_8,
            'hour_9': self.hour_9,
            'hour_10': self.hour_10,
            'hour_11': self.hour_11,
            'hour_12': self.hour_12,
            'update_id': self.update_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class LicensedSolar(db.Model):
    __tablename__ = 'meteologica_licensed_solar'
    __table_args__ = {'schema': 'meteologica'}
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    forecasted = db.Column(db.Float, nullable=True)
    hour_0 = db.Column(db.Float, nullable=True)
    hour_1 = db.Column(db.Float, nullable=True)
    hour_2 = db.Column(db.Float, nullable=True)
    hour_3 = db.Column(db.Float, nullable=True)
    hour_4 = db.Column(db.Float, nullable=True)
    hour_5 = db.Column(db.Float, nullable=True)
    hour_6 = db.Column(db.Float, nullable=True)
    hour_7 = db.Column(db.Float, nullable=True)
    hour_8 = db.Column(db.Float, nullable=True)
    hour_9 = db.Column(db.Float, nullable=True)
    hour_10 = db.Column(db.Float, nullable=True)
    hour_11 = db.Column(db.Float, nullable=True)
    hour_12 = db.Column(db.Float, nullable=True)
    update_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'forecasted': self.forecasted,
            'hour_0': self.hour_0,
            'hour_1': self.hour_1,
            'hour_2': self.hour_2,
            'hour_3': self.hour_3,
            'hour_4': self.hour_4,
            'hour_5': self.hour_5,
            'hour_6': self.hour_6,
            'hour_7': self.hour_7,
            'hour_8': self.hour_8,
            'hour_9': self.hour_9,
            'hour_10': self.hour_10,
            'hour_11': self.hour_11,
            'hour_12': self.hour_12,
            'update_id': self.update_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Wind(db.Model):
    __tablename__ = 'meteologica_wind'
    __table_args__ = {'schema': 'meteologica'}
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    forecasted = db.Column(db.Float, nullable=True)
    hour_0 = db.Column(db.Float, nullable=True)
    hour_1 = db.Column(db.Float, nullable=True)
    hour_2 = db.Column(db.Float, nullable=True)
    hour_3 = db.Column(db.Float, nullable=True)
    hour_4 = db.Column(db.Float, nullable=True)
    hour_5 = db.Column(db.Float, nullable=True)
    hour_6 = db.Column(db.Float, nullable=True)
    hour_7 = db.Column(db.Float, nullable=True)
    hour_8 = db.Column(db.Float, nullable=True)
    hour_9 = db.Column(db.Float, nullable=True)
    hour_10 = db.Column(db.Float, nullable=True)
    hour_11 = db.Column(db.Float, nullable=True)
    hour_12 = db.Column(db.Float, nullable=True)
    update_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'forecasted': self.forecasted,
            'hour_0': self.hour_0,
            'hour_1': self.hour_1,
            'hour_2': self.hour_2,
            'hour_3': self.hour_3,
            'hour_4': self.hour_4,
            'hour_5': self.hour_5,
            'hour_6': self.hour_6,
            'hour_7': self.hour_7,
            'hour_8': self.hour_8,
            'hour_9': self.hour_9,
            'hour_10': self.hour_10,
            'hour_11': self.hour_11,
            'hour_12': self.hour_12,
            'update_id': self.update_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class DamHydro(db.Model):
    __tablename__ = 'meteologica_dam_hydro'
    __table_args__ = {'schema': 'meteologica'}
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    forecasted = db.Column(db.Float, nullable=True)
    hour_0 = db.Column(db.Float, nullable=True)
    hour_1 = db.Column(db.Float, nullable=True)
    hour_2 = db.Column(db.Float, nullable=True)
    hour_3 = db.Column(db.Float, nullable=True)
    hour_4 = db.Column(db.Float, nullable=True)
    hour_5 = db.Column(db.Float, nullable=True)
    hour_6 = db.Column(db.Float, nullable=True)
    hour_7 = db.Column(db.Float, nullable=True)
    hour_8 = db.Column(db.Float, nullable=True)
    hour_9 = db.Column(db.Float, nullable=True)
    hour_10 = db.Column(db.Float, nullable=True)
    hour_11 = db.Column(db.Float, nullable=True)
    hour_12 = db.Column(db.Float, nullable=True)
    update_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'forecasted': self.forecasted,
            'hour_0': self.hour_0,
            'hour_1': self.hour_1,
            'hour_2': self.hour_2,
            'hour_3': self.hour_3,
            'hour_4': self.hour_4,
            'hour_5': self.hour_5,
            'hour_6': self.hour_6,
            'hour_7': self.hour_7,
            'hour_8': self.hour_8,
            'hour_9': self.hour_9,
            'hour_10': self.hour_10,
            'hour_11': self.hour_11,
            'hour_12': self.hour_12,
            'update_id': self.update_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class RunOfRiverHydro(db.Model):
    __tablename__ = 'meteologica_runofriver_hydro'
    __table_args__ = {'schema': 'meteologica'}
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    forecasted = db.Column(db.Float, nullable=True)
    hour_0 = db.Column(db.Float, nullable=True)
    hour_1 = db.Column(db.Float, nullable=True)
    hour_2 = db.Column(db.Float, nullable=True)
    hour_3 = db.Column(db.Float, nullable=True)
    hour_4 = db.Column(db.Float, nullable=True)
    hour_5 = db.Column(db.Float, nullable=True)
    hour_6 = db.Column(db.Float, nullable=True)
    hour_7 = db.Column(db.Float, nullable=True)
    hour_8 = db.Column(db.Float, nullable=True)
    hour_9 = db.Column(db.Float, nullable=True)
    hour_10 = db.Column(db.Float, nullable=True)
    hour_11 = db.Column(db.Float, nullable=True)
    hour_12 = db.Column(db.Float, nullable=True)
    update_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'forecasted': self.forecasted,
            'hour_0': self.hour_0,
            'hour_1': self.hour_1,
            'hour_2': self.hour_2,
            'hour_3': self.hour_3,
            'hour_4': self.hour_4,
            'hour_5': self.hour_5,
            'hour_6': self.hour_6,
            'hour_7': self.hour_7,
            'hour_8': self.hour_8,
            'hour_9': self.hour_9,
            'hour_10': self.hour_10,
            'hour_11': self.hour_11,
            'hour_12': self.hour_12,
            'update_id': self.update_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Demand(db.Model):
    __tablename__ = 'meteologica_demand'
    __table_args__ = {'schema': 'meteologica'}
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    forecasted = db.Column(db.Float, nullable=True)
    hour_0 = db.Column(db.Float, nullable=True)
    hour_1 = db.Column(db.Float, nullable=True)
    hour_2 = db.Column(db.Float, nullable=True)
    hour_3 = db.Column(db.Float, nullable=True)
    hour_4 = db.Column(db.Float, nullable=True)
    hour_5 = db.Column(db.Float, nullable=True)
    hour_6 = db.Column(db.Float, nullable=True)
    hour_7 = db.Column(db.Float, nullable=True)
    hour_8 = db.Column(db.Float, nullable=True)
    hour_9 = db.Column(db.Float, nullable=True)
    hour_10 = db.Column(db.Float, nullable=True)
    hour_11 = db.Column(db.Float, nullable=True)
    hour_12 = db.Column(db.Float, nullable=True)
    update_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'forecasted': self.forecasted,
            'hour_0': self.hour_0,
            'hour_1': self.hour_1,
            'hour_2': self.hour_2,
            'hour_3': self.hour_3,
            'hour_4': self.hour_4,
            'hour_5': self.hour_5,
            'hour_6': self.hour_6,
            'hour_7': self.hour_7,
            'hour_8': self.hour_8,
            'hour_9': self.hour_9,
            'hour_10': self.hour_10,
            'hour_11': self.hour_11,
            'hour_12': self.hour_12,
            'update_id': self.update_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class SystemDirection(db.Model):
    __tablename__ = 'epias_yal'
    __table_args__ = {'schema': 'epias'}
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, index=True)
    net = db.Column(db.Float, nullable=True)  # This is the system direction value
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'net': self.net,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        } 