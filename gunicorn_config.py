import os

# Let Render assign the port
port = os.getenv('PORT', '8000')
bind = f"0.0.0.0:{port}"

# gthread: 1 process × 8 threads — avoids duplicating heavy ML libraries (Darts etc.)
# across multiple worker processes on the 2GB Render Standard plan.
workers = 2
threads = 4
worker_class = "gthread"
timeout = 180
wsgi_app = "wsgi:app"