import os

# Let Render assign the port
port = os.getenv('PORT', '8000')
bind = f"0.0.0.0:{port}"
workers = 4
threads = 2
timeout = 120
worker_class = "aiohttp.worker.GunicornWebWorker"
wsgi_app = "wsgi:app" 