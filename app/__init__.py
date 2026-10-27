import os
import pytz
import logging
from flask import Flask, render_template
from flask_session import Session
from dotenv import load_dotenv
from .database.config import init_db, db
from .routes.realtime_generation import realtime_generation_bp
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from .factory import create_app


# Create the application instance
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0')

