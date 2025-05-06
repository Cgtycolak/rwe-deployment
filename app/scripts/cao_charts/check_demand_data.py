import os
import sys
from datetime import datetime, timedelta
import json
from sqlalchemy import text

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(parent_dir)

from app import create_app
from app.database.config import db
from app.models.demand import DemandData

def check_demand_data():
    """Check demand data for completeness and recent updates"""
    
    # Create app context
    app = create_app()
    
    with app.app_context():
        # Get min and max dates
        min_date = db.session.query(db.func.min(DemandData.datetime)).scalar()
        max_date = db.session.query(db.func.max(DemandData.datetime)).scalar()
        
        if not min_date or not max_date:
            print("No demand data found in database")
            return
        
        # Get current time
        now = datetime.now()
        
        # Calculate how many hours behind we are
        hours_behind = int((now - max_date).total_seconds() / 3600)
        
        print(f"Demand data summary:")
        print(f"  First record: {min_date.strftime('%Y-%m-%d %H:%M')}")
        print(f"  Latest record: {max_date.strftime('%Y-%m-%d %H:%M')}")
        print(f"  Current time: {now.strftime('%Y-%m-%d %H:%M')}")
        print(f"  Hours behind current time: {hours_behind}")
        
        # Find gaps in data using SQLAlchemy's text()
        query = text("""
            WITH dates AS (
                SELECT generate_series(
                    date_trunc('hour', min(datetime)),
                    date_trunc('hour', max(datetime)),
                    '1 hour'::interval
                ) as expected_datetime
                FROM demand_data
            )
            SELECT expected_datetime::timestamp
            FROM dates
            LEFT JOIN demand_data ON dates.expected_datetime = date_trunc('hour', demand_data.datetime)
            WHERE demand_data.id IS NULL
            ORDER BY expected_datetime;
        """)
        
        missing_dates = db.session.execute(query).fetchall()
        
        if missing_dates:
            print(f"\nFound {len(missing_dates)} missing hours in the date range")
            print("First 10 missing hours:")
            for i, date in enumerate(missing_dates[:10]):
                print(f"  {date[0].strftime('%Y-%m-%d %H:%M')}")
        else:
            print("\nNo missing hours found in the existing date range")
        
        # Check if we need to update to current time
        if hours_behind > 0:
            print(f"\nNeed to fetch {hours_behind} hours of new data to catch up to current time")
            print(f"Run the update_demand_data_api endpoint to fetch the latest data")

if __name__ == "__main__":
    check_demand_data() 