from ..database.config import db
from datetime import datetime

class ProductionData(db.Model):
    __tablename__ = 'production_data'
    
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False)
    fueloil = db.Column(db.Float)
    gasoil = db.Column(db.Float)
    blackcoal = db.Column(db.Float)
    lignite = db.Column(db.Float)
    geothermal = db.Column(db.Float)
    naturalgas = db.Column(db.Float)
    river = db.Column(db.Float)
    dammedhydro = db.Column(db.Float)
    lng = db.Column(db.Float)
    biomass = db.Column(db.Float)
    naphta = db.Column(db.Float)
    importcoal = db.Column(db.Float)
    asphaltitecoal = db.Column(db.Float)
    wind = db.Column(db.Float)
    nuclear = db.Column(db.Float)
    sun = db.Column(db.Float)
    importexport = db.Column(db.Float)
    total = db.Column(db.Float)
    wasteheat = db.Column(db.Float)
    
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            'datetime': self.datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'FuelOil': self.fueloil,
            'GasOil': self.gasoil,
            'BlackCoal': self.blackcoal,
            'Lignite': self.lignite,
            'Geothermal': self.geothermal,
            'NaturalGas': self.naturalgas,
            'Run-of-River': self.river,
            'Dam': self.dammedhydro,
            'LNG': self.lng,
            'Biomass': self.biomass,
            'Naphta': self.naphta,
            'HardCoal': self.importcoal,
            'Asphaltite': self.asphaltitecoal,
            'Wind': self.wind,
            'Nuclear': self.nuclear,
            'Solar': self.sun,
            'ImportExport': self.importexport,
            'Total': self.total,
            'WasteHeat': self.wasteheat
        } 