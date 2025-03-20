import os

# Let Render assign the port
port = os.getenv('PORT', '8000')
bind = f"0.0.0.0:{port}"
workers = 2
threads = 2
timeout = 120
worker_class = "gthread"
wsgi_app = "wsgi:app"
max_requests = 1000
max_requests_jitter = 200