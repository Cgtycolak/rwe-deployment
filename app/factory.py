import os
import pytz
import logging
from datetime import timedelta
from flask import Flask, render_template
from flask_session import Session
from flask_cors import CORS
from dotenv import load_dotenv
from .database.config import init_db, db
from .routes.realtime_generation import realtime_generation_bp
from .routes.forecasting import forecasting_bp

def create_app():
    # Load environment variables
    load_dotenv()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    app = Flask(__name__, template_folder='templates', static_folder='static')
    
    # CORS — restrict to the deployed origin only; no cross-origin callers are legitimate
    allowed_origins = [o.strip() for o in os.getenv('ALLOWED_ORIGINS', '').split(',') if o.strip()]
    if allowed_origins:
        CORS(app, origins=allowed_origins, supports_credentials=True)
    # If ALLOWED_ORIGINS is not set (local dev), CORS is disabled entirely

    # Configure app
    app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # Session lasts 30 minutes
    app.config["SESSION_TYPE"] = "filesystem"
    app.config['SESSION_FILE_DIR'] = os.path.join(app.root_path, '../flask_session')

    # Security settings from environment variables
    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        raise RuntimeError("SECRET_KEY environment variable must be set")
    app.config['SECRET_KEY'] = secret_key
    app.config['USERNAME'] = os.getenv('USERNAME')
    app.config['PASSWORD'] = os.getenv('PASSWORD')
    app.config['TIMEZONE'] = pytz.timezone('Etc/GMT-3')

    # Dashboard authentication — no fallback; app must not start with missing credentials
    dashboard_username = os.getenv('DASHBOARD_USERNAME')
    dashboard_password = os.getenv('DASHBOARD_PASSWORD')
    if not dashboard_username or not dashboard_password:
        raise RuntimeError("DASHBOARD_USERNAME and DASHBOARD_PASSWORD environment variables must be set")
    app.config['DASHBOARD_USERNAME'] = dashboard_username
    app.config['DASHBOARD_PASSWORD'] = dashboard_password

    # Cookie security — Secure flag requires HTTPS; disable locally (Render sets RENDER env var)
    app.config['SESSION_COOKIE_SECURE'] = bool(os.getenv('RENDER'))
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'

    # API endpoints
    app.config['BASEURL_1'] = 'https://seffaflik.epias.com.tr/electricity-service/'
    app.config['ORGANIZATION_LIST'] = 'v1/generation/data/organization-list'
    app.config['UEVCB_ENDPOINT'] = 'v1/generation/data/uevcb-list'
    app.config['DPP_ENDPOINT'] = 'v1/generation/data/dpp'
    app.config['DPP_FIRST_VERSION_ENDPOINT'] = 'v1/generation/data/dpp-first-version'
    app.config['POWERPLANT_ENDPOINT'] = 'v1/generation/data/powerplant-list'
    app.config['REALTIME_ENDPOINT'] = 'v1/generation/data/realtime-generation'
    app.config['AIC_ENDPOINT'] = 'v1/generation/data/aic'

    # Set up full URLs directly
    app.config['ORGANIZATION_LIST_URL'] = app.config['BASEURL_1'] + app.config['ORGANIZATION_LIST']
    app.config['UEVCB_URL'] = app.config['BASEURL_1'] + app.config['UEVCB_ENDPOINT']
    app.config['DPP_URL'] = app.config['BASEURL_1'] + app.config['DPP_ENDPOINT']
    app.config['DPP_FIRST_VERSION_URL'] = app.config['BASEURL_1'] + app.config['DPP_FIRST_VERSION_ENDPOINT']
    app.config['POWERPLANT_URL'] = app.config['BASEURL_1'] + app.config['POWERPLANT_ENDPOINT']
    app.config['REALTIME_URL'] = app.config['BASEURL_1'] + app.config['REALTIME_ENDPOINT']
    app.config['AIC_URL'] = app.config['BASEURL_1'] + app.config['AIC_ENDPOINT']

    # Configure database
    if os.getenv('USE_LOCAL_DB', 'false').lower() == 'true':
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('LOCAL_DATABASE_URL')
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('PRODUCTION_DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'connect_args': {'connect_timeout': 10},
    }
    
    # Initialize database
    init_db(app)

    # Setup session
    Session(app)

    # Warn at startup for optional services whose absence causes silent failures later
    _optional_vars = {
        'SUPABASE_USER':      'Supabase analytics routes will return errors',
        'SUPABASE_PASSWORD':  'Supabase analytics routes will return errors',
        'XTRADERS_USERNAME':  'Meteologica solar data routes will return errors',
        'XTRADERS_PASSWORD':  'Meteologica solar data routes will return errors',
        'MODAL_CHRONOS_URL':  'Forecasting endpoint will raise on first call',
        'SENDER_EMAIL':       'Automated email reports will not send',
        'SENDER_PASSWORD':    'Automated email reports will not send',
        'RECIPIENT_EMAILS':   'Automated email reports will not send',
        'ALLOWED_ORIGINS':    'CORS is disabled (all cross-origin requests blocked)',
    }
    for _var, _consequence in _optional_vars.items():
        if not os.getenv(_var):
            app.logger.warning(f"Missing env var {_var!r}: {_consequence}")

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Permissions-Policy'] = 'geolocation=(), camera=(), microphone=()'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' "
                "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
                "https://code.jquery.com https://cdn.plot.ly https://cdn.sheetjs.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "img-src 'self' data:; "
            "connect-src 'self' https://cdn.jsdelivr.net; "
            "frame-src 'self' https://dbc-6991d07f-d61a.cloud.databricks.com; "
            "frame-ancestors 'self';"
        )
        return response

    # Register blueprints
    from .main import main
    app.register_blueprint(main)
    app.register_blueprint(realtime_generation_bp)
    app.register_blueprint(forecasting_bp)

    # Start background scheduler.
    # Dev (flask run with reloader): only start in the reloader child, not the parent watcher.
    # Production (gunicorn N workers): use a file lock so only the first worker starts it;
    # the others skip silently. The lock is held for the process lifetime so if that worker
    # dies and restarts, it re-acquires and starts again.
    _should_start = (not app.debug) or (os.environ.get('WERKZEUG_RUN_MAIN') == 'true')
    if _should_start:
        import fcntl as _fcntl
        _lock_path = os.path.join(app.root_path, '..', '.scheduler.lock')
        try:
            _lock_fd = open(_lock_path, 'w')
            _fcntl.flock(_lock_fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            app._scheduler_lock_fd = _lock_fd  # keep fd open so the lock persists
            from .tasks.scheduler import init_scheduler
            init_scheduler(app)
        except (IOError, OSError):
            app.logger.info("Scheduler already running in another worker — skipping start")

    return app