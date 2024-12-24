import os
import pytz
from flask import Flask, render_template, redirect, url_for
from flask_session import Session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder='templates', static_folder='static')

# Configure app
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024
app.config['SESSION_PERMANENT'] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['SESSION_FILE_DIR'] = os.path.join(app.root_path, '../flask_session')

# Security settings
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-default-secret-key')
app.config['USERNAME'] = os.getenv('USERNAME')
app.config['PASSWORD'] = os.getenv('PASSWORD')
app.config['TIMEZONE'] = pytz.timezone('Etc/GMT-3')

# API endpoints
app.config['BASEURL_1'] = 'https://seffaflik.epias.com.tr/electricity-service/'
app.config['ORGANIZATION_LIST'] = 'v1/generation/data/organization-list'
app.config['UEVCB_ENDPOINT'] = 'v1/generation/data/uevcb-list'
app.config['DPP_ENDPOINT'] = 'v1/generation/data/dpp'
app.config['POWERPLANT_ENDPOINT'] = 'v1/generation/data/powerplant-list'
app.config['REALTIME_ENDPOINT'] = 'v1/generation/data/realtime-generation'
app.config['FUEL_TYPE_GENERATION_ENDPOINT'] = 'v1/generation/data/fueltype-generation'
app.config['AIC_ENDPOINT'] = 'v1/generation/data/aic'

app.config['ORGANIZATION_LIST_URL'] = app.config['BASEURL_1'] + app.config['ORGANIZATION_LIST']
app.config['UEVCB_URL'] = app.config['BASEURL_1'] + app.config['UEVCB_ENDPOINT']
app.config['DPP_URL'] = app.config['BASEURL_1'] + app.config['DPP_ENDPOINT']
app.config['POWERPLANT_URL'] = app.config['BASEURL_1'] + app.config['POWERPLANT_ENDPOINT']
app.config['REALTIME_URL'] = app.config['BASEURL_1'] + app.config['REALTIME_ENDPOINT']
app.config['FUEL_TYPE_GENERATION_URL'] = app.config['BASEURL_1'] + app.config['FUEL_TYPE_GENERATION_ENDPOINT']
app.config['AIC_URL'] = app.config['BASEURL_1'] + app.config['AIC_ENDPOINT']

# Setup session
flaskSession = Session(app)

# Register blueprints
from .main import main
app.register_blueprint(main)

# Error handlers
@app.errorhandler(404)
def handle_not_found(e):
    return render_template('errors/error_404.html'), 404

@app.errorhandler(400)
def handle_bad_request(e):
    return render_template('errors/error_400.html'), 400

@app.errorhandler(405)
def handle_method_not_allowed(e):
    return render_template('errors/error_405.html'), 405

@app.errorhandler(500)
def handle_internal_server_error(e):
    return render_template('errors/error_500.html'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0')

