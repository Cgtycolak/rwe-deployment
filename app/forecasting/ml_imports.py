# Import at the top of the file to ensure PyTorch uses CPU-only mode
from app.utils.ml_config import log_memory_usage, cleanup_memory

def get_darts_models():
    """Import darts models only when needed"""
    log_memory_usage()  # Log memory before imports
    
    from darts.models import Prophet, CatBoostModel, LightGBMModel, LinearRegressionModel, XGBModel
    
    cleanup_memory()  # Clean up after imports
    return {
        "Prophet": Prophet,
        "CatBoost": CatBoostModel,
        "LightGBM": LightGBMModel, 
        "LinearRegression": LinearRegressionModel,
        "XGBoost": XGBModel
    } 