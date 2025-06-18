from darts.models import Prophet, CatBoostModel, LightGBMModel, LinearRegressionModel, XGBModel

def get_models():
    """Return a dictionary of initialized forecasting models."""
    return {
        "Prophet": Prophet(daily_seasonality=True, weekly_seasonality=True),
        "LinearRegression": LinearRegressionModel(lags_future_covariates=[0], likelihood='quantile', quantiles=[0.05,0.5,0.95]),
        "XGBoost": XGBModel(lags_future_covariates=[0], likelihood='quantile', quantiles=[0.05,0.5,0.95]),
        "LightGBM": LightGBMModel(lags_future_covariates=[0], likelihood='quantile', quantiles=[0.05,0.5,0.95]),
        "CatBoost": CatBoostModel(lags_future_covariates=[0], likelihood='quantile', quantiles=[0.05,0.5,0.95])
    }