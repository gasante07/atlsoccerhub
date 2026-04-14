"""Configuration management"""
import json
import os
from pathlib import Path


def _load_site_display_name() -> str:
    """Brand name from src/config/site.config.json (for API strings and admin UI)."""
    try:
        root = Path(__file__).resolve().parent.parent.parent
        site_path = root / "src" / "config" / "site.config.json"
        with open(site_path, encoding="utf-8") as f:
            data = json.load(f)
        return (data.get("brand") or {}).get("siteName") or "Atlanta Soccer Hub"
    except Exception:
        return "Atlanta Soccer Hub"


SITE_DISPLAY_NAME = _load_site_display_name()

# Try to load from config.py, fallback to defaults
try:
    from config import (
        DATABASE_PATH,
        ADMIN_PASSWORD_HASH,
        RATE_LIMIT_PER_HOUR,
        RATE_LIMIT_PER_DAY,
        SECRET_KEY,
        ALLOWED_ORIGINS
    )
except ImportError:
    # Defaults for development
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), "..", "leads.db")
    ADMIN_PASSWORD_HASH = None  # Must be set in config.py or ADMIN_PASSWORD_HASH env
    RATE_LIMIT_PER_HOUR = 5
    RATE_LIMIT_PER_DAY = 20
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    # CORS: Use environment variable for production, allow all in development
    # In production, set ALLOWED_ORIGINS env var to your domain, e.g., "https://atlsoccerhub.com"
    allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
    if allowed_origins_env:
        # Split comma-separated list if multiple origins provided
        ALLOWED_ORIGINS = [origin.strip() for origin in allowed_origins_env.split(",")]
    else:
        # Development default - allow all (NOT for production!)
        ALLOWED_ORIGINS = ["*"]

# Allow ADMIN_PASSWORD_HASH from environment (e.g. Replit Secrets) when not in config
if ADMIN_PASSWORD_HASH is None and os.environ.get("ADMIN_PASSWORD_HASH"):
    ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH").strip() or None

# Database: PostgreSQL when set (e.g. Replit), else SQLite via DATABASE_PATH
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip() or None

# Leads proxy: GAS web app URL (server forwards to avoid CORS)
LEADS_WEB_APP_URL = (os.environ.get("LEADS_WEB_APP_URL") or "").strip() or None

# Production: require explicit CORS origins (do not allow "*")
if os.getenv("ENV", "production").lower() == "production":
    if ALLOWED_ORIGINS == ["*"] or (len(ALLOWED_ORIGINS) == 1 and ALLOWED_ORIGINS[0] == "*"):
        raise ValueError(
            "CRITICAL: ALLOWED_ORIGINS must be set to your production domain(s) in production. "
            "Set ALLOWED_ORIGINS in Replit Secrets, e.g. https://your-repl.your-username.repl.co"
        )

