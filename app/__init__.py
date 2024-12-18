import os
import pytz
import pyodbc
from flask import Flask, render_template, redirect, url_for
from flask_session import Session
import os
from dotenv import load_dotenv  # Updated import statement

load_dotenv()
# import flask_excel as excel

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024
# configure backend-session
app.config['SESSION_PERMANENT'] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['SESSION_FILE_DIR'] = os.path.join(app.root_path, '../flask_session')
# app.config['SESSION_FILE_DIR'] = '/home/ubuntu/inventory_app/flask_session'
# print(app.root_path)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['USERNAME'] = os.getenv('USERNAME')
app.config['PASSWORD'] = os.getenv('PASSWORD')
app.config['TIMEZONE'] = pytz.timezone('Etc/GMT-3')

# API base electricity-service (Endpoints)
app.config['BASEURL_1'] = 'https://seffaflik.epias.com.tr/electricity-service/'
app.config['ORGANIZATION_LIST'] = 'v1/generation/data/organization-list'
app.config['UEVCB_ENDPOINT'] = 'v1/generation/data/uevcb-list'
app.config['DPP_ENDPOINT'] = 'v1/generation/data/dpp'

app.config['ORGANIZATION_LIST_URL'] = app.config['BASEURL_1'] + app.config['ORGANIZATION_LIST']
app.config['UEVCB_URL'] = app.config['BASEURL_1'] + app.config['UEVCB_ENDPOINT']
app.config['DPP_URL'] = app.config['BASEURL_1'] + app.config['DPP_ENDPOINT']


# setup backend-session
flaskSession = Session(app)

# register blueprints
from .main import main
main = app.register_blueprint(main)

# error handlers (form app)
@app.errorhandler(404)
def handle_not_found(e):
    return render_template('errors/error_404.html'), 404

@app.errorhandler(400)
def handle_not_found(e):
    return render_template('errors/error_400.html'), 400

@app.errorhandler(405)
def handle_method_not_allowed(e):
    return render_template('errors/error_405.html'), 405
 
@app.errorhandler(500)
def handle_internal_server_error(e):
    return render_template('errors/error_500.html'), 500

