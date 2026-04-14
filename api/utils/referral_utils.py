"""
Referral code generation utilities
Centralized referral code generation logic
"""
import secrets
import string
from typing import Optional
from api.models.database import Database


def generate_referral_code(db: Database) -> str:
    """
    Generate a unique referral code in format REF-XXXX-XXXX.
    
    Args:
        db: Database instance for checking uniqueness
    
    Returns:
        Unique referral code string
    """
    max_attempts = 100  # Prevent infinite loops
    attempt = 0
    
    while attempt < max_attempts:
        # Generate 8 character alphanumeric code
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        formatted_code = f"REF-{code[:4]}-{code[4:]}"
        
        # Check if code exists
        existing = db.get_referral_code_by_code(formatted_code)
        if not existing:
            return formatted_code
        
        attempt += 1
    
    # Fallback: add timestamp to ensure uniqueness
    import time
    timestamp = str(int(time.time()))[-4:]
    code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"REF-{code}-{timestamp}"
