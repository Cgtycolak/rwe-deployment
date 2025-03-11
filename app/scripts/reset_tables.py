import os
import sys

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(parent_dir)

from app import create_app
from app.database.config import db
from app.models.heatmap import HydroHeatmapData, NaturalGasHeatmapData, ImportedCoalHeatmapData
from app.models.realtime import HydroRealtimeData, NaturalGasRealtimeData

def reset_tables():
    """Reset all heatmap and realtime tables"""
    app = create_app()
    
    with app.app_context():
        try:
            # Delete all data from tables
            print("Deleting data from HydroHeatmapData...")
            HydroHeatmapData.query.delete()
            
            print("Deleting data from NaturalGasHeatmapData...")
            NaturalGasHeatmapData.query.delete()
            
            print("Deleting data from ImportedCoalHeatmapData...")
            ImportedCoalHeatmapData.query.delete()
            
            print("Deleting data from HydroRealtimeData...")
            HydroRealtimeData.query.delete()
            
            print("Deleting data from NaturalGasRealtimeData...")
            NaturalGasRealtimeData.query.delete()
            
            # Commit the changes
            db.session.commit()
            print("All tables have been reset successfully!")
            
        except Exception as e:
            print(f"Error resetting tables: {str(e)}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    reset_tables() 