def get_models():
    """Return a dictionary of initialized forecasting models."""
    # Only import when the function is actually called
    from app.forecasting.ml_imports import get_darts_models
    
    models = get_darts_models()
    
    return {
        "Prophet": models["Prophet"](daily_seasonality=True, weekly_seasonality=True),
        "LinearRegression": models["LinearRegression"](lags_future_covariates=[0], likelihood='quantile', quantiles=[0.05,0.5,0.95]),
        "XGBoost": models["XGBoost"](lags_future_covariates=[0], likelihood='quantile', quantiles=[0.05,0.5,0.95]),
        "LightGBM": models["LightGBM"](lags_future_covariates=[0], likelihood='quantile', quantiles=[0.05,0.5,0.95]),
        "CatBoost": models["CatBoost"](lags_future_covariates=[0], likelihood='quantile', quantiles=[0.05,0.5,0.95])
    } 