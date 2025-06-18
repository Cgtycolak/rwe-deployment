import os
import sys
import tempfile
import argparse
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import csv
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

# Load environment variables
load_dotenv()

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(parent_dir)

def bulk_copy_demand_data(source_url, target_url):
    """Copy demand data from source to target database using bulk operations"""
    print(f"Connecting to source database...")
    
    # Create source engine
    source_engine = create_engine(source_url)
    source_conn = source_engine.connect()
    
    try:
        # Get all records from source database
        print("Fetching records from source database...")
        source_records = source_conn.execute(text(
            "SELECT datetime, consumption, created_at FROM demand_data ORDER BY datetime"
        )).fetchall()
        
        print(f"Found {len(source_records)} records in source database")
        
        if not source_records:
            print("No records to copy.")
            return
        
        # Connect to target database using psycopg2 for faster operations
        print("Connecting to target database...")
        target_conn = psycopg2.connect(target_url)
        target_cursor = target_conn.cursor()
        
        # First, ensure the table exists and is empty
        print("Preparing target table...")
        target_cursor.execute("DROP TABLE IF EXISTS demand_data CASCADE")
        target_conn.commit()
        
        target_cursor.execute("""
        CREATE TABLE demand_data (
            id SERIAL PRIMARY KEY,
            datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            consumption FLOAT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT demand_data_datetime_key UNIQUE (datetime)
        )
        """)
        target_conn.commit()
        
        # Prepare data for bulk insert
        print("Preparing data for bulk insert...")
        records_to_insert = []
        for record in source_records:
            # Convert to the format expected by execute_values
            dt = record[0]
            consumption = record[1]
            created_at = record[2] if record[2] else datetime.now()
            records_to_insert.append((dt, consumption, created_at))
        
        # Bulk insert using execute_values
        print("Performing bulk insert...")
        execute_values(
            target_cursor,
            "INSERT INTO demand_data (datetime, consumption, created_at) VALUES %s",
            records_to_insert,
            template="(%s, %s, %s)",
            page_size=1000
        )
        target_conn.commit()
        
        # Verify record count
        target_cursor.execute("SELECT COUNT(*) FROM demand_data")
        target_count = target_cursor.fetchone()[0]
        
        print(f"Bulk copy complete. {target_count} records inserted into target database.")
        
        # Close connections
        target_cursor.close()
        target_conn.close()
        
    finally:
        source_conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Bulk copy demand data between databases')
    parser.add_argument('--source-url', help='Source database URL')
    parser.add_argument('--target-url', help='Target database URL')
    parser.add_argument('--production', action='store_true', help='Copy from local to production')
    
    args = parser.parse_args()
    
    source_url = args.source_url
    target_url = args.target_url
    
    if args.production:
        source_url = os.environ.get('DATABASE_URL')
        target_url = os.environ.get('PRODUCTION_DATABASE_URL')
        
        if not source_url:
            print("Error: DATABASE_URL environment variable not set")
            sys.exit(1)
        if not target_url:
            print("Error: PRODUCTION_DATABASE_URL environment variable not set")
            sys.exit(1)
    
    if not source_url or not target_url:
        print("Error: Both source and target database URLs are required")
        sys.exit(1)
    
    bulk_copy_demand_data(source_url, target_url) 