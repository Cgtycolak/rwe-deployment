import os
import sys
from app.factory import create_app

# Initialize Flask app
app = create_app()

# Keep the app context alive
app.app_context().push()