import io
import pandas as pd


def to_excel_bytes(df):
    """Convert a DataFrame to Excel bytes for download."""
    df_copy = df.copy()
    if 'date' in df_copy.columns and hasattr(df_copy['date'].dtype, 'tz'):
        df_copy['date'] = df_copy['date'].dt.tz_localize(None)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_copy.to_excel(writer, index=False, sheet_name='Veri')
    return output.getvalue()
