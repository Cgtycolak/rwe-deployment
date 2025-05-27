def get_model(model_name):
    """Return a single initialized forecasting model."""
    # Only import when the function is called
    from app.forecasting.ml_imports import get_darts_models
    
    models = get_darts_models()
    
    model_configs = {
        "Prophet": lambda: models["Prophet"](daily_seasonality=True, weekly_seasonality=True),
        "LinearRegression": lambda: models["LinearRegression"](lags_future_covariates=[0], likelihood='quantile', quantiles=[0.05,0.5,0.95]),
        "XGBoost": lambda: models["XGBoost"](lags_future_covariates=[0], likelihood='quantile', quantiles=[0.05,0.5,0.95]),
        "LightGBM": lambda: models["LightGBM"](lags_future_covariates=[0], likelihood='quantile', quantiles=[0.05,0.5,0.95]),
        "CatBoost": lambda: models["CatBoost"](lags_future_covariates=[0], likelihood='quantile', quantiles=[0.05,0.5,0.95])
    }
    
    if model_name not in model_configs:
        raise ValueError(f"Model {model_name} not supported")
        
    # Return only the requested model
    return model_configs[model_name]() 