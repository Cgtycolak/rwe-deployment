import os
import sys
import argparse

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(parent_dir)

from app import create_app
from app.models.demand import DemandData
from app.database.config import db
from sqlalchemy import inspect

def create_demand_table(db_url=None):
    """Create the demand_data table directly using SQLAlchemy"""
    app = create_app()
    
    # Override database URL if provided
    if db_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url
        print(f"Using provided database URL")
    
    with app.app_context():
        # Print connection details (masked for security)
        db_url_display = app.config['SQLALCHEMY_DATABASE_URI']
        if '@' in db_url_display:
            # Mask the password in the URL for display
            parts = db_url_display.split('@')
            auth_parts = parts[0].split(':')
            masked_url = f"{auth_parts[0]}:****@{parts[1]}"
            print(f"Connecting to database: {masked_url}")
        else:
            print(f"Connecting to database: {db_url_display}")
        
        inspector = inspect(db.engine)
        
        # Print all existing tables
        print("\nExisting tables:", inspector.get_table_names())
        
        # Check if table exists
        if 'demand_data' not in inspector.get_table_names():
            print("\nCreating demand_data table...")
            DemandData.__table__.create(db.engine)
            print("Table created successfully!")
            
            # Verify table was created
            print("\nUpdated table list:", inspect(db.engine).get_table_names())
        else:
            print("\ndemand_data table already exists!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create demand_data table in the database')
    parser.add_argument('--db-url', help='Database URL to connect to (overrides config)')
    parser.add_argument('--production', action='store_true', help='Use PRODUCTION_DATABASE_URL from environment')
    
    args = parser.parse_args()
    
    db_url = None
    if args.production:
        db_url = os.environ.get('PRODUCTION_DATABASE_URL')
        if not db_url:
            print("Error: PRODUCTION_DATABASE_URL environment variable not set")
            sys.exit(1)
    elif args.db_url:
        db_url = args.db_url
    
    create_demand_table(db_url) 