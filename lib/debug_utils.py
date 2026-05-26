# lib/debug_utils.py
import logging
import functools
import time
from datetime import datetime
import json

# Configure debug logging
DEBUG_MODE = False  # Set to False to disable debug output

class DebugLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)
        
        # Console handler
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s - %(message)s',
                datefmt='%H:%M:%S'
            ))
            self.logger.addHandler(handler)
    
    def debug(self, msg, *args, **kwargs):
        if DEBUG_MODE:
            self.logger.debug(msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

def trace_chain(func):
    """Decorator to trace chain-related function calls"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = DebugLogger(func.__module__)
        
        # Log entry
        call_info = f"{func.__name__}("
        if args:
            call_info += f"args={args[:2]}..." if len(args) > 2 else f"args={args}"
        if kwargs:
            call_info += f", kwargs={kwargs}"
        call_info += ")"
        
        logger.debug(f"→ ENTER {call_info}")
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            elapsed = (time.time() - start_time) * 1000
            logger.debug(f"← EXIT {func.__name__} -> {type(result).__name__} in {elapsed:.2f}ms")
            
            # For database results, log summary
            if isinstance(result, list):
                logger.debug(f"  Result length: {len(result)}")
                if result and len(result) <= 3:
                    for i, item in enumerate(result):
                        logger.debug(f"  [{i}]: {str(item)[:100]}")
            elif isinstance(result, dict):
                logger.debug(f"  Result keys: {list(result.keys())}")
            
            return result
        except Exception as e:
            logger.error(f"✗ EXCEPTION in {func.__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    return wrapper