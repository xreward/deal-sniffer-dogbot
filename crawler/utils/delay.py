#!/usr/bin/env python
import time
import random
import logging

logger = logging.getLogger(__name__)

def delay(milliseconds):
    """
    Delay execution for a fixed number of milliseconds
    
    Args:
        milliseconds: Time to delay in milliseconds
    """
    seconds = milliseconds / 1000.0
    logger.info(f"Delaying for {milliseconds}ms ({seconds:.2f}s)")
    time.sleep(seconds)

def random_delay(min_ms, max_ms):
    """
    Delay execution for a random number of milliseconds within range
    
    Args:
        min_ms: Minimum milliseconds to delay
        max_ms: Maximum milliseconds to delay
        
    Returns:
        The actual delay time in milliseconds
    """
    min_seconds = min_ms / 1000.0
    max_seconds = max_ms / 1000.0
    
    # Calculate random delay in seconds
    seconds = random.uniform(min_seconds, max_seconds)
    
    logger.info(f"Random delay for {seconds*1000:.0f}ms ({seconds:.2f}s)")
    time.sleep(seconds)
    
    return seconds * 1000

def human_like_delay():
    """
    Simulate a human-like delay between actions (500-2000ms)
    """
    return random_delay(500, 2000)
