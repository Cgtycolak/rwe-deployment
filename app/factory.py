import os
import pytz
import logging
from flask import Flask, render_template
from flask_session import Session
from flask_cors import CORS
from dotenv import load_dotenv
from .database.config import init_db, db
from .routes.realtime_generation import realtime_generation_bp

def create_app():
    # Load environment variables
    load_dotenv()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    app = Flask(__name__, template_folder='templates', static_folder='static')
    
    # Enable CORS
    CORS(app)

    # Configure app
    app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024
    app.config['SESSION_PERMANENT'] = False
    app.config["SESSION_TYPE"] = "filesystem"
    app.config['SESSION_FILE_DIR'] = os.path.join(app.root_path, '../flask_session')

    # Security settings from environment variables
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['USERNAME'] = os.getenv('USERNAME')
    app.config['PASSWORD'] = os.getenv('PASSWORD')
    app.config['TIMEZONE'] = pytz.timezone('Etc/GMT-3')

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
    
    # Initialize database
    init_db(app)

    # Setup session
    Session(app)

    # Register blueprints
    from .main import main
    app.register_blueprint(main)
    app.register_blueprint(realtime_generation_bp)

    return app 