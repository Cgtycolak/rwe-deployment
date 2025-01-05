from app import create_app
from flask_cors import CORS
import os

app = create_app()

# Enable CORS
CORS(app)

#production
if __name__ == '__main__':
    app.jinja_env.auto_reload = True
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
