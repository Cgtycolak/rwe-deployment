import os
import gc
import resource

# Force CPU-only mode for PyTorch to reduce memory footprint
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:32"

def log_memory_usage():
    """Log current memory usage"""
    gc.collect()  # Force garbage collection
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(f"Memory usage: {usage / 1024:.2f} MB")
    return usage / 1024

def cleanup_memory():
    """Perform aggressive memory cleanup"""
    gc.collect()
    return True 