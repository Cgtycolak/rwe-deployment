import os
import sys
from app import create_app

# Initialize Flask app
app = create_app()

# Keep the app context alive
app.app_context().push()