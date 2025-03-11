from flask import Flask
from app import create_app
from app.database.config import db, migrate

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all() 