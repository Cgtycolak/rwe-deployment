# Import at the top of the file to ensure PyTorch uses CPU-only mode
from app.utils.ml_config import log_memory_usage, cleanup_memory

# Add cache for models to avoid reloading
_model_cache = {}

def get_darts_models():
    """Import darts models only when needed with caching"""
    # Return cached models if available
    if _model_cache:
        return _model_cache
        
    log_memory_usage()  # Log memory before imports
    
    # Import models inside function to avoid loading at startup
    from darts.models import Prophet, CatBoostModel, LightGBMModel, LinearRegressionModel, XGBModel
    
    # Cache the models
    _model_cache.update({
        "Prophet": Prophet,
        "CatBoost": CatBoostModel,
        "LightGBM": LightGBMModel, 
        "LinearRegression": LinearRegressionModel,
        "XGBoost": XGBModel
    })
    
    cleanup_memory()  # Clean up after imports
    return _model_cache 