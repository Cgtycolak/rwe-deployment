import os
import sys
import argparse
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_demand_table_sql(db_url):
    """Create the demand_data table using direct SQL"""
    print(f"Connecting to database...")
    
    # Create engine
    engine = create_engine(db_url)
    conn = engine.connect()
    
    try:
        # Check if table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'demand_data'
            )
        """)).scalar()
        
        if result:
            print("demand_data table already exists, dropping it...")
            conn.execute(text("DROP TABLE IF EXISTS demand_data CASCADE"))
            conn.commit()
            print("Table dropped successfully")
        
        # Create the table
        print("Creating demand_data table...")
        conn.execute(text("""
        CREATE TABLE demand_data (
            id SERIAL PRIMARY KEY,
            datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            consumption FLOAT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT demand_data_datetime_key UNIQUE (datetime)
        )
        """))
        conn.commit()
        print("Table created successfully!")
        
        # Verify table was created
        tables = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")).fetchall()
        print("\nTables in database:", [t[0] for t in tables])
        
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create demand_data table using direct SQL')
    parser.add_argument('--db-url', help='Database URL to connect to')
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
    else:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            print("Error: DATABASE_URL environment variable not set")
            sys.exit(1)
    
    create_demand_table_sql(db_url) 