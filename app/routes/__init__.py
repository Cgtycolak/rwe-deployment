"""One blueprint per dashboard area. URL paths are flat (no prefix) except forecasting,
because the frontend calls them by path."""
from .cao_charts import cao_charts_bp
from .forecast_performance import forecast_performance_bp
from .forecasting import forecasting_bp
from .heatmaps import heatmaps_bp
from .hydro_map import hydro_map_bp
from .market import market_bp
from .merit_order import merit_order_bp
from .pages import pages_bp
from .plan_vs_realtime import plan_vs_realtime_bp
from .realtime_generation import realtime_generation_bp

BLUEPRINTS = (
    pages_bp,
    plan_vs_realtime_bp,
    realtime_generation_bp,
    heatmaps_bp,
    cao_charts_bp,
    market_bp,
    merit_order_bp,
    hydro_map_bp,
    forecast_performance_bp,
    forecasting_bp,
)


def register_blueprints(app):
    for bp in BLUEPRINTS:
        app.register_blueprint(bp)
