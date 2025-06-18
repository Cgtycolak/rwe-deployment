import os
import sys

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from app.tasks.scheduler import init_scheduler

if __name__ == "__main__":
    init_scheduler()