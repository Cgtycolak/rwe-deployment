import os
import gc
import psutil
import torch

# Set environment variables for PyTorch to reduce memory usage
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['VECLIB_MAXIMUM_THREADS'] = '1'

# Force PyTorch to use CPU mode only
os.environ['CUDA_VISIBLE_DEVICES'] = ''

# Set PyTorch to use the smallest precision possible
torch.set_default_dtype(torch.float32)

# Limit PyTorch threads
torch.set_num_threads(1)

# Disable gradient calculation for inference
torch.set_grad_enabled(False)

def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / 1024 / 1024
    return memory_mb

def log_memory_usage():
    """Log current memory usage"""
    memory_mb = get_memory_usage()
    print(f"Memory usage: {memory_mb:.2f} MB")
    return memory_mb

def cleanup_memory():
    """Aggressive memory cleanup for ML operations"""
    # Run garbage collection multiple times
    for _ in range(3):
        gc.collect()
    
    # Clear PyTorch cache if available
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    # Also clear CPU cache in PyTorch
    if hasattr(torch, 'empty_cache'):
        torch.empty_cache()
    
    # Log memory after cleanup
    log_memory_usage()

def log_memory_with_label(label):
    """Log memory usage with a specific label"""
    memory_mb = get_memory_usage()
    print(f"Memory usage ({label}): {memory_mb:.2f} MB")
    return memory_mb 