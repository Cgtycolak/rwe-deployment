from app import create_app
from app.models.production import ProductionData
from app.database.config import db
from sqlalchemy import inspect

def create_production_table():
    """Create the production_data table directly using SQLAlchemy"""
    app = create_app()
    
    with app.app_context():
        # Print connection details
        print(f"Connecting to database: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        inspector = inspect(db.engine)
        
        # Print all existing tables
        print("\nExisting tables:", inspector.get_table_names())
        
        # Check if table exists
        if 'production_data' not in inspector.get_table_names():
            print("\nCreating production_data table...")
            ProductionData.__table__.create(db.engine)
            print("Table created successfully!")
            
            # Verify table was created
            print("\nUpdated table list:", inspect(db.engine).get_table_names())
        else:
            print("\nproduction_data table already exists!")

if __name__ == "__main__":
    create_production_table() 