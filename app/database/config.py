import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

db = SQLAlchemy()
migrate = Migrate()

def init_db(app):
    """Initialize database and migrations"""
    db.init_app(app)
    migrate.init_app(app, db)