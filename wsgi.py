# Import this early to set environment variables before any ML imports
from app.utils.ml_config import log_memory_usage, cleanup_memory

# Log initial memory usage
print("Initial memory usage before app creation:")
log_memory_usage()

# Import and create the app with ML preloading disabled
from app import create_app
app = create_app(skip_ml_preload=True)

# Log memory after app creation
print("Memory usage after app creation:")
log_memory_usage()

if __name__ == "__main__":
    app.run() 