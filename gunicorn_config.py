import os

# Let Render assign the port
port = os.getenv('PORT', '8000')
bind = f"0.0.0.0:{port}"

# 2 workers × 4 threads = 8 concurrent request slots.
# gthread avoids forking the heavy ML process memory on each worker start.
workers = 2
threads = 4
worker_class = "gthread"
timeout = 180
