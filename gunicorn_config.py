import os
import multiprocessing

# Set appropriate worker count - fewer workers = less memory used
workers = 2  # Reduce from default to save memory
threads = 2  # Fewer threads per worker

# Timeout settings
timeout = 120  # Increase timeout for ML operations
keepalive = 5

# Memory optimization settings
max_requests = 20
max_requests_jitter = 5

# Preload app (set to False to save memory during startup)
preload_app = False

# Logging
loglevel = 'info'
accesslog = '-'
errorlog = '-'

# Set environment variables for PyTorch to reduce memory usage
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['VECLIB_MAXIMUM_THREADS'] = '1'

# Force PyTorch to use CPU mode only
os.environ['CUDA_VISIBLE_DEVICES'] = ''

# Let Render assign the port
port = os.getenv('PORT', '8000')
bind = f"0.0.0.0:{port}"
worker_class = "gthread"  # Use gthread for better memory management
wsgi_app = "wsgi:app" 