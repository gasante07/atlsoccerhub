"""
Configuration loader with support for:
- External JSON configuration files
- Environment-based configuration (dev/staging/prod)
- Environment variable overrides
- Generic sport-agnostic structure
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

from src.config.site_context import resolved_sport_config_path


def load_config_file(config_path: Path, default: Dict = None) -> Dict:
    """Load configuration from JSON file"""
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load config from {config_path}: {e}")
    return default or {}


def get_environment() -> str:
    """Get current environment from ENV variable, default to 'production'"""
    return os.getenv("ENV", "production").lower()


def load_config() -> Dict[str, Any]:
    """Load configuration with environment support"""
    env = get_environment()
    config_dir = Path("src/config")
    
    # Load base site config
    site_config = load_config_file(
        config_dir / "site.config.json",
        _get_default_site_config()
    )
    
    # Load environment-specific overrides if they exist
    env_config_path = config_dir / f"site.config.{env}.json"
    if env_config_path.exists():
        env_overrides = load_config_file(env_config_path, {})
        site_config = _deep_merge(site_config, env_overrides)
    
    sport_path = resolved_sport_config_path(config_dir)
    sport_config = load_config_file(sport_path, {})
    
    # Apply environment variable overrides
    site_config = _apply_env_overrides(site_config)

    result = {
        "site": site_config,
        "sport": sport_config,  # Generic name instead of uk_volleyball
        "environment": env
    }
    _validate_config(result)
    return result


def _validate_config(config: Dict[str, Any]) -> None:
    """Validate required config keys; raise ValueError with clear message if missing."""
    site = config.get("site") or {}
    sport = config.get("sport") or {}
    missing = []
    if not site.get("baseUrl"):
        missing.append("site.baseUrl")
    if not (site.get("brand") or {}).get("siteName"):
        missing.append("site.brand.siteName")
    if not sport.get("cities"):
        missing.append("sport.cities (sport config JSON)")
    if missing:
        raise ValueError(
            "Configuration validation failed. Missing or empty required keys: " + ", ".join(missing) + ". "
            "Ensure src/config/site.config.json exists and sport config (default src/config/sport.config.json "
            "or SPORT_CONFIG_FILE) is valid."
        )


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config: Dict) -> Dict:
    """Apply environment variable overrides to config"""
    if "BASE_URL" in os.environ:
        config["baseUrl"] = os.getenv("BASE_URL")
    
    # Override API keys from environment if provided (for security)
    # This allows keeping keys in .env instead of config files
    if "PEXELS_API_KEY" in os.environ:
        if "pexels" not in config:
            config["pexels"] = {
                "apiBaseUrl": "https://api.pexels.com",
                "searchQueries": {
                    "heroVideo": ["pickup soccer", "soccer game urban", "soccer field"],
                    "heroPoster": ["soccer field", "pickup soccer"],
                    "testimonials": ["soccer team", "soccer players"]
                }
            }
        config["pexels"]["apiKey"] = os.getenv("PEXELS_API_KEY")
    
    if "PIXABAY_API_KEY" in os.environ:
        if "pixabay" not in config:
            config["pixabay"] = {
                "apiBaseUrl": "https://pixabay.com/api",
                "rateLimit": {
                    "requests_per_minute": 100,
                    "requests_per_60_seconds": 100
                }
            }
        config["pixabay"]["apiKey"] = os.getenv("PIXABAY_API_KEY")

    if "UNSPLASH_API_KEY" in os.environ:
        if "unsplash" not in config:
            config["unsplash"] = {"apiBaseUrl": "https://api.unsplash.com"}
        config["unsplash"]["apiKey"] = os.getenv("UNSPLASH_API_KEY")

    return config


def _get_default_site_config() -> Dict:
    """Default site configuration (fallback if JSON not found)"""
    # Minimal fallback - actual config should be in JSON
    return {
        "hubMarketingName": "Metro Atlanta",
        "brand": {
            "siteName": "Atlanta Soccer Hub",
            "poweredBy": "GameOn Active",
            "tagline": "Find pickup soccer, organize games, and connect with players across Metro Atlanta",
            "valueProposition": "The home of pickup soccer in Metro Atlanta. Whether you're after a quick run, looking to join a regular game, or want to organize your own matches - we've got you covered."
        },
        "baseUrl": os.getenv("BASE_URL", "https://atlsoccerhub.com"),
        "paths": {
            "basePath": "/",
            "assetPrefix": "/"
        },
        "meta": {
            "defaultTitle": "Atlanta Soccer Hub | Pickup Soccer in Metro Atlanta",
            "defaultDescription": "Join Atlanta Soccer Hub to find and organize pickup soccer games across Metro Atlanta.",
            "defaultImage": "/assets/images/og-default.jpg",
            "twitterHandle": "@atlsoccerhub"
        },
        "pexels": {
            "apiKey": os.getenv("PEXELS_API_KEY", ""),
            "apiBaseUrl": "https://api.pexels.com",
            "searchQueries": {
                "heroVideo": ["pickup soccer", "soccer game urban", "soccer field"],
                "heroPoster": ["soccer field", "pickup soccer"],
                "testimonials": ["soccer team", "soccer players"]
            }
        },
        "media": {
            "searchQueries": {
                "heroVideo": ["pickup soccer", "soccer game", "football match", "soccer field", "soccer training"],
                "heroPoster": ["soccer field", "pickup soccer", "soccer players", "football game"],
                "cityFallback": ["soccer city", "football stadium", "soccer field"],
                "testimonials": ["soccer team", "soccer players", "sports community"]
            },
            "imageProviderOrder": ["pexels", "pixabay", "unsplash"]
        },
        "localAssets": {
            "imagesDir": "public/assets/images",
            "imagesWebPath": "assets/images",
            "namePatterns": ["football", "soccer"],
            "excludePatterns": ["logo", "football_hub", "volleyball"],
            "extensions": [".jpg", ".jpeg", ".png", ".webp"],
            "blogFallbackUrls": [],
            "aboutFallbackUrl": "",
            "cityFallbackImage": "football_hub_logo_2.png"
        },
        "unsplash": {
            "apiKey": os.getenv("UNSPLASH_API_KEY", ""),
            "apiBaseUrl": "https://api.unsplash.com"
        },
        "messaging": {
            "cta": {
                "hub": "Get Involved",
                "city": "Find Games Near Me",
                "area": "Find Games Near Me"
            },
            "hero": {},
            "sections": {
                "areaLinksTitle": "Find Soccer Across {city_name}"
            },
            "faq": {
                "hubCount": 12,
                "cityCount": None,
                "areaCount": None
            },
            "cityLinks": {
                "placement": "after_faqs"
            }
        }
    }
