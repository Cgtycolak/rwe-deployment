"""Turn stored heatmap rows into an hour x plant table. Used by the heatmap routes and the daily email."""
import pandas as pd


def process_heatmap_data(heatmap_data, mapping):
    """Process heatmap data from database into a pandas DataFrame."""
    hours = [f"{str(i).zfill(2)}:00" for i in range(24)]
    df = pd.DataFrame(index=hours, columns=mapping['plant_names'])

    for record in heatmap_data:
        hour = f"{str(record.hour).zfill(2)}:00"
        df.at[hour, record.plant_name] = record.value

    # Fix the pandas warning by explicitly converting to numeric
    return df.fillna(0).astype(float)
