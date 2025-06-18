import os
import pytz
import logging
from flask import Flask, render_template
from flask_session import Session
from flask_cors import CORS
from dotenv import load_dotenv
from .database.config import init_db, db
from .routes.realtime_generation import realtime_generation_bp
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from .factory import create_app


def register_error_handlers(app):
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

# Create the application instance
app = create_app()

# Initialize scheduler after app creation
from .tasks.scheduler import init_scheduler
init_scheduler(app)

# Register error handlers
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

