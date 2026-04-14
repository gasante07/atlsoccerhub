"""Security utilities"""
import time
import threading
from collections import defaultdict
from typing import Optional

# Simple in-memory rate limiting (use Redis in production for multi-instance deployments)
_rate_limit_store = defaultdict(list)
_rate_limit_lock = threading.Lock()
_last_cleanup = time.time()
CLEANUP_INTERVAL = 300  # Clean up every 5 minutes

def _cleanup_old_entries():
    """Remove old entries from rate limit store to prevent memory leaks"""
    global _last_cleanup
    now = time.time()
    
    # Only cleanup if enough time has passed
    if now - _last_cleanup < CLEANUP_INTERVAL:
        return
    
    with _rate_limit_lock:
        # Remove IPs with no recent activity (older than 1 hour)
        cutoff_time = now - 3600
        ips_to_remove = []
        
        for ip, requests in _rate_limit_store.items():
            # Remove old requests
            requests[:] = [req_time for req_time in requests if req_time > cutoff_time]
            
            # Mark IPs with no requests for removal
            if not requests:
                ips_to_remove.append(ip)
        
        # Remove empty IP entries
        for ip in ips_to_remove:
            del _rate_limit_store[ip]
        
        _last_cleanup = now

def check_rate_limit(ip: str, max_requests: int, window_seconds: int) -> bool:
    """
    Check if IP is within rate limit.
    
    Args:
        ip: Client IP address
        max_requests: Maximum number of requests allowed
        window_seconds: Time window in seconds
    
    Returns:
        True if within limit, False if rate limit exceeded
    """
    # Periodic cleanup to prevent memory leaks
    _cleanup_old_entries()
    
    now = time.time()
    
    with _rate_limit_lock:
        requests = _rate_limit_store[ip]
        
        # Remove old requests outside window
        requests[:] = [req_time for req_time in requests if now - req_time < window_seconds]
        
        if len(requests) >= max_requests:
            return False
        
        requests.append(now)
        return True

def validate_honeypot(honeypot_value: Optional[str]) -> bool:
    """Validate honeypot field (should be empty)"""
    return not honeypot_value or honeypot_value.strip() == ""

def sanitize_input(value: Optional[str]) -> str:
    """Basic input sanitization"""
    if not value:
        return ""
    return value.strip()[:500]  # Limit length

def validate_email(email: str) -> bool:
    """Basic email validation"""
    if not email:
        return False
    return "@" in email and "." in email.split("@")[1]

