import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

db = SQLAlchemy()
migrate = Migrate()

def init_db(app):
    """Initialize database and migrations"""
    # Initialize SQLAlchemy with app
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Import all models here so they're registered with SQLAlchemy
    from ..models.heatmap import HydroHeatmapData, NaturalGasHeatmapData, ImportedCoalHeatmapData
    from ..models.realtime import HydroRealtimeData, NaturalGasRealtimeData
    from ..models.production import ProductionData
    from ..models.demand import DemandData
    from ..models.forecasting import UnlicensedSolar, LicensedSolar, Wind, DamHydro, RunOfRiverHydro, Demand, SystemDirection
    
    # Create all tables
    with app.app_context():
        try:
            # This will create tables that don't exist, but won't update existing tables
            db.create_all()
            logging.info("Database tables created successfully")
        except Exception as e:
            logging.error(f"Error creating database tables: {e}")
            # Continue even if there's an error, as migrations will handle it
            pass