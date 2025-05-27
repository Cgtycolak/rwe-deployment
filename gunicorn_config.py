import os

# Let Render assign the port
port = os.getenv('PORT', '8000')
bind = f"0.0.0.0:{port}"
workers = 2  # Reduce from 4 to 2 to save memory
threads = 2
timeout = 120
worker_class = "gthread"  # Use gthread for better memory management
wsgi_app = "wsgi:app"

# Memory optimization settings
max_requests = 50  # Force worker restart after 50 requests
max_requests_jitter = 10  # Add randomness to prevent all workers restarting simultaneously
preload_app = False  # Don't preload the application 