#!/usr/bin/env python3
"""
Static Site Generator for Atlanta Soccer Hub
Scalable and efficient Python version with parallel processing, error recovery, and caching

Media API Integration:
- Pexels: Primary source for images/videos
  - Rate Limits: 200 requests/hour, 20,000 requests/month
- Pixabay: Fallback source for images/videos
  - Rate Limits: 100 requests/60 seconds
- Rate limiting implemented via MAX_CONCURRENT_API_CALLS and API_REQUEST_DELAY
- 429 errors handled with exponential backoff (RETRY_DELAY_429 = 60s)
- All API calls respect rate limits and include proper error handling
- Caching minimizes redundant API calls
- Automatic fallback: Pexels → Pixabay → Generic images
"""

import os
import re
import json
import random
import shutil
import time
import html
import hashlib
import copy
from pathlib import Path
from urllib.parse import quote
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Any
import requests

# Configuration constants
# Adaptive parallelization based on CPU count
CPU_COUNT = os.cpu_count() or 4
CONFIG = {
    "ASSET_PREFIX": "/",
    "MAX_CONCURRENT_PAGES": min(CPU_COUNT, 10),  # Adaptive: use CPU count, cap at 10
    "MAX_CONCURRENT_API_CALLS": 2,  # API rate limiting: Pexels allows 200/hour = ~3.3/min, use 2 for safety
    "RETRY_ATTEMPTS": 3,
    "RETRY_DELAY": 1.0,  # seconds
    "RETRY_DELAY_429": 60.0,  # seconds - wait 1 minute for rate limit (429) errors
    "API_REQUEST_DELAY": 0.5,  # seconds - delay between API requests to respect rate limits
    "CACHE_FILE": ".generator-cache.json",
    "CACHE_MAX_AGE": 24 * 60 * 60,  # 24 hours in seconds
    "PEXELS_RATE_LIMIT": {
        "requests_per_hour": 200,
        "requests_per_month": 20000
    }
}

# Configuration loading - fully externalized
_loaded_config = None
try:
    from src.config.config_loader import load_config
    _loaded_config = load_config()
    print(f"Loaded configuration from external files (environment: {_loaded_config['environment']})")
except (ImportError, Exception) as e:
    print(f"ERROR: Configuration loader failed: {e}")
    raise

if not _loaded_config or not _loaded_config.get("site"):
    raise ValueError("Site configuration is required. Please create src/config/site.config.json")

SITE_CONFIG = _loaded_config["site"]
SPORT_CONFIG = _loaded_config.get("sport", {})

from src.config.site_context import hub_marketing_name, hub_keyword_seeds, resolved_sport_config_path

HUB_MARKETING = hub_marketing_name(SITE_CONFIG)

# Validate required config sections
if not SPORT_CONFIG.get("cities"):
    raise ValueError(
        "Sport configuration must include cities. Ensure src/config/sport.config.json exists "
        "or set SPORT_CONFIG_FILE to a valid sport JSON."
    )

# Get configurable paths
BASE_PATH = SITE_CONFIG.get("paths", {}).get("basePath", "/")
# Base path with one trailing slash for building links (avoids "//" when BASE_PATH is "/")
BASE_PATH_LINKS = "/" if (not BASE_PATH or BASE_PATH == "/" or not BASE_PATH.strip("/")) else (BASE_PATH.rstrip("/") + "/")
# Full root URL (no double slash when BASE_PATH is "/")
ROOT_URL = SITE_CONFIG["baseUrl"].rstrip("/") + BASE_PATH_LINKS
ASSET_PREFIX = SITE_CONFIG.get("paths", {}).get("assetPrefix", "/")

# Legacy fallback removed - config must be in JSON files
# All configuration now comes from JSON files via config_loader

# Media cache with persistence
media_cache = {
    "videos": {},  # Pexels videos
    "photos": {},  # Pexels photos
    "pixabay_videos": {},  # Pixabay videos (fallback)
    "pixabay_photos": {},  # Pixabay photos (fallback)
    "unsplash_photos": {},  # Unsplash photos (fallback)
    "lastUpdated": None
}

# Stats tracking
stats = {
    "pagesGenerated": 0,
    "pagesFailed": 0,
    "apiCalls": 0,
    "cacheHits": 0,
    "startTime": None
}

# Area page existence cache
area_page_cache = {}

# Local football images cache (for section image fallbacks)
_local_football_images_cache = None
# Local hero videos cache (for hero background video discovery)
_local_hero_videos_cache = None


class PexelsClient:
    """
    Pexels API client with rate limiting and proper error handling.
    
    Rate Limits (per Pexels API documentation):
    - 200 requests per hour
    - 20,000 requests per month
    
    Best Practices:
    - Respect rate limit headers if provided
    - Handle 429 errors with exponential backoff
    - Add delays between requests
    - Cache responses to minimize API calls
    """
    
    def __init__(self, api_key: str, api_base_url: str = "https://api.pexels.com"):
        self.api_key = api_key
        self.api_base_url = api_base_url
        self.session = requests.Session()
        # Pexels API requires Authorization header with API key
        self.session.headers.update({"Authorization": api_key})
        self.last_request_time = 0
        self.request_lock = None  # Will be set if threading is used
    
    def _rate_limit_delay(self):
        """Add delay between requests to respect rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_delay = CONFIG["API_REQUEST_DELAY"]
        
        if time_since_last < min_delay:
            sleep_time = min_delay - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _handle_rate_limit_error(self, response: requests.Response) -> Optional[Dict]:
        """
        Handle 429 Rate Limit errors according to Pexels API best practices.
        Returns None to indicate the request should be retried later.
        """
        if response.status_code == 429:
            # Check for Retry-After header (if provided by API)
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    wait_time = int(retry_after)
                    print(f"Rate limit hit. Waiting {wait_time} seconds (per Retry-After header)...")
                    time.sleep(wait_time)
                except ValueError:
                    # If Retry-After is invalid, use default delay
                    print(f"Rate limit hit. Waiting {CONFIG['RETRY_DELAY_429']} seconds...")
                    time.sleep(CONFIG["RETRY_DELAY_429"])
            else:
                # Default: wait 1 minute for rate limit reset
                print(f"Rate limit hit (429). Waiting {CONFIG['RETRY_DELAY_429']} seconds...")
                time.sleep(CONFIG["RETRY_DELAY_429"])
            return None
        return None
    
    def fetch_videos(self, query: str, per_page: int = 20) -> Optional[Dict]:
        """
        Fetch videos from Pexels API with rate limiting.
        
        Args:
            query: Search query string
            per_page: Number of results per page (max 80 per Pexels API)
        
        Returns:
            API response dict or None on error
        """
        # Enforce per_page limit (Pexels API max is 80)
        per_page = min(per_page, 80)
        
        # Rate limiting delay
        self._rate_limit_delay()
        
        try:
            url = f"{self.api_base_url}/videos/search"
            params = {"query": query, "per_page": per_page}
            response = self.session.get(url, params=params, timeout=10)
            
            # Handle rate limit errors specifically
            if response.status_code == 429:
                self._handle_rate_limit_error(response)
                return None
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Already handled above, but catch here for safety
                return None
            print(f"HTTP error fetching Pexels videos for '{query}': {e}")
            return None
        except Exception as e:
            print(f"Error fetching Pexels videos for '{query}': {e}")
            return None
    
    def fetch_photos(self, query: str, per_page: int = 20) -> Optional[Dict]:
        """
        Fetch photos from Pexels API with rate limiting.
        
        Args:
            query: Search query string
            per_page: Number of results per page (max 80 per Pexels API)
        
        Returns:
            API response dict or None on error
        """
        # Enforce per_page limit (Pexels API max is 80)
        per_page = min(per_page, 80)
        
        # Rate limiting delay
        self._rate_limit_delay()
        
        try:
            url = f"{self.api_base_url}/v1/search"
            params = {"query": query, "per_page": per_page}
            response = self.session.get(url, params=params, timeout=10)
            
            # Handle rate limit errors specifically
            if response.status_code == 429:
                self._handle_rate_limit_error(response)
                return None
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Already handled above, but catch here for safety
                return None
            print(f"HTTP error fetching Pexels photos for '{query}': {e}")
            return None
        except Exception as e:
            print(f"Error fetching Pexels photos for '{query}': {e}")
            return None
    
    def get_video_url(self, video: Dict, quality: str = "hd") -> Optional[str]:
        """Extract video URL from Pexels video object"""
        if not video or "video_files" not in video:
            return None
        
        video_files = video["video_files"]
        hd_file = next((f for f in video_files if f.get("quality") == "hd" and f.get("width", 0) >= 1920), None)
        sd_file = next((f for f in video_files if f.get("quality") == "sd"), None)
        
        if hd_file:
            return hd_file.get("link")
        elif sd_file:
            return sd_file.get("link")
        elif video_files:
            return video_files[0].get("link")
        return None
    
    def get_image_url(self, photo: Dict, size: str = "large") -> Optional[str]:
        """Extract image URL from Pexels photo object"""
        if not photo or "src" not in photo:
            return None
        
        sizes = {
            "original": photo["src"].get("original"),
            "large": photo["src"].get("large"),
            "medium": photo["src"].get("medium"),
            "small": photo["src"].get("small")
        }
        return sizes.get(size) or photo["src"].get("original")


class PixabayClient:
    """
    Pixabay API client with rate limiting and proper error handling.
    
    Per Pixabay API documentation (https://pixabay.com/api/docs/):
    - Rate Limits: 100 requests per 60 seconds
    - Caching: Requests must be cached for 24 hours (per API requirements)
    - Hotlinking: Permanent hotlinking not allowed - images must be downloaded
    
    Best Practices:
    - Respect rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
    - Handle 429 errors with exponential backoff
    - Add delays between requests (0.6s minimum for 100 req/60s)
    - Cache responses for 24 hours to minimize API calls
    - Download images to server (no permanent hotlinking)
    """
    
    def __init__(self, api_key: str, api_base_url: str = "https://pixabay.com/api"):
        self.api_key = api_key
        self.api_base_url = api_base_url
        self.session = requests.Session()
        self.last_request_time = 0
    
    def _rate_limit_delay(self):
        """Add delay between requests to respect rate limits (100 per 60 seconds)"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        # Pixabay allows 100 requests per 60 seconds = ~0.6 seconds between requests
        min_delay = 0.6
        
        if time_since_last < min_delay:
            sleep_time = min_delay - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _handle_rate_limit_error(self, response: requests.Response) -> Optional[Dict]:
        """
        Handle 429 Rate Limit errors according to Pixabay API best practices.
        
        Per Pixabay API docs (https://pixabay.com/api/docs/):
        - X-RateLimit-Limit: Maximum requests per 60 seconds (default: 100)
        - X-RateLimit-Remaining: Remaining requests in current window
        - X-RateLimit-Reset: Remaining time in seconds until reset
        
        Returns None to indicate the request should be retried later.
        """
        if response.status_code == 429:
            # Check for X-RateLimit-Reset header (Pixabay provides this)
            rate_limit_reset = response.headers.get("X-RateLimit-Reset")
            rate_limit_remaining = response.headers.get("X-RateLimit-Remaining", "0")
            
            if rate_limit_reset:
                try:
                    # X-RateLimit-Reset is remaining seconds until reset
                    wait_time = int(rate_limit_reset)
                    # Ensure minimum wait time
                    wait_time = max(wait_time, 60)  # At least 60 seconds
                    print(f"Pixabay rate limit hit (429). Remaining: {rate_limit_remaining}. Waiting {wait_time} seconds (per X-RateLimit-Reset header)...")
                    time.sleep(wait_time)
                except (ValueError, TypeError):
                    # If X-RateLimit-Reset is invalid, use default delay
                    print(f"Pixabay rate limit hit (429). Waiting {CONFIG['RETRY_DELAY_429']} seconds...")
                    time.sleep(CONFIG["RETRY_DELAY_429"])
            else:
                # Default: wait 1 minute for rate limit reset (60 second window)
                print(f"Pixabay rate limit hit (429). Waiting {CONFIG['RETRY_DELAY_429']} seconds...")
                time.sleep(CONFIG["RETRY_DELAY_429"])
            return None
        return None
    
    def fetch_videos(self, query: str, per_page: int = 20) -> Optional[Dict]:
        """
        Fetch videos from Pixabay API with rate limiting.
        
        Per Pixabay API docs (https://pixabay.com/api/docs/):
        - Endpoint: https://pixabay.com/api/videos/
        - per_page: 3-200 (default: 20)
        - video_type: "all", "film", "animation"
        - safesearch: "true" or "false" (default: "false")
        
        Args:
            query: Search query string (URL encoded automatically)
            per_page: Number of results per page (3-200, default: 20)
        
        Returns:
            API response dict with "hits" array or None on error
        """
        # Enforce per_page limit (Pixabay API: 3-200)
        per_page = max(3, min(per_page, 200))
        
        # Rate limiting delay (100 requests per 60 seconds)
        self._rate_limit_delay()
        
        try:
            url = f"{self.api_base_url}/videos/"
            params = {
                "key": self.api_key,
                "q": query,
                "per_page": per_page,
                "video_type": "all",  # all, film, animation
                "safesearch": "true"  # Safe for all ages
            }
            response = self.session.get(url, params=params, timeout=10)
            
            # Handle rate limit errors specifically
            if response.status_code == 429:
                self._handle_rate_limit_error(response)
                return None
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Already handled above, but catch here for safety
                return None
            print(f"HTTP error fetching Pixabay videos for '{query}': {e}")
            return None
        except Exception as e:
            print(f"Error fetching Pixabay videos for '{query}': {e}")
            return None
    
    def fetch_photos(self, query: str, per_page: int = 20) -> Optional[Dict]:
        """
        Fetch photos from Pixabay API with rate limiting.
        
        Per Pixabay API docs (https://pixabay.com/api/docs/):
        - Endpoint: https://pixabay.com/api/
        - per_page: 3-200 (default: 20)
        - image_type: "all", "photo", "illustration", "vector"
        - safesearch: "true" or "false" (default: "false")
        
        Args:
            query: Search query string (URL encoded automatically)
            per_page: Number of results per page (3-200, default: 20)
        
        Returns:
            API response dict with "hits" array or None on error
        """
        # Enforce per_page limit (Pixabay API: 3-200)
        per_page = max(3, min(per_page, 200))
        
        # Rate limiting delay (100 requests per 60 seconds)
        self._rate_limit_delay()
        
        try:
            url = f"{self.api_base_url}/"
            params = {
                "key": self.api_key,
                "q": query,
                "per_page": per_page,
                "image_type": "photo",  # all, photo, illustration, vector
                "safesearch": "true"  # Safe for all ages
            }
            response = self.session.get(url, params=params, timeout=10)
            
            # Handle rate limit errors specifically
            if response.status_code == 429:
                self._handle_rate_limit_error(response)
                return None
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Already handled above, but catch here for safety
                return None
            print(f"HTTP error fetching Pixabay photos for '{query}': {e}")
            return None
        except Exception as e:
            print(f"Error fetching Pixabay photos for '{query}': {e}")
            return None
    
    def get_video_url(self, video: Dict, quality: str = "hd") -> Optional[str]:
        """
        Extract video URL from Pixabay video object.
        
        Per Pixabay API docs (https://pixabay.com/api/docs/):
        - large: Usually 3840x2160 (may not be available, empty URL if unavailable)
        - medium: Usually 1920x1080 (available for all videos)
        - small: Usually 1280x720 (available for all videos)
        - tiny: Usually 960x540 (available for all videos)
        
        Args:
            video: Pixabay video object from API response
            quality: Desired quality - "hd" (maps to large), "medium", "small", or "tiny"
        
        Returns:
            Video URL string or None if not available
        """
        if not video or "videos" not in video:
            return None
        
        videos = video["videos"]
        # Try to get best quality available (per API documentation)
        # "hd" maps to "large" (highest quality)
        if quality == "hd" and "large" in videos and videos["large"].get("url"):
            return videos["large"].get("url")
        elif "medium" in videos and videos["medium"].get("url"):
            return videos["medium"].get("url")
        elif "small" in videos and videos["small"].get("url"):
            return videos["small"].get("url")
        elif "tiny" in videos and videos["tiny"].get("url"):
            return videos["tiny"].get("url")
        elif videos:
            # Return first available non-empty URL
            for key in ["large", "medium", "small", "tiny"]:
                if key in videos and videos[key].get("url"):
                    return videos[key].get("url")
        return None
    
    def get_image_url(self, photo: Dict, size: str = "large") -> Optional[str]:
        """
        Extract image URL from Pixabay photo object.
        
        Per Pixabay API docs (https://pixabay.com/api/docs/):
        - largeImageURL: Scaled image with max width/height of 1280px
        - webformatURL: Medium sized image with max width/height of 640px
          (Can replace '_640' with '_180', '_340', or '_960' for other sizes)
        - previewURL: Low resolution image with max width/height of 150px
        - imageURL: Original image (full resolution, requires full API access)
        
        Args:
            photo: Pixabay photo object from API response
            size: Desired size - "original", "large", "medium", or "small"
        
        Returns:
            Image URL string or None if not available
        """
        if not photo:
            return None
        
        # Map our size names to Pixabay fields (per API documentation)
        size_mapping = {
            "original": photo.get("imageURL") or photo.get("largeImageURL"),
            "large": photo.get("largeImageURL") or photo.get("webformatURL"),
            "medium": photo.get("webformatURL") or photo.get("previewURL"),
            "small": photo.get("previewURL")
        }
        
        return size_mapping.get(size) or photo.get("largeImageURL") or photo.get("webformatURL")


class UnsplashClient:
    """Unsplash API client for images (no video search)."""

    def __init__(self, api_key: str, base_url: str = "https://api.unsplash.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def fetch_photos(self, query: str, per_page: int = 20) -> Optional[Dict]:
        """Fetch photos from Unsplash search. Returns API response dict or None."""
        if not self.api_key:
            return None
        try:
            url = f"{self.base_url}/search/photos"
            params = {
                "query": query,
                "client_id": self.api_key,
                "per_page": min(per_page, 30),
                "orientation": "landscape",
            }
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Unsplash fetch error for '{query}': {e}")
            return None

    def get_image_url(self, photo: Dict, size: str = "large") -> Optional[str]:
        """Extract image URL from Unsplash photo object."""
        if not photo or "urls" not in photo:
            return None
        urls = photo.get("urls", {})
        return urls.get("regular") or urls.get("full") or urls.get("small") or urls.get("thumb", "")


def _word_count_from_html(html_or_text: str) -> int:
    """Strip HTML and return word count for Article wordCount schema."""
    if not html_or_text or not isinstance(html_or_text, str):
        return 0
    stripped = re.sub(r"<[^>]+>", " ", html_or_text)
    stripped = " ".join(stripped.split())
    return len(stripped.split()) if stripped else 0


def _organization_same_as() -> List[str]:
    """Return Organization sameAs URLs from config (meta.sameAs or brand.sameAs), or placeholder fallback."""
    same_as = (SITE_CONFIG.get("meta") or {}).get("sameAs") or (SITE_CONFIG.get("brand") or {}).get("sameAs")
    if same_as and isinstance(same_as, list) and len(same_as) > 0:
        return [u for u in same_as if u and isinstance(u, str)]
    handle = (SITE_CONFIG.get("meta") or {}).get("twitterHandle", "@atlsoccerhub").replace("@", "")
    return [
        f"https://twitter.com/{handle}",
        f"https://www.facebook.com/{handle}"
    ]


class SEOHelper:
    """SEO helper functions"""
    
    @staticmethod
    def escape_html(text: str) -> str:
        """Escape HTML special characters"""
        return html.escape(str(text))
    
    @staticmethod
    def generate_meta_tags(data: Dict) -> Dict:
        """Generate comprehensive meta tags for SEO, GEO, and AEO"""
        title = data.get("title", "")
        description = data.get("description", "")
        canonical = data.get("canonical", "")
        og_image = _absolute_image_url(data.get("ogImage", "") or "")
        og_url = data.get("ogUrl", "")
        keywords = data.get("keywords", [])
        location = data.get("location", "")
        theme_color = data.get("themeColor", "#0B5E2F")
        hreflang_alternates = data.get("hreflangAlternates", [])
        page_type = data.get("pageType", "")
        
        # Optimize keywords if not provided
        if not keywords and location:
            keywords = SEOHelper.generate_keywords_optimized(location, page_type)
        
        # Optimize description if not provided or too short
        if not description or len(description) < 120:
            description = SEOHelper.generate_meta_description_optimized(title, location or HUB_MARKETING, page_type)
        
        # Locale from config
        locale_cfg = SITE_CONFIG.get("locale", {})
        content_language = locale_cfg.get("language", "en-US")
        geo_region = locale_cfg.get("region", "US-GA")
        og_locale = locale_cfg.get("locale", "en_US")
        # Base meta tags with enhanced SEO
        meta_tags = {
            "title": f'<title>{SEOHelper.escape_html(title)}</title>',
            "description": f'<meta name="description" content="{SEOHelper.escape_html(description)}">',
            "canonical": f'<link rel="canonical" href="{canonical}">',
            "robots": '<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">',
            "author": f'<meta name="author" content="{SITE_CONFIG["brand"]["siteName"]}">',
            "language": f'<meta http-equiv="content-language" content="{SEOHelper.escape_html(content_language)}">',
            "ogTags": SEOHelper.generate_og_tags({"title": title, "description": description, "image": og_image, "url": og_url, "locale": og_locale}),
            "twitterTags": SEOHelper.generate_twitter_tags({"title": title, "description": description, "image": og_image}),
            "themeColor": f'<meta name="theme-color" content="{theme_color}">',
            "appleMobileWebApp": f'<meta name="mobile-web-app-capable" content="yes">\n      <meta name="apple-mobile-web-app-capable" content="yes">\n      <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n      <meta name="apple-mobile-web-app-title" content="{SITE_CONFIG["brand"]["siteName"]}">',
            "formatDetection": '<meta name="format-detection" content="telephone=no">',
            "referrer": '<meta name="referrer" content="strict-origin-when-cross-origin">',
            "viewport": '<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">',
            # Additional SEO meta tags
            "rating": '<meta name="rating" content="general">',
            "distribution": '<meta name="distribution" content="global">',
            "revisitAfter": '<meta name="revisit-after" content="7 days">',
            "googlebot": '<meta name="googlebot" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">',
            "bingbot": '<meta name="bingbot" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">'
        }
        
        # Add keywords if provided
        if keywords:
            # Limit keywords to top 10 for optimal SEO
            keywords_limited = keywords[:10]
            keywords_str = ", ".join([SEOHelper.escape_html(k) for k in keywords_limited])
            meta_tags["keywords"] = f'<meta name="keywords" content="{keywords_str}">'
        else:
            meta_tags["keywords"] = ""
        
        # Add geographic meta tags (region from config)
        if location:
            meta_tags["geo"] = f'<meta name="geo.region" content="{SEOHelper.escape_html(geo_region)}"><meta name="geo.placename" content="{SEOHelper.escape_html(location)}">'
        else:
            meta_tags["geo"] = f'<meta name="geo.region" content="{SEOHelper.escape_html(geo_region)}">'
        
        # Add hreflang alternates if provided
        if hreflang_alternates:
            hreflang_tags = "\n".join([
                f'      <link rel="alternate" hreflang="{alt["lang"]}" href="{alt["url"]}">'
                for alt in hreflang_alternates
            ])
            meta_tags["hreflang"] = hreflang_tags
        else:
            meta_tags["hreflang"] = ""
        
        return meta_tags
    
    @staticmethod
    def generate_og_tags(data: Dict) -> str:
        """Generate Open Graph tags with enhanced properties"""
        title = data.get("title", "")
        description = data.get("description", "")
        image = data.get("image", "")
        url = data.get("url", "")
        site_name = data.get("siteName", SITE_CONFIG["brand"]["siteName"])
        locale = data.get("locale", (SITE_CONFIG.get("locale", {}) or {}).get("locale", "en_US"))
        meta_cfg = SITE_CONFIG.get("meta", {}) or {}
        image_width = data.get("imageWidth") or str(meta_cfg.get("ogImageWidth", 1200))
        image_height = data.get("imageHeight") or str(meta_cfg.get("ogImageHeight", 630))
        image_alt = data.get("imageAlt", title)
        
        og_tags = f'''      <meta property="og:title" content="{SEOHelper.escape_html(title)}">
      <meta property="og:description" content="{SEOHelper.escape_html(description)}">
      <meta property="og:image" content="{image}">
      <meta property="og:image:width" content="{image_width}">
      <meta property="og:image:height" content="{image_height}">
      <meta property="og:image:alt" content="{SEOHelper.escape_html(image_alt)}">
      <meta property="og:url" content="{url}">
      <meta property="og:type" content="website">
      <meta property="og:site_name" content="{SEOHelper.escape_html(site_name)}">
      <meta property="og:locale" content="{locale}">'''
        
        # Add video tags if video provided (absolute URL for crawlers)
        if data.get("video"):
            v_url = _absolute_image_url(str(data.get("video")))
            og_tags += f'''
      <meta property="og:video" content="{SEOHelper.escape_html(v_url)}">
      <meta property="og:video:type" content="video/mp4">'''
        
        return og_tags
    
    @staticmethod
    def generate_twitter_tags(data: Dict) -> str:
        """Generate Twitter Card tags"""
        title = data.get("title", "")
        description = data.get("description", "")
        image = data.get("image", "")
        site_handle = data.get("siteHandle", SITE_CONFIG["meta"].get("twitterHandle", "@atlsoccerhub"))
        
        return f'''      <meta name="twitter:card" content="summary_large_image">
      <meta name="twitter:site" content="{site_handle}">
      <meta name="twitter:creator" content="{site_handle}">
      <meta name="twitter:title" content="{SEOHelper.escape_html(title)}">
      <meta name="twitter:description" content="{SEOHelper.escape_html(description)}">
      <meta name="twitter:image" content="{image}">'''
    
    @staticmethod
    def generate_json_ld(data: Dict) -> str:
        """Generate JSON-LD structured data"""
        page_type = data.get("type", "WebPage")
        title = data.get("title", "")
        description = data.get("description", "")
        url = data.get("url", "")
        date_modified = data.get("dateModified", "")
        organization = data.get("organization", {"name": SITE_CONFIG["brand"]["siteName"], "publisher": SITE_CONFIG["brand"]["poweredBy"]})
        breadcrumbs = data.get("breadcrumbs", [])
        primary_image = data.get("primaryImageOfPage")
        meta_cfg = SITE_CONFIG.get("meta", {}) or {}
        og_w = meta_cfg.get("ogImageWidth", 1200)
        og_h = meta_cfg.get("ogImageHeight", 630)
        
        base_schema = {
            "@context": "https://schema.org",
            "@type": page_type,
            "name": title,
            "description": description,
            "url": url,
            "dateModified": date_modified,
            "publisher": {
                "@type": "Organization",
                "name": organization["name"],
                "publisher": {
                    "@type": "Organization",
                    "name": organization["publisher"]
                }
            }
        }
        if primary_image:
            img = {"@type": "ImageObject", "url": primary_image}
            if data.get("primaryImageWidth") or data.get("primaryImageHeight"):
                if data.get("primaryImageWidth"):
                    img["width"] = data["primaryImageWidth"]
                if data.get("primaryImageHeight"):
                    img["height"] = data["primaryImageHeight"]
            else:
                img["width"] = og_w
                img["height"] = og_h
            base_schema["primaryImageOfPage"] = img
        
        if breadcrumbs:
            base_schema["breadcrumb"] = {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": i + 1,
                        "name": crumb["name"],
                        "item": crumb["url"]
                    }
                    for i, crumb in enumerate(breadcrumbs)
                ]
            }
        # AEO: Speakable for voice / answer engines (hub and city pages)
        speakable_selectors = data.get("speakableSelectors")
        if speakable_selectors:
            base_schema["speakable"] = {
                "@type": "SpeakableSpecification",
                "cssSelector": speakable_selectors
            }
        
        base_url = "/".join(url.split("/")[:3])
        website_description = (meta_cfg.get("authoritativeSummary") or "").strip() or SITE_CONFIG["brand"].get("tagline", "")
        website_schema = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": SITE_CONFIG["brand"]["siteName"],
            "url": base_url,
            "description": website_description,
            "potentialAction": {
                "@type": "SearchAction",
                "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": f"{base_url}/search?q={{search_term_string}}"
                },
                "query-input": "required name=search_term_string"
            }
        }
        
        # Generate Organization schema (should be on every page)
        organization_schema = SEOHelper.generate_organization_schema(base_url)
        
        webpage_script = f'<script type="application/ld+json">{json.dumps(base_schema, indent=2)}</script>'
        website_script = f'<script type="application/ld+json">{json.dumps(website_schema, indent=2)}</script>'
        organization_script = f'<script type="application/ld+json">{json.dumps(organization_schema, indent=2)}</script>'
        
        # Standalone BreadcrumbList for rich results (when breadcrumbs present)
        breadcrumb_standalone_script = ""
        if breadcrumbs:
            breadcrumb_list_schema = {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": i + 1, "name": crumb["name"], "item": crumb["url"]}
                    for i, crumb in enumerate(breadcrumbs)
                ]
            }
            breadcrumb_standalone_script = f'\n<script type="application/ld+json">{json.dumps(breadcrumb_list_schema, indent=2)}</script>'
        
        # Add additional schemas if provided
        additional_schemas = data.get("additionalSchemas", [])
        additional_scripts = "\n".join([
            f'<script type="application/ld+json">{json.dumps(schema, indent=2)}</script>'
            for schema in additional_schemas
        ])
        
        return webpage_script + "\n" + website_script + "\n" + organization_script + breadcrumb_standalone_script + ("\n" + additional_scripts if additional_scripts else "")
    
    @staticmethod
    def generate_faq_schema(faqs: List[Dict], url: str) -> Dict:
        """Generate FAQPage schema for AEO optimization"""
        if not faqs:
            return None
        
        faq_items = []
        for faq in faqs:
            faq_items.append({
                "@type": "Question",
                "name": faq.get("question", ""),
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": faq.get("answer", "")
                }
            })
        
        return {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faq_items
        }
    
    @staticmethod
    def generate_howto_schema(steps: List[str], title: str, description: str, url: str) -> Dict:
        """Generate HowTo schema for answer block (AEO optimization)"""
        if not steps:
            return None
        
        howto_steps = []
        for i, step in enumerate(steps, 1):
            howto_steps.append({
                "@type": "HowToStep",
                "position": i,
                "name": step,
                "text": step
            })
        
        return {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": title,
            "description": description,
            "step": howto_steps
        }
    
    @staticmethod
    def generate_local_business_schema(city_name: str, url: str, area_name: Optional[str] = None, 
                                      coordinates: Optional[Dict] = None, postal_code: Optional[str] = None,
                                      include_rating: bool = True) -> Dict:
        """Generate enhanced LocalBusiness schema for GEO optimization"""
        location_name = f"{area_name}, {city_name}" if area_name else city_name
        
        locale_cfg = SITE_CONFIG.get("locale", {}) or {}
        address_country = locale_cfg.get("country", "US")
        address_region = locale_cfg.get("regionName", "GA")
        default_tel = (locale_cfg.get("defaultTelephone") or "").strip()
        schema = {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": f"{SITE_CONFIG['brand']['siteName']} - {location_name}",
            "description": f"Find, organize, and play soccer games in {location_name} across {HUB_MARKETING}",
            "url": url,
            "address": {
                "@type": "PostalAddress",
                "addressLocality": location_name,
                "addressRegion": address_region,
                "addressCountry": address_country
            },
            "areaServed": {
                "@type": "City",
                "name": city_name
            },
            "serviceType": "Soccer Community Platform",
            "priceRange": "Free to join",
            "openingHours": "Mo-Su 00:00-23:59",
            "paymentAccepted": "Free"
        }
        if default_tel:
            schema["telephone"] = default_tel
        
        # Add postal code if provided
        if postal_code:
            schema["address"]["postalCode"] = postal_code
        
        # Add coordinates if provided (handle both lat/lng and latitude/longitude formats)
        if coordinates:
            lat = coordinates.get("latitude") or coordinates.get("lat")
            lng = coordinates.get("longitude") or coordinates.get("lng")
            if lat and lng:
                schema["geo"] = {
                    "@type": "GeoCoordinates",
                    "latitude": lat,
                    "longitude": lng
                }
        
        # Add aggregate rating for trust signals
        if include_rating:
            schema["aggregateRating"] = SEOHelper.generate_aggregate_rating_schema()
        
        # Add ServiceArea for better local SEO
        if area_name and coordinates:
            lat = coordinates.get("latitude") or coordinates.get("lat")
            lng = coordinates.get("longitude") or coordinates.get("lng")
            if lat and lng:
                schema["serviceArea"] = {
                    "@type": "GeoCircle",
                    "geoMidpoint": {
                        "@type": "GeoCoordinates",
                        "latitude": lat,
                        "longitude": lng
                    },
                    "geoRadius": {
                        "@type": "Distance",
                        "value": 10,
                        "unitCode": "KM"
                    }
                }
        
        return schema
    
    @staticmethod
    def generate_place_schema(city_name: str, url: str, area_name: Optional[str] = None, coordinates: Optional[Dict] = None) -> Dict:
        """Generate enhanced Place schema for GEO optimization"""
        location_name = f"{area_name}, {city_name}" if area_name else city_name
        
        locale_cfg = (SITE_CONFIG.get("locale", {}) or {})
        address_country = locale_cfg.get("country", "US")
        address_region = locale_cfg.get("regionName", "GA")
        schema = {
            "@context": "https://schema.org",
            "@type": "Place",
            "name": location_name,
            "description": f"Soccer community in {location_name}, {HUB_MARKETING}",
            "url": url,
            "address": {
                "@type": "PostalAddress",
                "addressLocality": location_name,
                "addressRegion": address_region,
                "addressCountry": address_country
            }
        }
        
        # Add coordinates if provided
        if coordinates:
            schema["geo"] = {
                "@type": "GeoCoordinates",
                "latitude": coordinates.get("latitude") or coordinates.get("lat"),
                "longitude": coordinates.get("longitude") or coordinates.get("lng")
            }
        
        return schema
    
    @staticmethod
    def generate_organization_schema(base_url: str) -> Dict:
        """Generate comprehensive Organization schema"""
        meta_cfg = SITE_CONFIG.get("meta", {}) or {}
        desc = (meta_cfg.get("authoritativeSummary") or "").strip() or SITE_CONFIG["brand"]["valueProposition"]
        return {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": SITE_CONFIG["brand"]["siteName"],
            "alternateName": f"{SITE_CONFIG['brand']['siteName']}",
            "url": base_url,
            "logo": f"{base_url}/assets/images/football_hub_logo_2.png",
            "description": desc,
            "foundingDate": "2025",
            "founder": {
                "@type": "Organization",
                "name": "GameOn Active"
            },
            "sameAs": _organization_same_as(),
            "contactPoint": {
                "@type": "ContactPoint",
                "contactType": "Customer Service",
                "email": f"info@{SITE_CONFIG['baseUrl'].replace('https://', '').replace('http://', '')}",
                "areaServed": (SITE_CONFIG.get("locale", {}) or {}).get("country", "US"),
                "availableLanguage": [(SITE_CONFIG.get("locale", {}) or {}).get("language", "en-US")]
            }
        }
    
    @staticmethod
    def generate_video_object_schema(video_url: str, thumbnail_url: str, title: str, description: str, duration: Optional[str] = None) -> Dict:
        """Generate VideoObject schema for video content"""
        schema = {
            "@context": "https://schema.org",
            "@type": "VideoObject",
            "name": title,
            "description": description,
            "thumbnailUrl": thumbnail_url,
            "uploadDate": datetime.now().isoformat(),
            "contentUrl": video_url,
            "embedUrl": video_url
        }
        
        if duration:
            schema["duration"] = duration
        
        return schema
    
    @staticmethod
    def generate_image_object_schema(image_url: str, caption: str, width: int = 1200, height: int = 630) -> Dict:
        """Generate ImageObject schema for images"""
        return {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "url": image_url,
            "caption": caption,
            "width": width,
            "height": height
        }
    
    @staticmethod
    def generate_event_schema(event_name: str, start_date: str, location_name: str, url: str, description: Optional[str] = None) -> Dict:
        """Generate Event schema for upcoming events"""
        schema = {
            "@context": "https://schema.org",
            "@type": "SportsEvent",
            "name": event_name,
            "startDate": start_date,
            "location": {
                "@type": "Place",
                "name": location_name,
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": location_name,
                    "addressCountry": (SITE_CONFIG.get("locale", {}) or {}).get("country", "US")
                }
            },
            "url": url,
            "sport": "Soccer"
        }
        
        if description:
            schema["description"] = description
        
        return schema
    
    @staticmethod
    def generate_aggregate_rating_schema(rating_value: float = 4.8, review_count: int = 150) -> Dict:
        """Generate AggregateRating schema for reviews"""
        return {
            "@type": "AggregateRating",
            "ratingValue": rating_value,
            "reviewCount": review_count,
            "bestRating": 5,
            "worstRating": 1
        }
    
    @staticmethod
    def generate_review_schema(reviews: List[Dict]) -> Dict:
        """Generate Review schema for trust signals and LLM optimization"""
        if not reviews:
            return None
        
        review_items = []
        for review in reviews:
            review_items.append({
                "@type": "Review",
                "author": {
                    "@type": "Person",
                    "name": review.get("author", "Anonymous")
                },
                "datePublished": review.get("date", datetime.now().strftime("%Y-%m-%d")),
                "reviewBody": review.get("text", ""),
                "reviewRating": {
                    "@type": "Rating",
                    "ratingValue": review.get("rating", 5),
                    "bestRating": 5,
                    "worstRating": 1
                }
            })
        
        return {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": SITE_CONFIG["brand"]["siteName"],
            "aggregateRating": SEOHelper.generate_aggregate_rating_schema(),
            "review": review_items[:5]  # Limit to 5 reviews
        }
    
    @staticmethod
    def generate_article_schema_enhanced(title: str, description: str, url: str, image_url: str,
                                         author: str, date_published: str, date_modified: str,
                                         keywords: List[str], article_section: str = "News",
                                         content_html_or_text: Optional[str] = None) -> Dict:
        """Generate enhanced Article schema optimized for LLM parsing. Optional content for wordCount; speakable includes first paragraph."""
        speakable_selectors = ["h1", ".hero__title", ".blog-post-page__title", ".blog-post-page__content p:first-of-type"]
        schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "description": description,
            "image": {
                "@type": "ImageObject",
                "url": image_url,
                "width": 1200,
                "height": 630
            },
            "datePublished": date_published,
            "dateModified": date_modified,
            "author": {
                "@type": "Organization",
                "name": author,
                "url": f"{ROOT_URL}"
            },
            "publisher": {
                "@type": "Organization",
                "name": SITE_CONFIG["brand"]["siteName"],
                "logo": {
                    "@type": "ImageObject",
                    "url": f"{SITE_CONFIG['baseUrl']}/assets/images/football_hub_logo_2.png",
                    "width": 512,
                    "height": 512
                }
            },
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": url
            },
            "articleSection": article_section,
            "keywords": ", ".join(keywords),
            "inLanguage": (SITE_CONFIG.get("locale", {}) or {}).get("language", "en-US"),
            "isAccessibleForFree": True,
            "speakable": {
                "@type": "SpeakableSpecification",
                "cssSelector": speakable_selectors
            }
        }
        if content_html_or_text and content_html_or_text.strip():
            word_count = _word_count_from_html(content_html_or_text)
            if word_count > 0:
                schema["wordCount"] = word_count
        return schema
    
    @staticmethod
    def generate_breadcrumb_schema_enhanced(breadcrumbs: List[Dict], url: str) -> Dict:
        """Generate enhanced BreadcrumbList schema"""
        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i + 1,
                    "name": crumb["name"],
                    "item": crumb["url"]
                }
                for i, crumb in enumerate(breadcrumbs)
            ]
        }
    
    @staticmethod
    def generate_keywords_optimized(location: str, page_type: str, modifiers: List[str] = None) -> List[str]:
        """
        Generate optimized keyword list for SEO - ALL PAGES COMPETE FOR SAME KEYWORDS
        Strategy: Every page targets the same primary keywords to dominate search results
        """
        # PRIMARY KEYWORDS - Same for ALL pages (core competition keywords)
        primary_keywords = SPORT_CONFIG["keywords"]["primary"].copy()
        
        # INTENT KEYWORDS - Same for ALL pages
        intent_keywords = SPORT_CONFIG["keywords"]["intent"].copy()
        
        # MODIFIER KEYWORDS - Same for ALL pages
        modifier_keywords = SPORT_CONFIG["keywords"]["modifiers"].copy()
        
        # Start with ALL primary keywords (every page competes for these)
        keywords = primary_keywords + intent_keywords + modifier_keywords
        
        # Add location-specific variations (but keep primary keywords)
        location_keywords = [kw.replace("[city]", location) for kw in SPORT_CONFIG["keywords"]["location"]]
        keywords.extend(location_keywords)
        
        # Add any additional modifiers
        if modifiers:
            keywords.extend(modifiers)
        
        # Add long-tail variations with location context
        long_tail = [
            f"find soccer games in {location}",
            f"organize soccer in {location}",
            f"5v5 soccer {location}",
            f"pickup soccer {location}",
            f"casual soccer {location}",
            f"join soccer game {location}",
            f"soccer community {location}",
            f"play soccer {location}",
            # Universal long-tail (no location) - ALL pages compete
            "find soccer games",
            "organize soccer",
            "5v5 soccer",
            "pickup soccer",
            "casual soccer",
            "join soccer game",
            "soccer community",
            "play soccer",
        ]
        for seed in hub_keyword_seeds(SITE_CONFIG, SPORT_CONFIG):
            if seed not in long_tail:
                long_tail.append(seed)
        keywords.extend(long_tail)
        
        return list(set(keywords))  # Remove duplicates
    
    @staticmethod
    def generate_meta_description_optimized(title: str, location: str, page_type: str, 
                                           include_cta: bool = True) -> str:
        """
        Generate optimized meta description - ALL PAGES USE SAME PRIMARY KEYWORDS
        Strategy: Every page description includes core keywords for maximum competition
        """
        # Core keywords that ALL pages compete for
        core_keywords = "Find and organize pickup soccer games, 5v5, casual soccer"
        
        # Base description with core keywords (same for all pages)
        if page_type == "hub":
            desc = f"{core_keywords} across {HUB_MARKETING}. Join {SITE_CONFIG['brand']['siteName']} to get notified when new games go live near you."
        elif page_type == "city":
            desc = f"{core_keywords} in {location}. Join the community organizing pickup and casual soccer matches."
        elif page_type == "area":
            desc = f"{core_keywords} in {location}. Join local players organizing casual matches and pickup games."
        elif page_type == "blog":
            desc = f"{core_keywords} across {HUB_MARKETING}. Learn how to find, organize, and play soccer games."
        else:
            desc = f"{core_keywords}. Join the community and find your next game."
        
        # Add CTA if requested
        if include_cta and len(desc) < 140:
            desc += " Sign up for free game invites."
        
        # Ensure optimal length (150-160 chars) with core keywords
        if len(desc) > 160:
            # Prioritize keeping core keywords
            if "5-a-side" in desc and len(desc) > 160:
                desc = desc[:157] + "..."
            else:
                desc = desc[:157] + "..."
        elif len(desc) < 120:
            desc += " All skill levels welcome. Free to join."
        
        return desc
    
    @staticmethod
    def generate_service_schema(service_name: str, service_type: str, area_served: str, url: str) -> Dict:
        """Generate Service schema for better local SEO"""
        return {
            "@context": "https://schema.org",
            "@type": "Service",
            "name": service_name,
            "serviceType": service_type,
            "areaServed": {
                "@type": "City",
                "name": area_served
            },
            "provider": {
                "@type": "Organization",
                "name": SITE_CONFIG["brand"]["siteName"]
            },
            "url": url
        }


_pexels_cfg = SITE_CONFIG.get("pexels", {})
pexels_client = PexelsClient(
    _pexels_cfg.get("apiKey", ""),
    _pexels_cfg.get("apiBaseUrl", "https://api.pexels.com")
)

_pixabay_cfg = SITE_CONFIG.get("pixabay", {})
pixabay_client = PixabayClient(
    _pixabay_cfg.get("apiKey", ""),
    _pixabay_cfg.get("apiBaseUrl", "https://pixabay.com/api")
)


def _pexels_api_configured() -> bool:
    return bool((SITE_CONFIG.get("pexels") or {}).get("apiKey"))


def _pixabay_api_configured() -> bool:
    return bool((SITE_CONFIG.get("pixabay") or {}).get("apiKey"))


# Initialize Unsplash client (optional, for images only)
_unsplash_cfg = SITE_CONFIG.get("unsplash", {})
unsplash_client = UnsplashClient(
    _unsplash_cfg.get("apiKey", ""),
    _unsplash_cfg.get("apiBaseUrl", "https://api.unsplash.com")
) if _unsplash_cfg.get("apiKey") else None


def _get_media_queries() -> Dict:
    """Single source for search queries: media.searchQueries or pexels.searchQueries fallback."""
    return (
        SITE_CONFIG.get("media", {}).get("searchQueries")
        or SITE_CONFIG.get("pexels", {}).get("searchQueries")
        or {}
    )


def _get_image_provider_order() -> List[str]:
    """Provider order for image fallback (e.g. ['pexels', 'pixabay', 'unsplash'])."""
    order = SITE_CONFIG.get("media", {}).get("imageProviderOrder") or ["pexels", "pixabay"]
    return [p for p in order if p in ("pexels", "pixabay", "unsplash")]


def compute_config_hash() -> str:
    """Compute hash of configuration to detect changes"""
    config_string = json.dumps({
        "media_queries": _get_media_queries(),
        "cities": [{"name": c["name"], "slug": c["slug"]} for c in SPORT_CONFIG["cities"]]
    }, sort_keys=True)
    return hashlib.md5(config_string.encode()).hexdigest()


def load_cache() -> bool:
    """Load cache from disk if available and valid"""
    try:
        cache_path = Path(CONFIG["CACHE_FILE"])
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            
            # Check cache version (config hash)
            current_config_hash = compute_config_hash()
            cached_config_hash = cache.get("configHash")
            
            if cached_config_hash != current_config_hash:
                print("Cache invalidated: configuration has changed")
                return False
            
            # Check cache age
            cache_age = time.time() - (cache.get("lastUpdated", 0) / 1000 if isinstance(cache.get("lastUpdated"), (int, float)) and cache.get("lastUpdated", 0) > 1000000000000 else cache.get("lastUpdated", 0))
            if cache_age < CONFIG["CACHE_MAX_AGE"]:
                global media_cache
                media_cache = cache
                # Ensure provider cache keys exist (for backward compatibility)
                if "pixabay_videos" not in media_cache:
                    media_cache["pixabay_videos"] = {}
                if "pixabay_photos" not in media_cache:
                    media_cache["pixabay_photos"] = {}
                if "unsplash_photos" not in media_cache:
                    media_cache["unsplash_photos"] = {}
                stats["cacheHits"] = len(media_cache.get("videos", {})) + len(media_cache.get("photos", {}))
                print(f"Loaded cache with {stats['cacheHits']} entries")
                return True
            else:
                print("Cache expired: older than 24 hours")
    except Exception as e:
        print(f"Cache load error: {e}")
    return False


def save_cache():
    """Save cache to disk with version information"""
    try:
        media_cache["lastUpdated"] = int(time.time() * 1000)
        media_cache["configHash"] = compute_config_hash()
        with open(CONFIG["CACHE_FILE"], "w", encoding="utf-8") as f:
            json.dump(media_cache, f, indent=2)
    except Exception as e:
        print(f"Failed to save cache: {e}")


def retry(func, attempts: int = CONFIG["RETRY_ATTEMPTS"], delay: float = CONFIG["RETRY_DELAY"]):
    """
    Retry wrapper for operations with exponential backoff.
    
    For 429 (rate limit) errors, uses longer delay (CONFIG["RETRY_DELAY_429"]).
    For other errors, uses exponential backoff with base delay.
    """
    for i in range(attempts):
        try:
            return func()
        except requests.exceptions.HTTPError as e:
            if i == attempts - 1:
                raise e
            # Check if it's a rate limit error (429)
            if hasattr(e, 'response') and e.response.status_code == 429:
                # Use longer delay for rate limit errors
                wait_time = CONFIG["RETRY_DELAY_429"]
                print(f"Rate limit error (429) on attempt {i+1}/{attempts}. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                # Exponential backoff for other HTTP errors
                wait_time = delay * (2 ** i)
                time.sleep(wait_time)
        except Exception as e:
            if i == attempts - 1:
                raise e
            # Exponential backoff for other errors
            wait_time = delay * (2 ** i)
            time.sleep(wait_time)


def get_random_media(media_type: str, query: str, use_pixabay_fallback: bool = True) -> Optional[Dict]:
    """
    Get random media from cache. For photos uses config-driven provider order (pexels, pixabay, unsplash).
    """
    if media_type == "video":
        cache = media_cache["videos"]
        media = cache.get(query, [])
        if not media and use_pixabay_fallback:
            media = media_cache.get("pixabay_videos", {}).get(query, [])
        if not media:
            return None
        return random.choice(media)
    # photo: use provider order
    for provider in _get_image_provider_order():
        if provider == "pexels":
            media = media_cache.get("photos", {}).get(query, [])
        elif provider == "pixabay":
            media = media_cache.get("pixabay_photos", {}).get(query, [])
        elif provider == "unsplash":
            media = media_cache.get("unsplash_photos", {}).get(query, []) if unsplash_client else []
        else:
            continue
        if media:
            return random.choice(media)
    return None


def get_random_photo_with_provider(query: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Get random photo and which provider it came from (for get_image_url dispatch)."""
    for provider in _get_image_provider_order():
        if provider == "pexels":
            media = media_cache.get("photos", {}).get(query, [])
        elif provider == "pixabay":
            media = media_cache.get("pixabay_photos", {}).get(query, [])
        elif provider == "unsplash":
            media = media_cache.get("unsplash_photos", {}).get(query, []) if unsplash_client else []
        else:
            continue
        if media:
            return random.choice(media), provider
    return None, None


def get_image_url_for_photo(photo: Dict, provider: str, size: str = "large") -> str:
    """Get image URL from photo dict using the correct client for the provider."""
    if not photo:
        return ""
    if provider == "pexels":
        return pexels_client.get_image_url(photo, size) or ""
    if provider == "pixabay":
        return pixabay_client.get_image_url(photo, size) or ""
    if provider == "unsplash" and unsplash_client:
        return unsplash_client.get_image_url(photo, size) or ""
    return ""


def get_random_hero_media() -> Dict[str, str]:
    """
    Get random video and poster media (config-driven provider order: Pexels, Pixabay, Unsplash for images).
    """
    queries = _get_media_queries()
    video_queries = queries.get("heroVideo", SITE_CONFIG.get("pexels", {}).get("searchQueries", {}).get("heroVideo", ["soccer game"]))
    poster_queries = queries.get("heroPoster", SITE_CONFIG.get("pexels", {}).get("searchQueries", {}).get("heroPoster", ["soccer field"]))
    video_query = random.choice(video_queries) if video_queries else "soccer game"
    poster_query = random.choice(poster_queries) if poster_queries else "soccer field"

    video = get_random_media("video", video_query)
    poster, poster_provider = get_random_photo_with_provider(poster_query)

    video_url = ""
    if video:
        if video_query in media_cache.get("videos", {}):
            video_url = pexels_client.get_video_url(video) or ""
        elif video_query in media_cache.get("pixabay_videos", {}):
            video_url = pixabay_client.get_video_url(video) or ""

    poster_url = get_image_url_for_photo(poster, poster_provider or "pexels", "large") if poster else ""

    return {"video": video_url, "poster": poster_url}


def download_and_save_image(image_url: str, save_path: Path) -> bool:
    """
    Download image from URL and save to local path.
    Returns True if successful, False otherwise.
    """
    try:
        response = requests.get(image_url, timeout=10, stream=True)
        response.raise_for_status()
        
        # Ensure directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save image
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True
    except Exception as e:
        print(f"Error downloading image to {save_path}: {e}")
        return False


def _get_tracking_config() -> Dict:
    """Analytics/tracking config (single source for GA4, custom endpoint, toggles)."""
    cfg = SITE_CONFIG.get("analytics", {})
    return {
        "enabled": bool(cfg.get("enabled")),
        "ga4MeasurementId": (cfg.get("ga4MeasurementId") or "").strip(),
        "eventsEndpoint": (cfg.get("eventsEndpoint") or "").strip(),
        "trackPageView": bool(cfg.get("trackPageView", True)),
        "trackClicks": bool(cfg.get("trackClicks", True)),
        "trackFormEngagement": bool(cfg.get("trackFormEngagement", True)),
    }


def _get_leads_endpoint() -> str:
    """Leads endpoint for modal submissions (config-driven). Empty = use API/localStorage."""
    cfg = SITE_CONFIG.get("leads", {})
    return (cfg.get("endpoint") or "").strip()


def _get_organizer_form_copy(city_name: str) -> tuple:
    """Return (label, help) for organizer checkbox with {city_name} substituted. Config: messaging.form."""
    form_cfg = SITE_CONFIG.get("messaging", {}).get("form", {})
    label = form_cfg.get(
        "organizerCheckboxLabel",
        "I run local games in {city_name} and want to list them on the site for free."
    ).replace("{city_name}", city_name)
    help_text = form_cfg.get(
        "organizerCheckboxHelp",
        "If you already organize runs, you can advertise them here for free and reach more players."
    ).replace("{city_name}", city_name)
    return (label, help_text)


def _absolute_image_url(url: Optional[str]) -> str:
    """Return absolute URL for Open Graph, Twitter, JSON-LD, and schema (baseUrl + path if relative)."""
    if not url:
        return ""
    u = str(url).strip()
    if u.startswith("http://") or u.startswith("https://"):
        return u
    if u.startswith("//"):
        return "https:" + u
    base = (SITE_CONFIG.get("baseUrl") or "").rstrip("/")
    if not base:
        return u
    path = u.lstrip("/")
    return f"{base}/{path}"


def _get_seo_title(page_type: str, **placeholders: str) -> str:
    """Build page title from config template when present. Placeholders: site_name, city, area, location, post_title."""
    site_name = SITE_CONFIG["brand"]["siteName"]
    templates = (SITE_CONFIG.get("seo") or {}).get("titleTemplates") or {}
    template = templates.get(page_type)
    if not template:
        return placeholders.get("fallback_title", "")
    values = {"site_name": site_name, "city": "", "area": "", "location": "", "post_title": ""}
    values.update(placeholders)
    title = template
    for key, val in values.items():
        title = title.replace("{" + key + "}", str(val or ""))
    return title[:75] if len(title) > 75 else title


def generate_in_short_section(page_type: str, city_name: Optional[str] = None) -> str:
    """Generate In short / summary block for hub and city pages (config-driven, LLM/snippet-friendly)."""
    meta_cfg = SITE_CONFIG.get("meta", {}) or {}
    if page_type == "hub":
        text = meta_cfg.get("inShortHub", "")
    elif page_type in ("city", "area") and city_name:
        template = meta_cfg.get("inShortCity", "")
        text = template.replace("{city}", city_name) if template else ""
    else:
        return ""
    if not text:
        return ""
    return f'''    <section class="in-short" aria-label="Summary">
        <div class="container container--content">
            <p class="in-short__text">{html.escape(text)}</p>
        </div>
    </section>
'''


def generate_key_takeaways_section() -> str:
    """Generate Key takeaways block from config (AEO/snippet-friendly). Returns empty if no keyTakeaways."""
    items = (SITE_CONFIG.get("meta") or {}).get("keyTakeaways") or []
    if not items:
        return ""
    lis = "".join(f'<li class="key-takeaways__item">{html.escape(str(item))}</li>' for item in items)
    return f'''    <section class="key-takeaways" aria-label="Key takeaways">
        <div class="container container--content">
            <h2 class="key-takeaways__title">In brief</h2>
            <ul class="key-takeaways__list">{lis}</ul>
        </div>
    </section>
'''


def _speakable_selectors_with_key_takeaways() -> List[str]:
    """Base speakable selectors for hub/location pages; includes .key-takeaways__item when keyTakeaways exist."""
    selectors = [".in-short__text"]
    if (SITE_CONFIG.get("meta") or {}).get("keyTakeaways"):
        selectors.append(".key-takeaways__item")
    selectors.extend([".faq-item__question", ".faq-item__answer"])
    return selectors


def _hub_speakable_selectors() -> List[str]:
    return _speakable_selectors_with_key_takeaways()


def _location_speakable_selectors() -> List[str]:
    return _speakable_selectors_with_key_takeaways()


def _get_local_assets_config() -> Dict:
    """Resolved localAssets config with defaults (single source for paths and fallbacks)."""
    cfg = SITE_CONFIG.get("localAssets", {})
    images_dir = cfg.get("imagesDir", "public/assets/images")
    videos_dir = cfg.get("videosDir", "public/assets/videos")
    return {
        "imagesDir": Path(images_dir),
        "imagesWebPath": (cfg.get("imagesWebPath") or images_dir.replace("public/", "").strip("/") or "assets/images").rstrip("/"),
        "videosDir": Path(videos_dir),
        "videosWebPath": (cfg.get("videosWebPath") or videos_dir.replace("public/", "").strip("/") or "assets/videos").rstrip("/"),
        "blogFallbackUrls": cfg.get("blogFallbackUrls", []),
        "aboutFallbackUrl": cfg.get("aboutFallbackUrl", ""),
        "cityFallbackImage": cfg.get("cityFallbackImage", "football_hub_logo_2.png"),
    }


def _local_asset_url_for_template(url: str) -> str:
    """
    Convert a local asset URL to use {{ASSET_PATH}} placeholder so replace_asset_paths() can
    fix it per page depth. Enables correct loading via file:// and on nested routes.
    """
    if not url or url.startswith("http://") or url.startswith("https://"):
        return url
    path = url.lstrip("/").strip()
    return f"{{{{ASSET_PATH}}}}{path}" if path else url


def get_local_football_images() -> List[str]:
    """
    Discover and cache section images from configurable local assets folder.
    Config: site.config localAssets.imagesDir, namePatterns, excludePatterns, extensions.
    Returns list of image filenames (relative to assets/images).
    """
    global _local_football_images_cache

    if _local_football_images_cache is not None:
        return _local_football_images_cache

    cfg = SITE_CONFIG.get("localAssets", {})
    images_dir = Path(cfg.get("imagesDir", "public/assets/images"))
    name_patterns = cfg.get("namePatterns", ["football", "soccer"])
    exclude_patterns = cfg.get("excludePatterns", ["logo", "football_hub", "volleyball"])
    ext_list = cfg.get("extensions", [".jpg", ".jpeg", ".png", ".webp"])
    image_extensions = set(e.lower() if e.startswith(".") else f".{e}".lower() for e in ext_list)

    if not images_dir.exists():
        _local_football_images_cache = []
        return []

    football_images = []
    for image_file in images_dir.iterdir():
        if not image_file.is_file() or image_file.suffix.lower() not in image_extensions:
            continue
        stem_lower = image_file.stem.lower()
        if any(p in stem_lower for p in exclude_patterns):
            continue
        if any(p in stem_lower for p in name_patterns):
            football_images.append(image_file.name)

    _local_football_images_cache = football_images
    if football_images:
        print(f"Found {len(football_images)} local football images for section fallbacks")
    return football_images


def get_local_hero_videos() -> List[str]:
    """
    Get list of local hero video filenames for hero background video.
    Priority: sport config localVideos (explicit list) else discover from localAssets.videosDir.
    Returns list of filenames (e.g. for use in <source src="...">).
    """
    global _local_hero_videos_cache

    if _local_hero_videos_cache is not None:
        return _local_hero_videos_cache

    explicit = SPORT_CONFIG.get("localVideos", [])
    if explicit:
        _local_hero_videos_cache = list(explicit)
        return _local_hero_videos_cache

    la = _get_local_assets_config()
    videos_dir = la.get("videosDir")
    if not videos_dir or not videos_dir.exists():
        _local_hero_videos_cache = []
        return []

    video_extensions = {".mp4", ".webm"}
    found = []
    for f in videos_dir.iterdir():
        if f.is_file() and f.suffix.lower() in video_extensions:
            found.append(f.name)

    _local_hero_videos_cache = sorted(found)
    if _local_hero_videos_cache:
        print(f"Found {len(_local_hero_videos_cache)} local hero videos in assets folder")
    return _local_hero_videos_cache


def get_local_football_image_url(seed: Optional[str] = None) -> Optional[str]:
    """
    Get a random football image URL from local assets with optional seed for consistency.
    
    Args:
        seed: Optional seed string for deterministic selection (e.g., post title)
    
    Returns:
        Asset URL string or None if no images available
    """
    football_images = get_local_football_images()
    
    if not football_images:
        return None
    
    # Use seed for deterministic selection if provided
    if seed:
        image_index = hash(seed) % len(football_images)
    else:
        image_index = random.randint(0, len(football_images) - 1)
    
    image_filename = football_images[image_index]
    asset_prefix = get_asset_path()
    web_path = _get_local_assets_config()["imagesWebPath"]
    encoded_name = quote(image_filename, safe="")
    return f"{asset_prefix}{web_path}/{encoded_name}"


def get_blog_image_url(post_title: str) -> str:
    """
    Get blog post image URL. Config-driven.
    Priority: Local assets (localAssets) → Sport config images.blog → localAssets.blogFallbackUrls.
    """
    local_image_url = get_local_football_image_url(seed=post_title)
    if local_image_url:
        return local_image_url
    images = SPORT_CONFIG.get("images", {}).get("blog", [])
    if images:
        image_index = hash(post_title) % len(images)
        return images[image_index]
    fallbacks = _get_local_assets_config().get("blogFallbackUrls", [])
    if fallbacks:
        return fallbacks[hash(post_title) % len(fallbacks)]
    return ""


def get_about_image_url() -> str:
    """
    Get about section image URL. Config-driven.
    Priority: Local assets → Sport config images.about → localAssets.aboutFallbackUrl.
    """
    local_image_url = get_local_football_image_url(seed="about")
    if local_image_url:
        return local_image_url
    image_url = SPORT_CONFIG.get("images", {}).get("about")
    if image_url:
        return image_url
    return _get_local_assets_config().get("aboutFallbackUrl", "") or ""


def get_city_image_url(city_slug: str, city_name: str) -> str:
    """
    Get city image URL. Config-driven: localAssets.imagesDir, imagesWebPath, cityFallbackImage; media.searchQueries.cityFallback.
    Tries local file first, then APIs (Pexels, Pixabay, Unsplash) with city query and cityFallback queries.
    """
    la = _get_local_assets_config()
    city_image_path = la["imagesDir"] / f"{city_slug}.jpg"
    asset_prefix = get_asset_path()
    web_path = la["imagesWebPath"]

    if city_image_path.exists():
        return f"{asset_prefix}{web_path}/{city_slug}.jpg"

    queries = _get_media_queries()
    city_queries = [f"{city_name} city"] + (queries.get("cityFallback") or ["soccer city", "football stadium", "soccer field"])

    def try_providers_for_query(q: str) -> Optional[str]:
        # Use cache first (provider order)
        photo, provider = get_random_photo_with_provider(q)
        if photo:
            image_url = get_image_url_for_photo(photo, provider or "pexels", "large")
            if image_url and download_and_save_image(image_url, city_image_path):
                return image_url
        # Fetch from APIs in provider order (skip HTTP when keys are unset — use local fallbacks)
        if _pexels_api_configured():
            stats["apiCalls"] += 1
            result = retry(lambda: pexels_client.fetch_photos(q, 10))
            if result and "photos" in result and len(result["photos"]) > 0:
                media_cache["photos"][q] = result["photos"]
                url = pexels_client.get_image_url(result["photos"][0], "large")
                if url and download_and_save_image(url, city_image_path):
                    return url
        if _pixabay_api_configured():
            stats["apiCalls"] += 1
            try:
                result = retry(lambda: pixabay_client.fetch_photos(q, 10))
                if result and "hits" in result and len(result["hits"]) > 0:
                    if "pixabay_photos" not in media_cache:
                        media_cache["pixabay_photos"] = {}
                    media_cache["pixabay_photos"][q] = result["hits"]
                    url = pixabay_client.get_image_url(result["hits"][0], "large")
                    if url and download_and_save_image(url, city_image_path):
                        return url
            except Exception as e:
                print(f"Warning: Pixabay fetch for '{q}': {e}")
        if unsplash_client:
            stats["apiCalls"] += 1
            try:
                result = retry(lambda: unsplash_client.fetch_photos(q, 10))
                if result and "results" in result and len(result["results"]) > 0:
                    if "unsplash_photos" not in media_cache:
                        media_cache["unsplash_photos"] = {}
                    media_cache["unsplash_photos"][q] = result["results"]
                    url = unsplash_client.get_image_url(result["results"][0], "large")
                    if url and download_and_save_image(url, city_image_path):
                        return url
            except Exception as e:
                print(f"Warning: Unsplash fetch for '{q}': {e}")
        return None

    for q in city_queries:
        if _pexels_api_configured() or _pixabay_api_configured():
            print(f"Fetching image for {city_name} (query: {q})...")
        if try_providers_for_query(q):
            return f"{asset_prefix}{web_path}/{city_slug}.jpg"

    fallback_image = la["cityFallbackImage"]
    fallback_path = la["imagesDir"] / fallback_image
    if fallback_path.exists():
        return f"{asset_prefix}{web_path}/{fallback_image}"
    print(f"Warning: No image available for {city_name}, using fallback")
    return f"{asset_prefix}{web_path}/{fallback_image}"


def name_to_slug(name: str) -> str:
    """Convert name to URL-safe slug"""
    return name.lower().replace(" ", "-")

def title_to_slug(title: str) -> str:
    """Convert blog post title to URL-safe slug"""
    import re
    # Convert to lowercase and replace spaces with hyphens
    slug = title.lower().replace(" ", "-")
    # Remove special characters except hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug


def depth_from_public_path(output_path: Path) -> int:
    """Number of directory levels from the page file up to public/. Computed from path so any page type gets correct asset depth without hardcoding."""
    try:
        rel = output_path.relative_to(Path("public"))
    except ValueError:
        return 0
    parts = rel.parts
    # depth = dirs above the file (e.g. index.html -> 0, brooklyn/index.html -> 1)
    return max(0, len(parts) - 1)


def get_asset_path(depth: Optional[int] = None) -> str:
    """Asset path prefix. depth = directory levels from page to public/ (use depth_from_public_path). depth 0 -> ''; depth >= 1 -> '../' * depth."""
    if depth is not None and depth > 0:
        return "../" * depth
    if depth == 0:
        return ""
    return ASSET_PREFIX


def get_base_path_segment() -> str:
    """Get the path segment from BASE_PATH (e.g., 'nyc/soccer' from '/nyc/soccer', '' from '/')"""
    # Remove leading/trailing slashes and return the path segment; empty for root
    return BASE_PATH.strip('/')


def get_home_link(depth: Optional[int] = None) -> str:
    """Relative path to site root (hub) for nav logo/Home. Works from any base path."""
    if depth == 0:
        return "./"
    if depth is not None and depth > 0:
        return "../" * depth
    return BASE_PATH_LINKS


def replace_asset_paths(html_content: str, depth: Optional[int] = None) -> str:
    """
    Replace asset and link placeholders so paths work at any page depth and with file://.
    depth = directory levels from page to public/ (from depth_from_public_path).
    When depth is set, {{ASSET_PATH}} and {{BASE_PATH_LINKS}} become relative (e.g. "" or "../").
    """
    link_prefix = get_asset_path(depth) if depth is not None else BASE_PATH_LINKS
    html_content = html_content.replace("{{ASSET_PATH}}", get_asset_path(depth))
    html_content = html_content.replace("{{BASE_PATH}}", BASE_PATH)
    html_content = html_content.replace("{{BASE_PATH_LINKS}}", link_prefix)
    html_content = html_content.replace("{{HOME_LINK}}", get_home_link(depth))
    return html_content


def generate_city_options(cities: List[Dict], selected_city: Optional[str] = None) -> str:
    """Generate city options for form"""
    options = []
    for city in cities:
        selected = ' selected' if city["slug"] == selected_city else ''
        options.append(f'                        <option value="{city["slug"]}"{selected}>{city["name"]}</option>')
    return "\n".join(options)


def apply_template_variables(text: str, context: Dict[str, str]) -> str:
    """Apply template variable substitution to a string"""
    if not text:
        return ""
    result = text
    for key, value in context.items():
        placeholder = f"{{{key}}}"
        result = result.replace(placeholder, value)
    return result

def generate_hero_bullets(bullets: List[str], context: Optional[Dict[str, str]] = None) -> str:
    """Generate HTML for hero section bullet points with optional context substitution"""
    if not bullets:
        return ""
    items = []
    for bullet in bullets:
        bullet_text = apply_template_variables(bullet, context or {})
        items.append(f'<li>{html.escape(bullet_text)}</li>')
    return '\n                    '.join(items)

def generate_single_hero_section(hero_config: Dict, context: Optional[Dict[str, str]] = None) -> str:
    """Generate single hero section HTML (no tabs)"""
    context = context or {}
    title = apply_template_variables(hero_config.get("title", ""), context)
    subtitle = apply_template_variables(hero_config.get("subtitle", ""), context)
    bullets = hero_config.get("bullets", [])
    cta = apply_template_variables(hero_config.get("cta", ""), context)
    microcopy = apply_template_variables(hero_config.get("microcopy", ""), context)
    
    bullets_html = generate_hero_bullets(bullets, context)
    
    return f'''<h1 class="hero__title">{html.escape(title)}</h1>
            <p class="hero__subtitle">{html.escape(subtitle)}</p>
            <ul class="hero__bullets">
                {bullets_html}
            </ul>
            <button class="hero__cta btn btn--primary btn--large" data-form-trigger>
                {html.escape(cta)}
            </button>
            <p class="hero__microcopy">{html.escape(microcopy)}</p>'''

def generate_dual_hero_section(players_config: Dict, organisers_config: Dict) -> str:
    """Generate dual hero section HTML with tabs"""
    players_bullets_html = generate_hero_bullets(players_config.get("bullets", []))
    organisers_bullets_html = generate_hero_bullets(organisers_config.get("bullets", []))
    
    return f'''<!-- Hero Tabs -->
            <div class="hero__tabs" data-hero-tabs>
                <button class="hero__tab hero__tab--active" data-hero-tab="players" aria-selected="true">
                    Players
                </button>
                <button class="hero__tab" data-hero-tab="organisers" aria-selected="false">
                    Organisers
                </button>
            </div>

            <!-- Players Hero Content -->
            <div class="hero__panel hero__panel--active" data-hero-panel="players">
                <h1 class="hero__title">{html.escape(players_config.get("title", ""))}</h1>
                <p class="hero__subtitle">{html.escape(players_config.get("subtitle", ""))}</p>
                <ul class="hero__bullets">
                    {players_bullets_html}
                </ul>
                <button class="hero__cta btn btn--primary btn--large" data-form-trigger data-hero-cta="players">
                    {html.escape(players_config.get("cta", ""))}
                </button>
                <p class="hero__microcopy">{html.escape(players_config.get("microcopy", ""))}</p>
            </div>

            <!-- Organisers Hero Content -->
            <div class="hero__panel" data-hero-panel="organisers">
                <h1 class="hero__title">{html.escape(organisers_config.get("title", ""))}</h1>
                <p class="hero__subtitle">{html.escape(organisers_config.get("subtitle", ""))}</p>
                <ul class="hero__bullets">
                    {organisers_bullets_html}
                </ul>
                <button class="hero__cta btn btn--primary btn--large" data-form-trigger data-hero-cta="organisers">
                    {html.escape(organisers_config.get("cta", ""))}
                </button>
                <p class="hero__microcopy">{html.escape(organisers_config.get("microcopy", ""))}</p>
            </div>'''

def generate_hero_section_content(page_type: str, context: Optional[Dict[str, str]] = None, city: Optional[Dict] = None) -> str:
    """
    Generate hero section content based on page type.
    
    Args:
        page_type: "hub", "city", or "area"
        context: Dictionary with variables like city_name, area_name for template substitution
        city: City config dict (for city-specific overrides)
    
    Returns:
        HTML string for hero section
    """
    context = context or {}
    hero_messaging = SITE_CONFIG.get("messaging", {}).get("heroMessaging", {})
    
    if page_type == "hub":
        hub_config = hero_messaging.get("hub", {})
        if hub_config.get("useTabs", True):
            players_config = hub_config.get("players", {})
            organisers_config = hub_config.get("organisers", {})
            return generate_dual_hero_section(players_config, organisers_config)
        else:
            template_config = hub_config.get("template", {})
            return generate_single_hero_section(template_config, context)
    
    elif page_type == "city":
        city_config = hero_messaging.get("city", {})
        
        # Check for city-specific override
        if city and city.get("heroMessaging"):
            override_config = city["heroMessaging"]
            # Merge override with template (override takes precedence)
            template_config = city_config.get("template", {}).copy()
            template_config.update(override_config)
            return generate_single_hero_section(template_config, context)
        
        # Check for legacy copyVariants support (backward compatibility)
        if city and city.get("copyVariants"):
            copy_variant = city["copyVariants"][0] if city["copyVariants"] else {}
            legacy_config = {
                "title": copy_variant.get("heroTitle", f"Find pickup soccer in {context.get('city_name', '')}"),
                "subtitle": copy_variant.get("heroSubtitle", ""),
                "bullets": city_config.get("template", {}).get("bullets", []),
                "cta": city_config.get("template", {}).get("cta", "Find Games Near Me"),
                "microcopy": city_config.get("template", {}).get("microcopy", "")
            }
            return generate_single_hero_section(legacy_config, context)
        
        # Use template
        template_config = city_config.get("template", {})
        return generate_single_hero_section(template_config, context)
    
    elif page_type == "area":
        area_config = hero_messaging.get("area", {})
        template_config = area_config.get("template", {})
        return generate_single_hero_section(template_config, context)
    
    # Fallback
    return f'<h1 class="hero__title">{SITE_CONFIG["brand"]["siteName"]}</h1>'

def generate_answer_steps(steps: List[str], with_images: bool = False) -> str:
    """
    Generate answer steps HTML with images from Pexels/Pixabay.
    Scalable: Dynamically fetches images for each step.
    """
    if with_images:
        result = []
        # Search queries for step images (from config with fallback)
        step_image_queries = SPORT_CONFIG.get("images", {}).get("answerSteps", {}).get("queries", [])
        if not step_image_queries:
            # Fallback to default queries if config is missing
            step_image_queries = [
                "soccer sign up", "soccer registration", "soccer community",
                "soccer notification", "soccer alert", "soccer game",
                "soccer players", "5v5 soccer", "soccer match",
                "soccer schedule", "soccer calendar", "soccer game",
                "pickup soccer", "soccer players", "casual soccer",
                "soccer organizer", "soccer community", "soccer group",
                "soccer community", "soccer team", "soccer players"
            ]
        
        for i, step in enumerate(steps):
            # Generate search query from step text or use predefined
            step_lower = step.lower()
            if "sign up" in step_lower or "join" in step_lower:
                query = "soccer sign up community"
            elif "notified" in step_lower or "notify" in step_lower:
                query = "soccer notification alert"
            elif "browse" in step_lower or "games" in step_lower:
                query = "soccer games 5v5"
            elif "schedule" in step_lower or "ability" in step_lower:
                query = "soccer schedule match"
            elif "show up" in step_lower or "play" in step_lower:
                query = "pickup soccer players"
            elif "organise" in step_lower or "organize" in step_lower:
                query = "soccer organizer community"
            elif "community" in step_lower or "friends" in step_lower:
                query = "soccer community team"
            else:
                # Use predefined query or generate from step
                query = step_image_queries[i % len(step_image_queries)]
            
            # Priority 1: Use local football images as default (scalable, efficient)
            image_url = get_local_football_image_url(seed=f"{step}_{i}")
            
            # Priority 2: Fallback to API images (config-driven provider order: Pexels, Pixabay, Unsplash)
            if not image_url:
                try:
                    photo, provider = get_random_photo_with_provider(query)
                    if photo and provider:
                        image_url = get_image_url_for_photo(photo, provider, "large")
                    if not image_url:
                        for prov in _get_image_provider_order():
                            if prov == "pexels" and _pexels_api_configured():
                                stats["apiCalls"] += 1
                                res = retry(lambda: pexels_client.fetch_photos(query, 5))
                                if res and "photos" in res and len(res["photos"]) > 0:
                                    if query not in media_cache["photos"]:
                                        media_cache["photos"][query] = []
                                    media_cache["photos"][query].extend(res["photos"])
                                    image_url = pexels_client.get_image_url(random.choice(res["photos"]), "large")
                                    break
                            elif prov == "pixabay" and _pixabay_api_configured():
                                stats["apiCalls"] += 1
                                try:
                                    res = retry(lambda: pixabay_client.fetch_photos(query, 5))
                                    if res and "hits" in res and len(res["hits"]) > 0:
                                        if "pixabay_photos" not in media_cache:
                                            media_cache["pixabay_photos"] = {}
                                        if query not in media_cache["pixabay_photos"]:
                                            media_cache["pixabay_photos"][query] = []
                                        media_cache["pixabay_photos"][query].extend(res["hits"])
                                        image_url = pixabay_client.get_image_url(random.choice(res["hits"]), "large")
                                        break
                                except Exception:
                                    continue
                            elif prov == "unsplash" and unsplash_client:
                                stats["apiCalls"] += 1
                                try:
                                    res = retry(lambda: unsplash_client.fetch_photos(query, 5))
                                    if res and "results" in res and len(res["results"]) > 0:
                                        if "unsplash_photos" not in media_cache:
                                            media_cache["unsplash_photos"] = {}
                                        if query not in media_cache["unsplash_photos"]:
                                            media_cache["unsplash_photos"][query] = []
                                        media_cache["unsplash_photos"][query].extend(res["results"])
                                        image_url = unsplash_client.get_image_url(random.choice(res["results"]), "large")
                                        break
                                except Exception:
                                    continue
                except Exception as e:
                    print(f"    Warning: Could not fetch image for step {i+1} ({query}): {e}")
            
            # Use relative path placeholder for local assets so they work from any page depth / file://
            if image_url:
                ap = get_asset_path()
                if ap and image_url.startswith(ap) and not image_url.startswith("http"):
                    image_url = "{{ASSET_PATH}}" + image_url[len(ap):]
            # Use image URL if available
            img_tag = f'<img src="{image_url}" alt="{html.escape(step)}" loading="lazy">' if image_url else f'<div class="answer-block__step-image-placeholder"></div>'
            
            result.append(f'''                    <li>
                        <div class="answer-block__step-content">
                            <div class="answer-block__step-text">
                                <p>{step}</p>
                            </div>
                            <div class="answer-block__step-image">
                                {img_tag}
                            </div>
                        </div>
                    </li>''')
        return "\n".join(result)
    else:
        return "\n".join([f'                    <li>{step}</li>' for step in steps])


def generate_faqs(faqs: List[Dict], city_name: str) -> str:
    """Generate FAQ HTML"""
    result = []
    for faq in faqs:
        question = faq["question"].replace("{city}", city_name)
        answer = faq["answer"].replace("{city}", city_name)
        result.append(f'''
                    <div class="faq-item" data-expanded="false">
                        <h3 class="faq-item__question">{html.escape(question)}</h3>
                        <div class="faq-item__answer">{html.escape(answer)}</div>
                    </div>''')
    return "\n".join(result)


def area_page_exists(city_slug: str, area_slug: str) -> bool:
    """Check if area page exists (with caching)"""
    cache_key = f"{city_slug}/{area_slug}"
    if cache_key in area_page_cache:
        return area_page_cache[cache_key]
    
    path_segment = get_base_path_segment()
    area_path = Path("public") / path_segment / city_slug / area_slug / "index.html"
    exists = area_path.exists()
    area_page_cache[cache_key] = exists
    return exists


def generate_area_links(city: Dict, all_cities: List[Dict], area_pages_exist: Optional[Dict[str, bool]] = None) -> str:
    """Generate area links HTML (uses pre-computed existence map for performance)"""
    if not city.get("areas"):
        return ""
    
    sections = (SITE_CONFIG.get("messaging") or {}).get("sections") or {}
    area_link_tpl = sections.get("areaLinkTitle", "Soccer in {area_name}, {city_name}")
    def link_text(area_name: str) -> str:
        return area_link_tpl.replace("{area_name}", area_name).replace("{city_name}", city["name"])
    # Use pre-computed map if provided (performance optimization)
    if area_pages_exist is not None:
        area_links = []
        for area_name in city["areas"]:
            area_slug = name_to_slug(area_name)
            cache_key = f"{city['slug']}/{area_slug}"
            if area_pages_exist.get(cache_key, False):
                area_links.append(
                    f'                    <a href="{{{{BASE_PATH_LINKS}}}}{city["slug"]}/{area_slug}/" class="city-link">{html.escape(link_text(area_name))}</a>'
                )
        return "\n".join(area_links)
    
    # Fallback to file system checks (slower, but works if map not provided)
    with ThreadPoolExecutor(max_workers=CONFIG["MAX_CONCURRENT_PAGES"]) as executor:
        area_checks = list(executor.map(
            lambda area_name: {
                "areaName": area_name,
                "areaSlug": name_to_slug(area_name),
                "exists": area_page_exists(city["slug"], name_to_slug(area_name))
            },
            city["areas"]
        ))
    
    area_links = [
        f'                    <a href="{{{{BASE_PATH_LINKS}}}}{city["slug"]}/{check["areaSlug"]}/" class="city-link">{html.escape(link_text(check["areaName"]))}</a>'
        for check in area_checks if check["exists"]
    ]
    
    # Log warnings for missing areas
    for check in area_checks:
        if not check["exists"]:
            print(f"Warning: Area page not found for {city['name']} - {check['areaName']} ({check['areaSlug']})")
    
    return "\n".join(area_links)


def generate_city_links(cities: List[Dict], current_city_slug: Optional[str] = None, with_images: bool = False) -> str:
    """Generate city links HTML with descriptive anchor text (SEO/internal links)."""
    sections = (SITE_CONFIG.get("messaging") or {}).get("sections") or {}
    link_title_tpl = sections.get("cityLinkTitle", "Pickup soccer in {city_name}")
    result = []
    for city in cities:
        if city["slug"] == current_city_slug:
            continue
        link_text = link_title_tpl.replace("{city_name}", city["name"])
        url = f"{{{{BASE_PATH_LINKS}}}}{city['slug']}/"
        if with_images:
            image_url = _local_asset_url_for_template(get_city_image_url(city["slug"], city["name"]))
            result.append(f'''
                    <a href="{url}" class="city-link">
                        <div class="city-link__image">
                            <img src="{image_url}" alt="{html.escape(link_text)}" loading="lazy">
                        </div>
                        <div class="city-link__text">{html.escape(link_text)}</div>
                    </a>''')
        else:
            result.append(f'''
                    <a href="{url}" class="city-link">{html.escape(link_text)}</a>''')
    return "\n".join(result)


def generate_city_links_section(city_links_html: str, title: str = "Find Soccer in Other Areas") -> str:
    """Generate city links section HTML"""
    if not city_links_html:
        return ""
    
    return f'''
        <!-- City Links -->
        <section class="city-links" id="areas">
            <div class="container container--content">
                <h2 class="city-links__title">{title}</h2>
                <div class="city-links__grid">
                    {city_links_html}
                </div>
            </div>
        </section>'''


def generate_background_style(poster_url: str) -> str:
    """
    Generate inline background-image style for hero video container.
    This ensures the image shows even if video fails to load.
    """
    if not poster_url:
        return ""
    
    # Escape single quotes in URL for HTML attribute
    escaped_url = poster_url.replace("'", "&#39;")
    return f' style="background-image: url(\'{escaped_url}\'); background-size: cover; background-position: center; background-repeat: no-repeat;"'


def generate_video_sources(pexels_video_url: str, page_slug: str = "") -> str:
    """Generate video sources HTML. Selects ONE local video per page using hash-based selection
    for variety across pages while keeping each page deterministic.
    Uses {{ASSET_PATH}} placeholder so replace_asset_paths() can fix paths per page depth."""
    local_videos = get_local_hero_videos()
    la = _get_local_assets_config()
    videos_web_path = la.get("videosWebPath", "assets/videos").rstrip("/")

    video_type_by_ext = {".mp4": "video/mp4", ".webm": "video/webm"}
    sources = []

    if local_videos:
        selected_index = int(hashlib.md5((page_slug or "home").encode()).hexdigest(), 16) % len(local_videos)
        video = local_videos[selected_index]
        ext = Path(video).suffix.lower()
        mime = video_type_by_ext.get(ext, "video/mp4")
        encoded = quote(video, safe="")
        sources.append(f'                <source src="{{{{ASSET_PATH}}}}{videos_web_path}/{encoded}" type="{mime}">')

    if pexels_video_url:
        external_sources = [
            '                <!-- External video sources (fallback if local videos fail) -->',
            f'                <source src="{pexels_video_url}" type="video/mp4">'
        ]
        
        if "hd_1280_720" in pexels_video_url:
            sd_url = pexels_video_url.replace("hd_1280_720", "sd_640_360")
            external_sources.append(f'                <source src="{sd_url}" type="video/mp4">')
        
        sources.extend(external_sources)
    
    return "\n".join(sources)


def generate_navigation(is_hub_page: bool = False, city_slug: Optional[str] = None, area_slug: Optional[str] = None) -> str:
    """Generate navigation HTML"""
    if is_hub_page:
        return '''                <a href="#areas" class="nav__link">Areas</a>
                <a href="#blog" class="nav__link">Blog</a>
                <a href="#about" class="nav__link">About</a>'''
    elif area_slug:
        # Area page: Cities link goes to area links section on the city page
        return f'''                <a href="{{{{BASE_PATH_LINKS}}}}{city_slug}/#area-links" class="nav__link">Areas</a>
                <a href="#blog" class="nav__link">Blog</a>
                <a href="{{{{BASE_PATH_LINKS}}}}#about" class="nav__link">About</a>'''
    elif city_slug:
        return f'''                <a href="#blog" class="nav__link">Blog</a>
                <a href="{{{{BASE_PATH_LINKS}}}}#about" class="nav__link">About</a>'''
    else:
        return f'''                <a href="{{{{BASE_PATH_LINKS}}}}#areas" class="nav__link">Areas</a>
                <a href="{{{{BASE_PATH_LINKS}}}}#blog" class="nav__link">Blog</a>
                <a href="{{{{BASE_PATH_LINKS}}}}#about" class="nav__link">About</a>'''


def generate_nav_brand() -> str:
    """Generate navigation brand HTML"""
    return '''            <div class="nav__brand">
                <a href="{{HOME_LINK}}" class="nav__logo">{{SITE_NAME}}</a>
                <p class="nav__powered-by">Powered by {{POWERED_BY}}</p>
            </div>'''


def generate_footer_network_links() -> str:
    """Build footer GameOn Active Network links HTML from config."""
    footer_cfg = SITE_CONFIG.get("footer", {})
    links = footer_cfg.get("networkLinks", [])
    if not links:
        return ""
    title = footer_cfg.get("networkTitle", "GameOn Active Network")
    items = []
    for item in links:
        label = item.get("label", "").strip()
        url = (item.get("url") or "").strip()
        if not url:
            url = "#"
        if not label:
            label = url
        if not url.startswith("http"):
            url = "https://" + url
        items.append(f'<a href="{html.escape(url)}" class="footer__network-link" rel="noopener noreferrer" target="_blank">{html.escape(label)}</a>')
    return f'<p class="footer__network-title">{html.escape(title)}</p><div class="footer__network-links">{" ".join(items)}</div>'


def generate_blog_posts(blog_type: str, location_context: Dict[str, str] = None) -> List[Dict]:
    """Generate blog posts based on type (country, city, area)"""
    if blog_type not in SPORT_CONFIG["blogPosts"]:
        return []
    
    # Import content generator
    try:
        from api.utils.blog_content_generator import BlogContentGenerator
        content_generator = BlogContentGenerator(SPORT_CONFIG)
    except ImportError:
        print("Warning: Blog content generator not available. Posts will use excerpts only.")
        content_generator = None
    
    # Use deep copy to ensure each city gets its own copy of blog posts
    # This prevents modifying the original templates when replacing placeholders
    posts = copy.deepcopy(SPORT_CONFIG["blogPosts"][blog_type])
    context = location_context or {}
    
    # Add slug placeholders to context for city and area posts
    if blog_type == "city" and "city" in context:
        city_name = context["city"]
        # Find city slug from config
        for city in SPORT_CONFIG.get("cities", []):
            if city.get("name") == city_name:
                context["city_slug"] = city.get("slug", name_to_slug(city_name))
                break
        else:
            context["city_slug"] = name_to_slug(city_name)
    
    if blog_type == "area":
        if "area_name" in context:
            context["area_slug"] = name_to_slug(context["area_name"])
        if "city_name" in context:
            city_name = context["city_name"]
            # Find city slug from config
            for city in SPORT_CONFIG.get("cities", []):
                if city.get("name") == city_name:
                    context["city_slug"] = city.get("slug", name_to_slug(city_name))
                    break
            else:
                context["city_slug"] = name_to_slug(city_name)
    
    # Replace placeholders in blog posts and generate content
    valid_posts = []
    for post in posts:
        try:
            # Format will work fine even if no placeholders exist
            # It will only raise KeyError if a placeholder is in the template but missing from context
            post["title"] = post["title"].format(**context)
            post["excerpt"] = post["excerpt"].format(**context)
            
            # Generate slug if not present
            if "slug" in post:
                # Format slug with context
                try:
                    post["slug"] = post["slug"].format(**context)
                except KeyError:
                    # If slug has placeholders that aren't in context, generate from title
                    post["slug"] = title_to_slug(post["title"])
            else:
                post["slug"] = title_to_slug(post["title"])
            
            # Generate content if not present and generator is available
            if "content" not in post or not post.get("content"):
                if content_generator:
                    try:
                        generated_content = content_generator.generate_content(post, blog_type, context)
                        if generated_content and len(generated_content.strip()) > 0:
                            post["content"] = generated_content
                        else:
                            print(f"Warning: Empty content generated for '{post.get('title', 'Unknown')[:50]}'")
                            post["content"] = f"<p>{post.get('excerpt', '')}</p>"
                    except Exception as e:
                        print(f"Warning: Error generating content for '{post.get('title', 'Unknown')[:50]}': {e}")
                        import traceback
                        traceback.print_exc()
                        post["content"] = f"<p>{post.get('excerpt', '')}</p>"
                else:
                    post["content"] = f"<p>{post.get('excerpt', '')}</p>"
            elif "content" in post:
                # Format existing content with context
                try:
                    post["content"] = post["content"].format(**context)
                except KeyError:
                    pass  # Content might not have placeholders
            
            # Add default metadata if not present
            if "date" not in post:
                # Generate dates spread over the last few months for variety
                days_ago = random.randint(1, 90)
                post["date"] = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            
            if "category" not in post:
                # Determine category from title/content
                title_lower = post["title"].lower()
                if "guide" in title_lower:
                    post["category"] = "Guide"
                elif "vs" in title_lower or "comparison" in title_lower:
                    post["category"] = "Comparison"
                elif "places" in title_lower or "venues" in title_lower:
                    post["category"] = "Venues"
                elif "culture" in title_lower:
                    post["category"] = "Culture"
                else:
                    post["category"] = "News"
            
            if "author" not in post:
                post["author"] = f"{SITE_CONFIG['brand']['siteName']} Team"
            
            valid_posts.append(post)
        except KeyError as e:
            # If a required placeholder is missing from context, skip this post
            # This ensures city-specific posts only show when properly configured
            # (e.g., a post with {city} won't show on country pages)
            continue
        except Exception as e:
            # Handle any other formatting errors gracefully
            print(f"Warning: Error formatting blog post '{post.get('title', 'Unknown')[:50]}': {e}")
            continue
    
    posts = valid_posts
    
    # Sort by date (newest first) - handle posts without date field
    posts.sort(key=lambda x: x.get("date", ""), reverse=True)
    
    return posts


def generate_blog_section(blog_type: str, location_context: Dict[str, str] = None, max_posts: int = 3) -> str:
    """Generate blog section HTML"""
    posts = generate_blog_posts(blog_type, location_context)
    
    if not posts:
        return ""
    
    # Limit number of posts
    posts = posts[:max_posts]
    
    blog_items = []
    
    for post in posts:
        # Format date - handle missing date field
        post_date_str = post.get("date", "")
        if post_date_str:
            try:
                post_date = datetime.strptime(post_date_str, "%Y-%m-%d")
                formatted_date = post_date.strftime("%B %d, %Y")
            except:
                formatted_date = post_date_str
        else:
            formatted_date = datetime.now().strftime("%B %d, %Y")
        
        # Get image from config (scalable approach); use placeholder so paths work at any depth
        image_url = _local_asset_url_for_template(get_blog_image_url(post["title"]))
        
        # Generate slug for blog post URL - use slug from post if available, otherwise generate from title
        post_slug = post.get("slug") or title_to_slug(post["title"])
        post_url = f"{{{{BASE_PATH_LINKS}}}}blog/{post_slug}/"
        
        # Get optional fields with defaults
        category = post.get("category", "News")
        author = post.get("author", f"{SITE_CONFIG['brand']['siteName']} Team")
        
        blog_items.append(f'''
            <article class="blog-post">
                <a href="{post_url}" class="blog-post__link">
                    <div class="blog-post__image">
                        <img src="{image_url}" alt="{html.escape(post['title'])}" loading="lazy">
                    </div>
                    <div class="blog-post__content">
                        <div class="blog-post__meta">
                            <span class="blog-post__category">{html.escape(category)}</span>
                            <span class="blog-post__date">{formatted_date}</span>
                        </div>
                        <h3 class="blog-post__title">{html.escape(post['title'])}</h3>
                        <p class="blog-post__excerpt">{html.escape(post.get('excerpt', ''))}</p>
                        <div class="blog-post__footer">
                            <span class="blog-post__author">By {html.escape(author)}</span>
                        </div>
                    </div>
                </a>
            </article>''')
    
    return f'''
        <!-- Blog Section -->
        <section class="blog" id="blog">
            <div class="container container--content">
                <h2 class="blog__title">Latest News & Updates</h2>
                <div class="blog__grid">
                    {''.join(blog_items)}
                </div>
            </div>
        </section>'''


def generate_blog_post_page(post: Dict, template: str) -> str:
    """Generate individual blog post page"""
    import re
    
    # Format date
    post_date_str = post.get("date", "")
    if post_date_str:
        try:
            post_date = datetime.strptime(post_date_str, "%Y-%m-%d")
            formatted_date = post_date.strftime("%B %d, %Y")
            date_published = post_date.isoformat()
        except:
            formatted_date = post_date_str
            date_published = post_date_str
    else:
        # Default date if not provided
        formatted_date = datetime.now().strftime("%B %d, %Y")
        date_published = datetime.now().isoformat()
    
    # Generate slug and URL
    post_slug = title_to_slug(post["title"])
    url = f"{ROOT_URL}blog/{post_slug}/"
    
    # Get image from config (scalable approach)
    asset_prefix = get_asset_path()
    image_url = get_blog_image_url(post["title"])
    
    # Extract location from post title/content for GEO optimization
    # Check if post mentions a specific city
    location = HUB_MARKETING
    city_name = None
    area_name = None
    
    # Try to extract city name from title or content
    title_lower = post.get("title", "").lower()
    content_lower = post.get("content", "").lower() if post.get("content") else ""
    
    # Check against known cities
    for city in SPORT_CONFIG.get("cities", []):
        city_lower = city["name"].lower()
        if city_lower in title_lower or city_lower in content_lower:
            city_name = city["name"]
            location = city["name"]
            # Check for area names
            for area in city.get("areas", []):
                if area.lower() in title_lower or area.lower() in content_lower:
                    area_name = area
                    location = f"{area}, {city['name']}"
            break
    
    # Generate meta tags - ALL BLOG POSTS COMPETE FOR SAME KEYWORDS
    # Use same primary keywords as all other pages
    keywords = SEOHelper.generate_keywords_optimized(location, "blog")
    
    # Add blog-specific keywords while keeping primary keywords
    keywords.extend([
        "soccer blog", "soccer news", "soccer guide", "soccer tips",
        post.get("category", "").lower()
    ])
    
    # Add location-specific variations if applicable
    if city_name:
        keywords.extend([f"soccer {city_name}", f"soccer {city_name.lower()}"])
    if area_name:
        keywords.extend([f"soccer {area_name}", f"soccer {area_name.lower()} {city_name.lower()}"])

    # Optimize title to include primary keywords
    post_title = post['title']
    # Ensure title includes core keywords if not already present
    title_lower = post_title.lower()
    if "soccer" not in title_lower:
        post_title = f"Soccer: {post_title}"
    if "5-a-side" not in title_lower and "casual" not in title_lower:
        # Add to description instead to keep title natural
        pass
    
    # Optimize description with core keywords
    description = post.get("excerpt", post.get("content", "")[:160])
    if not description or len(description) < 120:
        description = SEOHelper.generate_meta_description_optimized(
            post_title, location, "blog", include_cta=True
        )

    blog_title = _get_seo_title("blog", post_title=post_title, fallback_title=f"{post_title} | {SITE_CONFIG['brand']['siteName']}")
    meta = SEOHelper.generate_meta_tags({
        "title": blog_title,
        "description": description,
        "canonical": url,
        "ogImage": image_url,
        "ogUrl": url,
        "keywords": keywords,
        "location": location,
        "pageType": "blog"
    })
    
    # Generate breadcrumbs
    breadcrumbs = [
        {"name": "Home", "url": f"{SITE_CONFIG['baseUrl']}/"},
        {"name": SITE_CONFIG["brand"]["siteName"], "url": f"{ROOT_URL}"},
        {"name": "Blog", "url": f"{ROOT_URL}#blog"},
        {"name": post["title"], "url": url}
    ]
    
    # Generate enhanced Article schema optimized for LLM parsing (speakable first paragraph + wordCount)
    article_schema = SEOHelper.generate_article_schema_enhanced(
        title=post["title"],
        description=post.get("excerpt", ""),
        url=url,
        image_url=image_url,
        author=post.get("author", f"{SITE_CONFIG['brand']['siteName']} Team"),
        date_published=date_published,
        date_modified=date_published,
        keywords=keywords,
        article_section=post.get("category", "News"),
        content_html_or_text=post.get("content") or post.get("excerpt") or ""
    )
    
    # Add GEO optimization schemas if location-specific
    additional_schemas = [article_schema]
    
    if city_name:
        # Find city config for coordinates
        city_config = None
        for city in SPORT_CONFIG.get("cities", []):
            if city["name"] == city_name:
                city_config = city
                break
        
        if city_config:
            coordinates = city_config.get("coordinates")
            postal_code = city_config.get("postalCode")
            
            # Add LocalBusiness schema for GEO optimization
            local_business_schema = SEOHelper.generate_local_business_schema(
                city_name, url, area_name, coordinates, postal_code
            )
            additional_schemas.append(local_business_schema)
            
            # Add Place schema for GEO optimization
            place_schema = SEOHelper.generate_place_schema(
                city_name, url, area_name, coordinates
            )
            additional_schemas.append(place_schema)
            
            # Add Service schema for better local SEO
            service_schema = SEOHelper.generate_service_schema(
                f"Soccer Community Services in {location}",
                "Soccer Community Platform",
                city_name,
                url
            )
            additional_schemas.append(service_schema)
    
    # Add AEO optimization: FAQ schema if content suggests Q&A format
    # Check if content has question-like patterns or FAQ structure
    content = post.get("content", "")
    if content and ("?" in content or "question" in content.lower() or "faq" in content.lower()):
        # Extract potential Q&A pairs from content (simple heuristic)
        # For now, we'll add a basic FAQ schema if it's a "Tips" or "Guide" category
        if post.get("category", "").lower() in ["tips", "guide", "how-to"]:
            # Create a simple FAQ schema based on the excerpt
            faq_items = [{
                "question": post["title"],
                "answer": post.get("excerpt", "")[:500]  # First 500 chars as answer
            }]
            faq_schema = SEOHelper.generate_faq_schema(faq_items, url)
            additional_schemas.append(faq_schema)
    
    blog_primary_image = _absolute_image_url(image_url)
    json_ld = SEOHelper.generate_json_ld({
        "title": post["title"],
        "description": post.get("excerpt", ""),
        "url": url,
        "dateModified": date_published,
        "breadcrumbs": breadcrumbs,
        "additionalSchemas": additional_schemas,
        "primaryImageOfPage": blog_primary_image
    })
    
    nav_brand = generate_nav_brand().replace("{{SITE_NAME}}", SITE_CONFIG["brand"]["siteName"]).replace("{{POWERED_BY}}", SITE_CONFIG["brand"]["poweredBy"])
    # Blog post pages: No Cities link needed (standalone pages)
    nav_menu = f'''                <a href="{{{{BASE_PATH_LINKS}}}}#blog" class="nav__link">Blog</a>
                <a href="{{{{BASE_PATH_LINKS}}}}#about" class="nav__link">About</a>'''
    
    # Always generate content for blog posts to ensure it's fresh and complete
    # This ensures content is generated even if it was missed during initial generation
    try:
        from api.utils.blog_content_generator import BlogContentGenerator
        content_generator = BlogContentGenerator(SPORT_CONFIG)
        
        # Determine blog type from title/content
        title_lower = post.get("title", "").lower()
        blog_type = "country"
        location_context = {}
        
        # Check for city in title
        for city in SPORT_CONFIG.get("cities", []):
            if city["name"].lower() in title_lower:
                # Check if it's an area post (area name also in title)
                is_area = False
                for area in city.get("areas", []):
                    if area.lower() in title_lower:
                        blog_type = "area"
                        location_context = {"area_name": area, "city_name": city["name"]}
                        is_area = True
                        break
                
                if not is_area:
                    blog_type = "city"
                    location_context = {"city": city["name"]}
                break
        
        # Generate content
        generated_content = content_generator.generate_content(post, blog_type, location_context)
        if generated_content and len(generated_content.strip()) > 200:
            content = generated_content
        else:
            # Fallback to excerpt if generation fails
            content = f"<p>{post.get('excerpt', '')}</p>"
    except Exception as e:
        # Fallback to excerpt if generation fails
        content = f"<p>{post.get('excerpt', '')}</p>"
    
    replacements = {
        "META_TITLE": meta["title"],
        "META_DESCRIPTION": meta["description"],
        "META_CANONICAL": meta["canonical"],
        "META_ROBOTS": meta.get("robots", ""),
        "META_AUTHOR": meta.get("author", ""),
        "META_LANGUAGE": meta.get("language", ""),
        "META_KEYWORDS": meta.get("keywords", ""),
        "META_GEO": meta.get("geo", ""),
        "META_HREFLANG": meta.get("hreflang", ""),
        "META_THEME_COLOR": meta.get("themeColor", ""),
        "META_APPLE_MOBILE_WEB_APP": meta.get("appleMobileWebApp", ""),
        "META_FORMAT_DETECTION": meta.get("formatDetection", ""),
        "META_REFERRER": meta.get("referrer", ""),
        "OG_TAGS": meta["ogTags"],
        "TWITTER_TAGS": meta["twitterTags"],
        "JSON_LD": json_ld,
        "NAV_BRAND": nav_brand,
        "NAV_MENU": nav_menu,
        "NAV_CTA_TEXT": SITE_CONFIG["messaging"]["cta"].get("nav", "Get local game invites"),
        "BLOG_POST_TITLE": post["title"],
        "BLOG_POST_DATE": formatted_date,
        "BLOG_POST_CATEGORY": post.get("category", ""),
        "BLOG_POST_AUTHOR": post.get("author", f"{SITE_CONFIG['brand']['siteName']} Team"),
        "BLOG_POST_CONTENT": content,
        "BLOG_POST_IMAGE": _local_asset_url_for_template(image_url),
        "BLOG_POST_IMAGE_WIDTH": str((SITE_CONFIG.get("meta") or {}).get("ogImageWidth", 1200)),
        "BLOG_POST_IMAGE_HEIGHT": str((SITE_CONFIG.get("meta") or {}).get("ogImageHeight", 630)),
        "SITE_NAME": SITE_CONFIG["brand"]["siteName"],
        "HUB_MARKETING_NAME": HUB_MARKETING,
        "CITY_NAME": location,
        "POWERED_BY": SITE_CONFIG["brand"]["poweredBy"],
        "IN_SHORT_SECTION": "",
        "KEY_TAKEAWAYS_SECTION": "",
        "LEADS_ENDPOINT": _get_leads_endpoint(),
        "TRACKING_CONFIG_JSON": json.dumps(_get_tracking_config()),
        "FOOTER_NETWORK_LINKS": generate_footer_network_links(),
        "LAST_UPDATED": datetime.now().strftime("%d/%m/%Y")
    }
    # Blog uses hub-level region for organizer copy (same as hub page)
    blog_org_label, blog_org_help = _get_organizer_form_copy(replacements.get("CITY_NAME", HUB_MARKETING))
    replacements["ORGANIZER_CHECKBOX_LABEL"] = blog_org_label
    replacements["ORGANIZER_CHECKBOX_HELP"] = blog_org_help

    # Use a simplified template for blog posts
    # Generate blog-specific hero section
    blog_hero_content = f'''<h1 class="hero__title">{{BLOG_POST_TITLE}}</h1>'''
    blog_template = template.replace("{{HERO_SECTION_CONTENT}}", blog_hero_content)
    blog_template = blog_template.replace("{{HERO_VIDEO_SOURCES}}", "")
    blog_template = blog_template.replace("{{HERO_POSTER}}", "")
    blog_template = blog_template.replace("{{CTA_TEXT}}", "")
    blog_template = blog_template.replace("{{CITY_NAME}}", "")
    blog_template = blog_template.replace("{{CITY_OPTIONS}}", "")
    blog_template = blog_template.replace("{{ANSWER_STEPS}}", "")
    blog_template = blog_template.replace("{{QUICK_FACTS_BEST_TIMES}}", "")
    blog_template = blog_template.replace("{{QUICK_FACTS_INDOOR_OUTDOOR}}", "")
    blog_template = blog_template.replace("{{QUICK_FACTS_GROUP_SIZE}}", "")
    blog_template = blog_template.replace("{{QUICK_FACTS_SKILL_LEVELS}}", "")
    blog_template = blog_template.replace("{{FAQS}}", "")
    blog_template = blog_template.replace("{{ABOUT_SECTION}}", "")
    blog_template = blog_template.replace("{{BLOG_SECTION}}", "")
    blog_template = blog_template.replace("{{AREA_LINKS_SECTION}}", "")
    blog_template = blog_template.replace("{{CITY_LINKS_BEFORE_FAQS}}", "")
    blog_template = blog_template.replace("{{CITY_LINKS_AFTER_FAQS}}", "")
    
    # Add blog post content section (with double braces for replacement)
    blog_content_section = f'''
        <!-- Blog Post Content -->
        <article class="blog-post-page">
            <div class="container container--content">
                <div class="blog-post-page__header">
                    <div class="blog-post-page__meta">
                        <span class="blog-post-page__category">{{{{BLOG_POST_CATEGORY}}}}</span>
                        <span class="blog-post-page__date">{{{{BLOG_POST_DATE}}}}</span>
                    </div>
                    <h1 class="blog-post-page__title">{{{{BLOG_POST_TITLE}}}}</h1>
                    <div class="blog-post-page__author">By {{{{BLOG_POST_AUTHOR}}}}</div>
                </div>
                <div class="blog-post-page__image">
                    <img src="{{{{BLOG_POST_IMAGE}}}}" alt="{{{{BLOG_POST_TITLE}}}}" width="{{{{BLOG_POST_IMAGE_WIDTH}}}}" height="{{{{BLOG_POST_IMAGE_HEIGHT}}}}" loading="eager">
                </div>
                <div class="blog-post-page__content">
                    {{{{BLOG_POST_CONTENT}}}}
                </div>
                <div class="blog-post-page__footer">
                    <a href="{{{{BASE_PATH_LINKS}}}}#blog" class="blog-post-page__back-link" data-blog-back-link>← Back to Blog</a>
                </div>
            </div>
        </article>'''
    
    # Replace the main content section with blog post content
    # Remove the hero section and other sections for blog posts
    blog_template = blog_template.replace("<!-- Hero Section", "<!-- Hero Section (hidden for blog posts)")
    blog_template = blog_template.replace('<section class="hero">', '<section class="hero" style="display: none;">')
    blog_template = blog_template.replace("<!-- Main Content -->", f"<!-- Main Content -->{blog_content_section}")
    blog_template = blog_template.replace('<main class="main">', '<main class="main" style="display: none;">')
    
    html_content = apply_common_replacements(blog_template, replacements)
    return html_content


def generate_about_section(depth: Optional[int] = None) -> str:
    """Generate about section HTML"""
    site_name = SITE_CONFIG['brand']['siteName']
    value_prop = SITE_CONFIG['brand']['valueProposition']
    about_image_url = _local_asset_url_for_template(get_about_image_url())
    return f'''        <!-- About Section -->
        <section class="about" id="about">
            <div class="container container--content">
                <h2 class="about__title">About {site_name}</h2>
                <div class="about__content">
                    <div class="about__text">
                        <p class="about__description">{value_prop}</p>
                        <p class="about__description">Our mission is to make soccer more accessible and help build lasting connections through the sport. Whether you're a beginner looking to learn or an experienced player seeking competitive games, {site_name} is your gateway to the {HUB_MARKETING} soccer community.</p>
                    </div>
                    <div class="about__image">
                        <img src="{about_image_url}" alt="Soccer community" loading="lazy">
                    </div>
                </div>
                <div class="about__features">
                    <div class="about__feature">
                        <h3 class="about__feature-title">Community First</h3>
                        <p class="about__feature-text">Built by players, for players. We prioritize community needs and feedback.</p>
                    </div>
                    <div class="about__feature">
                        <h3 class="about__feature-title">Easy to Use</h3>
                        <p class="about__feature-text">Simple sign-up process and intuitive interface to find games quickly.</p>
                    </div>
                    <div class="about__feature">
                        <h3 class="about__feature-title">All Skill Levels</h3>
                        <p class="about__feature-text">From casual games to competitive matches, there's something for everyone.</p>
                    </div>
                </div>
            </div>
        </section>'''


def apply_common_replacements(html_content: str, replacements: Dict[str, str]) -> str:
    """Apply common template replacements (optimized single-pass)"""
    # Single-pass replacement using regex for better performance
    import re
    # Build pattern for all replacements at once
    pattern = re.compile('|'.join(re.escape(f"{{{{{key}}}}}") for key in replacements.keys()))
    
    def replacer(match):
        # Extract the key from the matched string
        matched = match.group(0)
        # Remove the braces to get the key
        key = matched[2:-2]  # Remove {{ and }}
        return replacements.get(key, matched)
    
    return pattern.sub(replacer, html_content)


def fetch_pexels_media_parallel():
    """
    Fetch media in parallel: Pexels/Pixabay for video; Pexels, Pixabay, Unsplash for poster (config-driven).
    """
    queries = _get_media_queries()
    hero_video = queries.get("heroVideo", [])
    hero_poster = queries.get("heroPoster", [])
    pex = _pexels_api_configured()
    pix = _pixabay_api_configured()
    if not pex and not pix and not unsplash_client:
        print("Skipping remote hero media fetch (no Pexels, Pixabay, or Unsplash API keys). Using local assets.")
        return
    print("Fetching media from Pexels, Pixabay" + (", Unsplash" if unsplash_client else "") + "...")

    video_queries = [
        q for q in hero_video
        if q not in media_cache["videos"] and q not in media_cache["pixabay_videos"]
    ]
    poster_queries = [
        q for q in hero_poster
        if q not in media_cache["photos"] and q not in media_cache["pixabay_photos"]
        and q not in media_cache.get("unsplash_photos", {})
    ]
    if video_queries and not pex and not pix:
        video_queries = []

    def fetch_video(query):
        if pex:
            stats["apiCalls"] += 1
            result = retry(lambda: pexels_client.fetch_videos(query, 20))
            if result and "videos" in result and len(result["videos"]) > 0:
                media_cache["videos"][query] = result["videos"]
                return
        if pix:
            if pex:
                print(f"Pexels returned no results for '{query}', trying Pixabay...")
            stats["apiCalls"] += 1
            try:
                result = retry(lambda: pixabay_client.fetch_videos(query, 20))
                if result and "hits" in result and len(result["hits"]) > 0:
                    if "pixabay_videos" not in media_cache:
                        media_cache["pixabay_videos"] = {}
                    media_cache["pixabay_videos"][query] = result["hits"]
            except Exception as e:
                print(f"Warning: Could not fetch video '{query}' from Pixabay: {e}")
    
    def fetch_poster(query):
        if pex:
            stats["apiCalls"] += 1
            result = retry(lambda: pexels_client.fetch_photos(query, 20))
            if result and "photos" in result and len(result["photos"]) > 0:
                media_cache["photos"][query] = result["photos"]
                return
        if pix:
            if pex:
                print(f"Pexels returned no results for '{query}', trying Pixabay...")
            stats["apiCalls"] += 1
            try:
                result = retry(lambda: pixabay_client.fetch_photos(query, 20))
                if result and "hits" in result and len(result["hits"]) > 0:
                    if "pixabay_photos" not in media_cache:
                        media_cache["pixabay_photos"] = {}
                    media_cache["pixabay_photos"][query] = result["hits"]
                    return
            except Exception as e:
                print(f"Warning: Could not fetch photo '{query}' from Pixabay: {e}")
        if unsplash_client:
            print(f"Trying Unsplash for '{query}'...")
            stats["apiCalls"] += 1
            try:
                result = retry(lambda: unsplash_client.fetch_photos(query, 20))
                if result and "results" in result and len(result["results"]) > 0:
                    if "unsplash_photos" not in media_cache:
                        media_cache["unsplash_photos"] = {}
                    media_cache["unsplash_photos"][query] = result["results"]
            except Exception as e:
                print(f"Warning: Could not fetch photo '{query}' from Unsplash: {e}")
    
    # Execute in parallel with rate limiting
    tasks = []
    for q in video_queries:
        tasks.append((fetch_video, q))
    for q in poster_queries:
        tasks.append((fetch_poster, q))
    
    with ThreadPoolExecutor(max_workers=CONFIG["MAX_CONCURRENT_API_CALLS"]) as executor:
        futures = [executor.submit(func, query) for func, query in tasks]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error in media fetch: {e}")
    
    print(f"Media fetched and cached. ({stats['apiCalls']} API calls)")


def fetch_city_images_parallel(cities: List[Dict]):
    """
    Pre-fetch city images from Pexels and Pixabay in parallel with rate limiting.
    
    Rate Limiting Strategy:
    - Uses MAX_CONCURRENT_API_CALLS (2) to limit concurrent requests
    - PexelsClient/PixabayClient handle per-request delays (API_REQUEST_DELAY)
    - Handles 429 errors with exponential backoff (RETRY_DELAY_429)
    - Respects API limits:
      - Pexels: 200 requests/hour, 20,000/month
      - Pixabay: 100 requests/60 seconds
    
    Note: For large city lists (60+ cities), this may take time due to rate limits.
    Consider running in batches or using cached images when possible.
    """
    if not _pexels_api_configured() and not _pixabay_api_configured():
        print("Skipping remote city image pre-fetch (no Pexels or Pixabay API key). Using local/cached images.")
        return

    print("Pre-fetching city images from Pexels and Pixabay...")
    la = _get_local_assets_config()

    def fetch_city_image(city):
        city_image_path = la["imagesDir"] / f"{city['slug']}.jpg"
        
        # Skip if already exists
        if city_image_path.exists():
            return
        
        city_query = f"{city['name']} city"
        
        # Check Pexels cache first
        if city_query in media_cache.get("photos", {}):
            photos = media_cache["photos"][city_query]
            if photos:
                photo = photos[0]
                image_url = pexels_client.get_image_url(photo, "large")
                if image_url:
                    if download_and_save_image(image_url, city_image_path):
                        print(f"✓ Pre-fetched {city['name']} image from Pexels cache")
                    return
        
        # Check Pixabay cache
        if city_query in media_cache.get("pixabay_photos", {}):
            photos = media_cache["pixabay_photos"][city_query]
            if photos:
                photo = photos[0]
                image_url = pixabay_client.get_image_url(photo, "large")
                if image_url:
                    if download_and_save_image(image_url, city_image_path):
                        print(f"✓ Pre-fetched {city['name']} image from Pixabay cache")
                    return
        
        # Fetch from Pexels API first
        if _pexels_api_configured():
            try:
                stats["apiCalls"] += 1
                result = retry(lambda: pexels_client.fetch_photos(city_query, 10))
                if result and "photos" in result and len(result["photos"]) > 0:
                    # Cache the photos
                    media_cache["photos"][city_query] = result["photos"]
                    
                    # Download first photo
                    photo = result["photos"][0]
                    image_url = pexels_client.get_image_url(photo, "large")
                    if image_url:
                        if download_and_save_image(image_url, city_image_path):
                            print(f"✓ Pre-fetched {city['name']} image from Pexels")
                        return
            except Exception as e:
                print(f"Warning: Could not pre-fetch {city['name']} image from Pexels: {e}")
        
        # Fallback to Pixabay API
        if not _pixabay_api_configured():
            return
        try:
            stats["apiCalls"] += 1
            result = retry(lambda: pixabay_client.fetch_photos(city_query, 10))
            if result and "hits" in result and len(result["hits"]) > 0:
                # Cache the photos
                if "pixabay_photos" not in media_cache:
                    media_cache["pixabay_photos"] = {}
                media_cache["pixabay_photos"][city_query] = result["hits"]
                
                # Download first photo
                photo = result["hits"][0]
                image_url = pixabay_client.get_image_url(photo, "large")
                if image_url:
                    if download_and_save_image(image_url, city_image_path):
                        print(f"✓ Pre-fetched {city['name']} image from Pixabay")
        except Exception as e:
            print(f"Warning: Could not pre-fetch {city['name']} image from Pixabay: {e}")
    
    # Execute in parallel with rate limiting
    with ThreadPoolExecutor(max_workers=CONFIG["MAX_CONCURRENT_API_CALLS"]) as executor:
        futures = [executor.submit(fetch_city_image, city) for city in cities]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error in city image fetch: {e}")
    
    print(f"City images pre-fetch complete. ({stats['apiCalls']} API calls)")


def generate_location_page_data(
    city: Dict,
    location_name: str,
    url: str,
    page_type: str,  # "city" or "area"
    area_name: Optional[str] = None
) -> Dict[str, Any]:
    """Generate common page data for city and area pages (reduces duplication)"""
    hero_media = get_random_hero_media()
    date_modified = datetime.now().isoformat()
    
    # Generate title from config template when present; else fallback
    fallback = f"Find Soccer Games, Pickup & Leagues in {location_name} | {SITE_CONFIG['brand']['siteName']}"
    if page_type == "city":
        title = _get_seo_title("city", city=location_name, fallback_title=fallback)
    else:
        title = _get_seo_title("area", area=area_name or "", city=city["name"], fallback_title=fallback)
    description = SEOHelper.generate_meta_description_optimized(
        title, location_name, page_type, include_cta=True
    )

    # Generate optimized keywords for SEO
    modifiers = city.get("searchModifiers", [])
    keywords = SEOHelper.generate_keywords_optimized(location_name, page_type, modifiers)
    if area_name:
        keywords.extend([
            f"soccer {city['name']}", 
            f"soccer {area_name.lower()} {city['name'].lower()}",
            f"{area_name} soccer",
            f"soccer near {area_name}"
        ])

    # Generate meta tags with enhanced properties
    meta = SEOHelper.generate_meta_tags({
        "title": title,
        "description": description,
        "canonical": url,
        "ogImage": hero_media["poster"] or SITE_CONFIG["meta"]["defaultImage"],
        "ogUrl": url,
        "keywords": keywords,
        "location": location_name,
        "themeColor": "#0B5E2F",
        "video": hero_media.get("video"),
        "pageType": page_type
    })
    
    # Generate breadcrumbs
    breadcrumbs = [
        {"name": "Home", "url": f"{SITE_CONFIG['baseUrl']}/"},
        {"name": SITE_CONFIG["brand"]["siteName"], "url": f"{ROOT_URL}"},
        {"name": city["name"], "url": f"{ROOT_URL}{city['slug']}/"}
    ]
    if page_type == "area":
        breadcrumbs.append({"name": area_name, "url": url})
    else:
        breadcrumbs.append({"name": city["name"], "url": url})
    
    # Generate structured data schemas
    faq_schema = SEOHelper.generate_faq_schema(
        [{"question": fq["question"].replace("{city}", location_name), 
          "answer": fq["answer"].replace("{city}", location_name)} 
         for fq in SPORT_CONFIG["faqTemplates"]],
        url
    )
    
    howto_schema = SEOHelper.generate_howto_schema(
        SPORT_CONFIG["answerBlockSteps"],
        f"How to find, organize, and play soccer in {location_name}",
        description,
        url
    )
    
    # Add video schema if hero video is available
    video_schema = None
    if hero_media.get("video"):
        video_schema = SEOHelper.generate_video_object_schema(
            hero_media["video"],
            hero_media.get("poster", ""),
            f"Soccer in {location_name}",
            description
        )
    
    # Get coordinates if available (handle both lat/lng and latitude/longitude formats)
    coordinates = city.get("coordinates")
    postal_code = city.get("postalCode")
    
    # Normalize coordinates format for consistent handling
    if coordinates:
        normalized_coords = {
            "latitude": coordinates.get("latitude") or coordinates.get("lat"),
            "longitude": coordinates.get("longitude") or coordinates.get("lng")
        }
        if normalized_coords["latitude"] and normalized_coords["longitude"]:
            coordinates = normalized_coords

    local_business_schema = SEOHelper.generate_local_business_schema(
        city["name"], url, area_name, coordinates, postal_code, include_rating=True
    )
    place_schema = SEOHelper.generate_place_schema(city["name"], url, area_name, coordinates)

    # Add Service schema for better local SEO
    service_schema = SEOHelper.generate_service_schema(
        f"Soccer Community Services in {location_name}",
        "Soccer Community Platform",
        city["name"],
        url
    )
    
    additional_schemas = [s for s in [faq_schema, howto_schema, local_business_schema, place_schema, service_schema, video_schema] if s]
    
    location_primary_image = _absolute_image_url(hero_media.get("poster") or SITE_CONFIG["meta"]["defaultImage"])
    json_ld = SEOHelper.generate_json_ld({
        "title": title, "description": description, "url": url, "dateModified": date_modified, 
        "breadcrumbs": breadcrumbs, "additionalSchemas": additional_schemas,
        "speakableSelectors": _location_speakable_selectors(),
        "primaryImageOfPage": location_primary_image
    })
    
    # Get FAQ count based on page type
    faq_count = SITE_CONFIG["messaging"]["faq"].get(f"{page_type}Count")
    faqs_to_use = SPORT_CONFIG["faqTemplates"][:faq_count] if faq_count else SPORT_CONFIG["faqTemplates"]
    
    return {
        "meta": meta,
        "json_ld": json_ld,
        "hero_media": hero_media,
        "location_name": location_name,
        "faqs_to_use": faqs_to_use
    }


def _build_location_page_replacements(
    page_data: Dict,
    city: Dict,
    location_name: str,
    page_type: str,
    area_name: Optional[str] = None,
    all_cities: List[Dict] = None,
    area_pages_exist: Optional[Dict[str, bool]] = None
) -> Dict[str, str]:
    """Build common replacements dictionary for city and area pages (reduces duplication)"""
    nav_brand = generate_nav_brand().replace("{{SITE_NAME}}", SITE_CONFIG["brand"]["siteName"]).replace("{{POWERED_BY}}", SITE_CONFIG["brand"]["poweredBy"])
    
    # Determine context and navigation based on page type
    if page_type == "city":
        context = {"city_name": city["name"]}
        nav_menu = generate_navigation(False, city_slug=city["slug"])
        blog_context = {"city": city["name"]}
        blog_type = "city"
    else:  # area
        context = {"city_name": city["name"], "area_name": area_name}
        nav_menu = generate_navigation(False, city_slug=city["slug"], area_slug=name_to_slug(area_name))
        blog_context = {"area_name": area_name, "city_name": city["name"]}
        blog_type = "area"
    
    # Generate hero section using new scalable system
    hero_section_content = generate_hero_section_content(page_type, context, city)
    
    replacements = {
        "META_TITLE": page_data["meta"]["title"],
        "META_DESCRIPTION": page_data["meta"]["description"],
        "META_CANONICAL": page_data["meta"]["canonical"],
        "META_ROBOTS": page_data["meta"].get("robots", ""),
        "META_AUTHOR": page_data["meta"].get("author", ""),
        "META_LANGUAGE": page_data["meta"].get("language", ""),
        "META_KEYWORDS": page_data["meta"].get("keywords", ""),
        "META_GEO": page_data["meta"].get("geo", ""),
        "META_HREFLANG": page_data["meta"].get("hreflang", ""),
        "META_THEME_COLOR": page_data["meta"].get("themeColor", ""),
        "META_APPLE_MOBILE_WEB_APP": page_data["meta"].get("appleMobileWebApp", ""),
        "META_FORMAT_DETECTION": page_data["meta"].get("formatDetection", ""),
        "META_REFERRER": page_data["meta"].get("referrer", ""),
        "OG_TAGS": page_data["meta"]["ogTags"],
        "TWITTER_TAGS": page_data["meta"]["twitterTags"],
        "JSON_LD": page_data["json_ld"],
        "NAV_BRAND": nav_brand,
        "NAV_MENU": nav_menu,
        "HERO_SECTION_CONTENT": hero_section_content,
        "HERO_VIDEO_SOURCES": generate_video_sources(page_data["hero_media"]["video"], city["slug"]),
        "HERO_POSTER": page_data["hero_media"]["poster"],
        "HERO_BACKGROUND_STYLE": generate_background_style(page_data["hero_media"]["poster"]),
        "CITY_NAME": location_name,
        "CITY_OPTIONS": generate_city_options(all_cities, city["slug"]),
        "ANSWER_STEPS": generate_answer_steps(SPORT_CONFIG["answerBlockSteps"], True),
        "QUICK_FACTS_BEST_TIMES": SPORT_CONFIG["quickFacts"]["bestTimes"],
        "QUICK_FACTS_INDOOR_OUTDOOR": SPORT_CONFIG["quickFacts"]["indoorVsOutdoor"],
        "QUICK_FACTS_GROUP_SIZE": SPORT_CONFIG["quickFacts"]["groupSize"],
        "QUICK_FACTS_SKILL_LEVELS": SPORT_CONFIG["quickFacts"]["skillLevels"],
        "FAQS": generate_faqs(page_data["faqs_to_use"], location_name),
        "ABOUT_SECTION": "",
        "BLOG_SECTION": generate_blog_section(blog_type, blog_context),
        "IN_SHORT_SECTION": generate_in_short_section(page_type, city["name"]),
        "KEY_TAKEAWAYS_SECTION": generate_key_takeaways_section(),
        "SITE_NAME": SITE_CONFIG["brand"]["siteName"],
        "HUB_MARKETING_NAME": HUB_MARKETING,
        "POWERED_BY": SITE_CONFIG["brand"]["poweredBy"],
        "NAV_CTA_TEXT": SITE_CONFIG["messaging"]["cta"].get("nav", "Get local game invites"),
        "LEADS_ENDPOINT": _get_leads_endpoint(),
        "TRACKING_CONFIG_JSON": json.dumps(_get_tracking_config()),
        "FOOTER_NETWORK_LINKS": generate_footer_network_links(),
        "LAST_UPDATED": datetime.now().strftime("%d/%m/%Y")
    }
    org_label, org_help = _get_organizer_form_copy(location_name)
    replacements["ORGANIZER_CHECKBOX_LABEL"] = org_label
    replacements["ORGANIZER_CHECKBOX_HELP"] = org_help

    # Area links (only for city pages)
    if page_type == "city":
        area_links = generate_area_links(city, all_cities, area_pages_exist)
        replacements["AREA_LINKS_SECTION"] = f'''
        <!-- Area Links -->
        <section class="area-links" id="area-links">
            <div class="container container--content">
                <h2 class="area-links__title">{SITE_CONFIG["messaging"]["sections"]["areaLinksTitle"].replace("{city_name}", city['name'])}</h2>
                <div class="area-links__grid">
                    {area_links}
                </div>
            </div>
        </section>''' if area_links else ""
    else:
        replacements["AREA_LINKS_SECTION"] = ""
    
    # City links placement (common for both)
    city_links_html = generate_city_links(all_cities, city["slug"], True)
    city_links_section = generate_city_links_section(city_links_html)
    if SITE_CONFIG["messaging"]["cityLinks"]["placement"] == "before_faqs":
        replacements["CITY_LINKS_BEFORE_FAQS"] = city_links_section
        replacements["CITY_LINKS_AFTER_FAQS"] = ""
    else:
        replacements["CITY_LINKS_BEFORE_FAQS"] = ""
        replacements["CITY_LINKS_AFTER_FAQS"] = city_links_section
    
    return replacements


def generate_city_page(city: Dict, template: str, all_cities: List[Dict], area_pages_exist: Optional[Dict[str, bool]] = None) -> str:
    """Generate a city page"""
    url = f"{ROOT_URL}{city['slug']}/"
    page_data = generate_location_page_data(city, city["name"], url, "city")
    replacements = _build_location_page_replacements(page_data, city, city["name"], "city", None, all_cities, area_pages_exist)
    html_content = apply_common_replacements(template, replacements)
    return html_content


def generate_area_page(city: Dict, area_name: str, template: str, all_cities: List[Dict]) -> str:
    """Generate an area page"""
    area_slug = name_to_slug(area_name)
    location_name = f"{area_name}, {city['name']}"
    url = f"{ROOT_URL}{city['slug']}/{area_slug}/"
    page_data = generate_location_page_data(city, location_name, url, "area", area_name)
    replacements = _build_location_page_replacements(page_data, city, location_name, "area", area_name, all_cities)
    html_content = apply_common_replacements(template, replacements)
    return html_content


def generate_hub_page(template: str, cities: List[Dict]) -> str:
    """Generate hub page - COMPETES FOR SAME KEYWORDS AS ALL PAGES"""
    url = f"{ROOT_URL}"
    title = _get_seo_title("hub", fallback_title=f"Find Soccer Games, Pickup & Leagues in {HUB_MARKETING} | {SITE_CONFIG['brand']['siteName']}")
    description = SEOHelper.generate_meta_description_optimized(title, HUB_MARKETING, "hub", include_cta=True)
    date_modified = datetime.now().isoformat()
    
    queries = _get_media_queries()
    video_queries = queries.get("heroVideo", [])
    poster_queries = queries.get("heroPoster", [])
    video_query = video_queries[0] if video_queries else "soccer game"
    poster_query = poster_queries[0] if poster_queries else "soccer field"
    video = get_random_media("video", video_query)
    poster, poster_provider = get_random_photo_with_provider(poster_query)
    hero_video = ""
    if video:
        if video_query in media_cache.get("pixabay_videos", {}):
            hero_video = pixabay_client.get_video_url(video) or ""
        else:
            hero_video = pexels_client.get_video_url(video) or ""
    hero_poster = get_image_url_for_photo(poster, poster_provider or "pexels", "large") if poster else ""
    
    # Generate optimized keywords for SEO - SAME AS ALL PAGES
    keywords = SEOHelper.generate_keywords_optimized(HUB_MARKETING, "hub")
    
    meta = SEOHelper.generate_meta_tags({
        "title": title, 
        "description": description, 
        "canonical": url,
        "ogImage": hero_poster or SITE_CONFIG["meta"]["defaultImage"], 
        "ogUrl": url,
        "keywords": keywords, 
        "location": HUB_MARKETING,
        "themeColor": "#0B5E2F",
        "video": hero_video,
        "pageType": "hub"
    })
    
    # Generate structured data schemas for hub page
    hub_faqs = SPORT_CONFIG["faqTemplates"][:SITE_CONFIG["messaging"]["faq"]["hubCount"]]
    faq_schema = SEOHelper.generate_faq_schema(
        [{"question": fq["question"].replace("{city}", HUB_MARKETING),
          "answer": fq["answer"].replace("{city}", HUB_MARKETING)}
         for fq in hub_faqs],
        url
    )
    
    howto_schema = SEOHelper.generate_howto_schema(
        SPORT_CONFIG["answerBlockSteps"],
        f"How to find, organize, and play soccer in {HUB_MARKETING}",
        description,
        url
    )
    
    # Add video schema for hub page
    video_schema = None
    if hero_video:
        video_schema = SEOHelper.generate_video_object_schema(
            hero_video,
            hero_poster or SITE_CONFIG["meta"]["defaultImage"],
            f"Soccer in {HUB_MARKETING}",
            description
        )
    
    # Add Service schema for hub-wide service (GEO optimization)
    # Note: Organization schema is already included in generate_json_ld
    service_schema = SEOHelper.generate_service_schema(
        f"Soccer Community Services in {HUB_MARKETING}",
        "Soccer Community Platform",
        HUB_MARKETING,
        url
    )
    
    # Optional Review and Event schemas from config (GEO/trust)
    reviews = SITE_CONFIG.get("reviews") or []
    review_schema = SEOHelper.generate_review_schema(reviews) if reviews else None
    events = SITE_CONFIG.get("events") or []
    event_schemas = []
    for e in events[:10]:
        event_schemas.append(SEOHelper.generate_event_schema(
            e.get("name", ""),
            e.get("startDate", ""),
            e.get("location", HUB_MARKETING),
            e.get("url", url),
            e.get("description")
        ))
    
    additional_schemas = [s for s in [faq_schema, howto_schema, video_schema, service_schema, review_schema] if s] + event_schemas
    
    primary_image = _absolute_image_url(hero_poster or SITE_CONFIG["meta"]["defaultImage"])
    json_ld = SEOHelper.generate_json_ld({
        "title": title, "description": description, "url": url, "dateModified": date_modified,
        "breadcrumbs": [
            {"name": "Home", "url": f"{SITE_CONFIG['baseUrl']}/"},
            {"name": "Soccer", "url": url}
        ],
        "additionalSchemas": additional_schemas,
        "speakableSelectors": _hub_speakable_selectors(),
        "primaryImageOfPage": primary_image
    })
    
    nav_brand = generate_nav_brand().replace("{{SITE_NAME}}", SITE_CONFIG["brand"]["siteName"]).replace("{{POWERED_BY}}", SITE_CONFIG["brand"]["poweredBy"])
    nav_menu = generate_navigation(True)
    
    # Generate hero section using new scalable system
    hero_section_content = generate_hero_section_content("hub")
    
    replacements = {
        "META_TITLE": meta["title"],
        "META_DESCRIPTION": meta["description"],
        "META_CANONICAL": meta["canonical"],
        "META_ROBOTS": meta.get("robots", ""),
        "META_AUTHOR": meta.get("author", ""),
        "META_LANGUAGE": meta.get("language", ""),
        "META_KEYWORDS": meta.get("keywords", ""),
        "META_GEO": meta.get("geo", ""),
        "META_HREFLANG": meta.get("hreflang", ""),
        "META_THEME_COLOR": meta.get("themeColor", ""),
        "META_APPLE_MOBILE_WEB_APP": meta.get("appleMobileWebApp", ""),
        "META_FORMAT_DETECTION": meta.get("formatDetection", ""),
        "META_REFERRER": meta.get("referrer", ""),
        "OG_TAGS": meta["ogTags"],
        "TWITTER_TAGS": meta["twitterTags"],
        "JSON_LD": json_ld,
        "NAV_BRAND": nav_brand,
        "NAV_MENU": nav_menu,
        "HERO_SECTION_CONTENT": hero_section_content,
        "HERO_VIDEO_SOURCES": generate_video_sources(hero_video, "home"),
        "HERO_POSTER": hero_poster,
        "HERO_BACKGROUND_STYLE": generate_background_style(hero_poster),
        "CITY_NAME": HUB_MARKETING,
        "CITY_OPTIONS": generate_city_options(cities),
        "ANSWER_STEPS": generate_answer_steps(SPORT_CONFIG["answerBlockSteps"], True),
        "QUICK_FACTS_BEST_TIMES": SPORT_CONFIG["quickFacts"]["bestTimes"],
        "QUICK_FACTS_INDOOR_OUTDOOR": SPORT_CONFIG["quickFacts"]["indoorVsOutdoor"],
        "QUICK_FACTS_GROUP_SIZE": SPORT_CONFIG["quickFacts"]["groupSize"],
        "QUICK_FACTS_SKILL_LEVELS": SPORT_CONFIG["quickFacts"]["skillLevels"],
        "FAQS": generate_faqs(
            SPORT_CONFIG["faqTemplates"][:SITE_CONFIG["messaging"]["faq"]["hubCount"]],
            HUB_MARKETING
        ),
        "ABOUT_SECTION": generate_about_section(2),
        "BLOG_SECTION": generate_blog_section("country"),
        "AREA_LINKS_SECTION": "",
        "IN_SHORT_SECTION": generate_in_short_section("hub"),
        "KEY_TAKEAWAYS_SECTION": generate_key_takeaways_section(),
        "SITE_NAME": SITE_CONFIG["brand"]["siteName"],
        "HUB_MARKETING_NAME": HUB_MARKETING,
        "POWERED_BY": SITE_CONFIG["brand"]["poweredBy"],
        "NAV_CTA_TEXT": SITE_CONFIG["messaging"]["cta"].get("nav", "Get local game invites"),
        "LEADS_ENDPOINT": _get_leads_endpoint(),
        "TRACKING_CONFIG_JSON": json.dumps(_get_tracking_config()),
        "FOOTER_NETWORK_LINKS": generate_footer_network_links(),
        "LAST_UPDATED": datetime.now().strftime("%d/%m/%Y")
    }
    hub_org_label, hub_org_help = _get_organizer_form_copy(replacements["CITY_NAME"])
    replacements["ORGANIZER_CHECKBOX_LABEL"] = hub_org_label
    replacements["ORGANIZER_CHECKBOX_HELP"] = hub_org_help

    # Standardize city links placement based on config
    city_links_html = generate_city_links(cities, None, True)
    city_links_section = generate_city_links_section(city_links_html)
    if SITE_CONFIG["messaging"]["cityLinks"]["placement"] == "before_faqs":
        replacements["CITY_LINKS_BEFORE_FAQS"] = city_links_section
        replacements["CITY_LINKS_AFTER_FAQS"] = ""
    else:
        replacements["CITY_LINKS_BEFORE_FAQS"] = ""
        replacements["CITY_LINKS_AFTER_FAQS"] = city_links_section
    
    html_content = apply_common_replacements(template, replacements)
    return html_content


def _sitemap_image_caption_for_url(url: str) -> str:
    """Return a page-specific image caption for sitemap (GEO/context)."""
    base = (SITE_CONFIG.get("baseUrl") or "").rstrip("/")
    path = url.replace(base, "", 1).strip("/") if base else url.strip("/")
    if not path or path == "":
        return f"Pickup soccer in {HUB_MARKETING}"
    if "blog/" in path or path == "blog":
        # Humanize first path segment after blog/ for caption if present
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            slug_title = parts[1].replace("-", " ")
            return f"Soccer blog: {slug_title}"
        return f"Soccer blog and pickup soccer in {HUB_MARKETING}"
    parts = [p for p in path.split("/") if p]
    for city in SPORT_CONFIG.get("cities", []):
        if city.get("slug") != parts[0]:
            continue
        city_name = city.get("name", parts[0])
        if len(parts) == 1:
            return f"Pickup soccer in {city_name}"
        area_slug = parts[1]
        for area_name in city.get("areas", []):
            if name_to_slug(area_name) == area_slug:
                return f"Pickup soccer in {area_name}, {city_name}"
        return f"Pickup soccer in {city_name}"
    return f"Soccer community in {HUB_MARKETING}"


def generate_sitemap(urls: List[str], url_images: Optional[Dict[str, List[str]]] = None,
                     url_captions: Optional[Dict[str, str]] = None) -> str:
    """Generate enhanced sitemap.xml with image and video support, optimized priorities. url_captions maps URL to image caption."""
    base_url = SITE_CONFIG["baseUrl"]
    lastmod = datetime.now().strftime("%Y-%m-%d")
    
    url_entries = []
    for url in urls:
        # Optimize priorities based on page importance
        if url == ROOT_URL or url == f"{base_url}/":
            priority = "1.0"  # Homepage/hub page
            changefreq = "daily"
        elif "/blog/" in url:
            priority = "0.7"  # Blog posts
            changefreq = "monthly"
        elif any(city["slug"] in url for city in SPORT_CONFIG["cities"]):
            if url.count("/") == 3:  # City page
                priority = "0.9"  # High priority for city pages
                changefreq = "weekly"
            else:  # Area page
                priority = "0.8"  # Medium-high priority for area pages
                changefreq = "weekly"
        else:
            priority = "0.6"  # Other pages
            changefreq = "weekly"
        
        url_entry = f'''  <url>
    <loc>{url}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>'''
        
        # Add images if available (caption per URL when provided)
        default_caption = f"Soccer community in {HUB_MARKETING}"
        if url_images and url in url_images:
            caption = (url_captions or {}).get(url) or default_caption
            caption_escaped = html.escape(caption)
            for image_url in url_images[url]:
                image_url_escaped = html.escape(image_url)
                url_entry += f'''
    <image:image>
      <image:loc>{image_url_escaped}</image:loc>
      <image:title>{html.escape(SITE_CONFIG["brand"]["siteName"])}</image:title>
      <image:caption>{caption_escaped}</image:caption>
    </image:image>'''
        
        url_entry += '''
  </url>'''
        url_entries.append(url_entry)
    
    # Add image namespace if images are present
    namespaces = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
    if url_images:
        namespaces += ' xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"'
    
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset {namespaces}>
{chr(10).join(url_entries)}
</urlset>'''


def generate_robots(sitemap_url: str) -> str:
    """Generate robots.txt"""
    return f'''User-agent: *
Allow: /

Sitemap: {sitemap_url}
'''


def _validate_required_assets() -> None:
    """Check that required template and asset paths exist; exit with clear message if not."""
    required = [
        "src/templates/page.template.html",
        "src/styles/main.css",
        "src/js/main.js",
        "src/js/storage.js",
        "src/js/referral.js",
        "src/js/analytics.js",
    ]
    missing = [p for p in required if not Path(p).exists()]
    if missing:
        print("ERROR: Required files missing. Cannot run generation.")
        for p in missing:
            print(f"  - {p}")
        print("Ensure the project structure is complete (templates and src assets).")
        exit(1)


def copy_assets():
    """Copy static assets (parallelized)"""
    assets = [
        {"src": "src/styles/main.css", "dest": "public/assets/styles/main.css"},
        {"src": "src/js/main.js", "dest": "public/assets/js/main.js"},
        {"src": "src/js/storage.js", "dest": "public/assets/js/storage.js"},
        {"src": "src/js/referral.js", "dest": "public/assets/js/referral.js"},
        {"src": "src/js/analytics.js", "dest": "public/assets/js/analytics.js"}
    ]
    
    def copy_asset(asset):
        src_path = Path(asset["src"])
        dest_path = Path(asset["dest"])
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        if src_path.exists():
            shutil.copy2(src_path, dest_path)
            print(f"Copied {asset['src']} to {asset['dest']}")
        else:
            print(f"Warning: {asset['src']} not found")
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        executor.map(copy_asset, assets)


def generate_page_with_error_handling(generator, page_name: str) -> Dict[str, Any]:
    """Generate page with error handling"""
    try:
        html = generator()
        stats["pagesGenerated"] += 1
        return {"success": True, "html": html, "pageName": page_name}
    except Exception as e:
        stats["pagesFailed"] += 1
        print(f"Error generating {page_name}: {e}")
        return {"success": False, "error": str(e), "pageName": page_name}


def write_file_safe(file_path: Path, content: str, page_name: str) -> bool:
    """Write file with error handling (directory should already exist from pre-creation)"""
    try:
        # Directory should already exist from pre-creation, but ensure it does as fallback
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        print(f"Failed to write {page_name}: {e}")
        return False


def should_regenerate_page(page_path: Path, dependencies: List[Path]) -> bool:
    """Check if page should be regenerated based on dependencies"""
    # Always regenerate if page doesn't exist
    if not page_path.exists():
        return True
    
    # Get page modification time
    try:
        page_mtime = page_path.stat().st_mtime
    except OSError:
        return True  # If we can't read the file, regenerate
    
    # Check if any dependency is newer than the page
    for dep in dependencies:
        if not dep.exists():
            continue  # Skip missing dependencies
        try:
            dep_mtime = dep.stat().st_mtime
            if dep_mtime > page_mtime:
                return True  # Dependency changed, regenerate
        except OSError:
            continue  # Skip dependencies we can't read
    
    return False  # Page is up to date


def get_page_dependencies(page_type: str, page_data: Dict = None) -> List[Path]:
    """Get list of dependency files for a page type"""
    dependencies = [
        Path("src/templates/page.template.html"),
        Path("src/styles/main.css"),
        Path("src/js/main.js"),
        Path("src/js/storage.js"),
        Path("src/js/referral.js")
    ]
    
    # Add config files as dependencies
    config_dir = Path("src/config")
    if (config_dir / "site.config.json").exists():
        dependencies.append(config_dir / "site.config.json")
    sport_path = resolved_sport_config_path(config_dir)
    if sport_path.exists():
        dependencies.append(sport_path)
    for extra in (config_dir / "config_loader.py", config_dir / "site_context.py"):
        if extra.exists():
            dependencies.append(extra)
    
    # Add environment-specific config if it exists
    env = os.getenv("ENV", "production").lower()
    env_config = config_dir / f"site.config.{env}.json"
    if env_config.exists():
        dependencies.append(env_config)
    
    # Add generate.py itself as a dependency (code changes should trigger regeneration)
    dependencies.append(Path("generate.py"))
    
    return dependencies


def validate_assets() -> bool:
    """Validate that all required assets exist before generation"""
    required_assets = [
        "src/templates/page.template.html",
        "src/styles/main.css",
        "src/js/main.js",
        "src/js/storage.js",
        "src/js/referral.js",
        "public/assets/images/football_hub_logo_2.png"
    ]
    
    missing_assets = []
    for asset_path in required_assets:
        if not Path(asset_path).exists():
            missing_assets.append(asset_path)
    
    if missing_assets:
        print("ERROR: Required assets are missing:")
        for asset in missing_assets:
            print(f"  - {asset}")
        return False
    
    # City images are optional - will be auto-fetched from Pexels if missing
    # No need to warn about them
    
    return True


def main():
    """Main generation function"""
    stats["startTime"] = time.time()

    # Optional: skip full generation when public site already exists (e.g. Replit with SKIP_GENERATION=1)
    skip_gen = os.getenv("SKIP_GENERATION", "").strip().lower() in ("1", "true", "yes")
    if skip_gen:
        path_segment = get_base_path_segment()
        hub_sentinel = (Path("public") / path_segment / "index.html") if path_segment else Path("public/index.html")
        if hub_sentinel.exists():
            print("SKIP_GENERATION is set and hub page exists; skipping generation.")
            return
        print("SKIP_GENERATION is set but hub page not found; running generation.")

    print("Starting site generation...")
    _validate_required_assets()

    # Validate required environment variables (security check)
    missing_vars = []
    if not SITE_CONFIG.get("pexels", {}).get("apiKey"):
        missing_vars.append("PEXELS_API_KEY")
    if not SITE_CONFIG.get("pixabay", {}).get("apiKey"):
        missing_vars.append("PIXABAY_API_KEY")
    
    if missing_vars:
        print("\n" + "=" * 60)
        print("SECURITY WARNING: Missing Required Environment Variables")
        print("=" * 60)
        print("The following API keys must be set as environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nExample:")
        print(f"  export PEXELS_API_KEY='your-pexels-key'")
        print(f"  export PIXABAY_API_KEY='your-pixabay-key'")
        print("\nFor production, set these in your deployment environment.")
        print("=" * 60 + "\n")
        
        print("NOTE: Continuing without API keys. Local assets will be used instead.\n")
        print("      To enable API-based media fetching, set these keys in your environment.\n")
    
    # Load cache
    cache_loaded = load_cache()
    
    # Ensure pixabay keys exist (safety check)
    if "pixabay_videos" not in media_cache:
        media_cache["pixabay_videos"] = {}
    if "pixabay_photos" not in media_cache:
        media_cache["pixabay_photos"] = {}
    
    # Create public directory structure
    Path("public").mkdir(exist_ok=True)
    path_segment = get_base_path_segment()
    Path(f"public/{path_segment}").mkdir(parents=True, exist_ok=True)

    # When generating to root, remove legacy output roots so they never accumulate
    legacy_roots = SITE_CONFIG.get("legacyPublicRootsToRemove") or ["nyc", "uk"]
    if path_segment == "":
        for name in legacy_roots:
            legacy_dir = Path("public") / str(name).strip("/\\")
            if legacy_dir.is_dir():
                shutil.rmtree(legacy_dir)
                print(f"Removed legacy output root: public/{name}/")
        site_name = SITE_CONFIG["brand"]["siteName"]
        redirect_template = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="0;url={target}">
  <title>Redirecting to {site_name}</title>
  <script>window.location.replace("{target}");</script>
</head>
<body>
  <p>Redirecting to <a href="{target}">{site_name}</a>…</p>
</body>
</html>
'''
        for entry in SITE_CONFIG.get("legacyRedirects") or []:
            segments = entry.get("path") or []
            target = (entry.get("target") or "/").strip() or "/"
            if not segments:
                continue
            redirect_dir = Path("public")
            for seg in segments:
                redirect_dir = redirect_dir / str(seg).strip("/\\")
            redirect_dir.mkdir(parents=True, exist_ok=True)
            html = redirect_template.format(site_name=site_name, target=target)
            (redirect_dir / "index.html").write_text(html, encoding="utf-8")

    # Fetch Pexels media (only if cache not loaded or incomplete)
    if not cache_loaded or not media_cache.get("videos"):
        fetch_pexels_media_parallel()
        save_cache()
    
    # Pre-fetch city images from Pexels (with fallback)
    fetch_city_images_parallel(SPORT_CONFIG["cities"])
    save_cache()  # Save cache after fetching city images
    
    # Read template once
    with open("src/templates/page.template.html", "r", encoding="utf-8") as f:
        template = f.read()
    
    # Validate required assets before generation
    if not validate_assets():
        print("Asset validation failed. Please ensure all required assets exist.")
        return
    
    # Pre-compute area page existence map (performance optimization)
    # This eliminates file system I/O during page generation
    # Since we generate all area pages from config, we know they'll all exist
    print("Pre-computing area page existence map...")
    area_pages_exist = {}
    for city in SPORT_CONFIG["cities"]:
        if city.get("areas"):
            for area_name in city["areas"]:
                area_slug = name_to_slug(area_name)
                cache_key = f"{city['slug']}/{area_slug}"
                # All areas in config will have pages generated, so mark as existing
                area_pages_exist[cache_key] = True
    
    # Check for incremental generation flag
    incremental = os.getenv("INCREMENTAL", "false").lower() == "true"
    
    # Pre-create all required directories (performance optimization)
    # This eliminates redundant directory creation during page generation
    print("Pre-creating directory structure...")
    path_segment = get_base_path_segment()
    base_dir = Path("public") / path_segment
    base_dir.mkdir(parents=True, exist_ok=True)
    
    # Pre-create city directories
    for city in SPORT_CONFIG["cities"]:
        city_dir = base_dir / city["slug"]
        city_dir.mkdir(parents=True, exist_ok=True)
        
        # Pre-create area directories
        if city.get("areas"):
            for area_name in city["areas"]:
                area_slug = name_to_slug(area_name)
                area_dir = city_dir / area_slug
                area_dir.mkdir(parents=True, exist_ok=True)
    
    # Pre-create blog directory
    blog_dir = base_dir / "blog"
    blog_dir.mkdir(parents=True, exist_ok=True)
    
    # Build list of all pages to generate
    pages_to_generate = []
    urls = [ROOT_URL]
    
    # Get common dependencies for all pages
    common_deps = get_page_dependencies("common")
    
    # City pages
    for city in SPORT_CONFIG["cities"]:
        path_segment = get_base_path_segment()
        city_dir = Path("public") / path_segment / city["slug"]
        city_path = city_dir / "index.html"
        city_copy = city  # Fix closure issue
        area_pages_exist_copy = area_pages_exist  # Fix closure issue
        
        # Check if regeneration is needed (incremental mode)
        if incremental and not should_regenerate_page(city_path, common_deps):
            print(f"Skipping {city['name']} (up to date)")
            continue
        
        pages_to_generate.append({
            "type": "city",
            "city": city_copy,
            "path": city_path,
            "url": f"{ROOT_URL}{city['slug']}/",
            "generator": lambda c=city_copy, ap=area_pages_exist_copy: generate_city_page(c, template, SPORT_CONFIG["cities"], ap)
        })
        urls.append(f"{ROOT_URL}{city['slug']}/")
        
        # Area pages
        if city.get("areas"):
            for area_name in city["areas"]:
                area_slug = name_to_slug(area_name)
                area_dir = city_dir / area_slug
                area_path = area_dir / "index.html"
                city_copy = city  # Fix closure issue
                area_copy = area_name  # Fix closure issue
                
                # Check if regeneration is needed (incremental mode)
                if incremental and not should_regenerate_page(area_path, common_deps):
                    continue  # Skip silently for areas
                
                pages_to_generate.append({
                    "type": "area",
                    "city": city_copy,
                    "areaName": area_copy,
                    "path": area_path,
                    "url": f"{ROOT_URL}{city['slug']}/{area_slug}/",
                    "generator": lambda c=city_copy, a=area_copy: generate_area_page(c, a, template, SPORT_CONFIG["cities"])
                })
                urls.append(f"{ROOT_URL}{city['slug']}/{area_slug}/")
    
    # Hub page
    path_segment = get_base_path_segment()
    hub_path = Path(f"public/{path_segment}/index.html")
    if not incremental or should_regenerate_page(hub_path, common_deps):
        pages_to_generate.append({
            "type": "hub",
            "path": hub_path,
            "url": f"{ROOT_URL}",
            "generator": lambda: generate_hub_page(template, SPORT_CONFIG["cities"])
        })
    elif incremental:
        print("Skipping hub page (up to date)")
    
    # Blog post pages
    path_segment = get_base_path_segment()
    blog_dir = Path("public") / path_segment / "blog"
    blog_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique blog posts efficiently (optimized to avoid duplicate generation)
    # Strategy: Track unique titles as we generate, skip duplicates early
    unique_posts = []
    seen_titles = set()
    
    # Country-level posts (unique, no duplicates possible)
    country_posts = generate_blog_posts("country")
    for post in country_posts:
        if post["title"] not in seen_titles:
            seen_titles.add(post["title"])
            unique_posts.append(post)
    
    # City-level posts (generate per city, but track duplicates)
    for city in SPORT_CONFIG["cities"]:
        city_posts = generate_blog_posts("city", {"city": city["name"]})
        for post in city_posts:
            if post["title"] not in seen_titles:
                seen_titles.add(post["title"])
                # Ensure content is preserved (deep copy to avoid reference issues)
                import copy
                post_with_content = copy.deepcopy(post)
                unique_posts.append(post_with_content)
    
    # Area-level posts (generate per area, but track duplicates)
    for city in SPORT_CONFIG["cities"]:
        if city.get("areas"):
            for area_name in city["areas"]:
                area_posts = generate_blog_posts("area", {"area_name": area_name, "city_name": city["name"]})
                for post in area_posts:
                    if post["title"] not in seen_titles:
                        seen_titles.add(post["title"])
                        unique_posts.append(post)
    
    # Generate blog post pages
    for post in unique_posts:
        # Use slug from post if available, otherwise generate from title
        post_slug = post.get("slug") or title_to_slug(post["title"])
        post_path = blog_dir / post_slug / "index.html"
        
        # Check if regeneration is needed (incremental mode)
        if incremental and not should_regenerate_page(post_path, common_deps):
            continue  # Skip silently for blog posts
        
        # Create a deep copy to avoid closure issues and preserve content
        import copy
        post_copy = copy.deepcopy(post)
        pages_to_generate.append({
            "type": "blog",
            "path": post_path,
            "url": f"{ROOT_URL}blog/{post_slug}/",
            "generator": lambda p=post_copy: generate_blog_post_page(p, template)
        })
        urls.append(f"{ROOT_URL}blog/{post_slug}/")
    
    # Generate all pages in parallel (with limit)
    print(f"Generating {len(pages_to_generate)} pages...")
    
    def process_page(page):
        result = generate_page_with_error_handling(page["generator"], f"{page['type']} page: {page['path']}")
        if result["success"]:
            html = replace_asset_paths(result["html"], depth_from_public_path(page["path"]))
            write_file_safe(page["path"], html, str(page["path"]))
        return result
    
    with ThreadPoolExecutor(max_workers=CONFIG["MAX_CONCURRENT_PAGES"]) as executor:
        page_results = list(executor.map(process_page, pages_to_generate))
    
    # Generate sitemap with images and per-URL captions (GEO/context)
    url_images = {}
    url_captions = {}
    for url in urls:
        images = []
        # Add hero images for location pages
        path_segment = get_base_path_segment()
        if f"/{path_segment.split('/')[-1]}/" in url and url.count("/") >= 3:
            # This is a city or area page
            images.append(f"{SITE_CONFIG['baseUrl']}/assets/images/football_hub_logo_2.png")
        # Add blog images
        if "/blog/" in url:
            blog_images = SPORT_CONFIG.get("images", {}).get("blog", [])
            if blog_images:
                images.append(blog_images[0])
            else:
                images.append(f"{SITE_CONFIG['baseUrl']}/assets/images/football_hub_logo_2.png")
        if images:
            url_images[url] = images
            url_captions[url] = _sitemap_image_caption_for_url(url)
    
    sitemap = generate_sitemap(urls, url_images if url_images else None, url_captions if url_captions else None)
    Path("public/sitemap.xml").write_text(sitemap, encoding="utf-8")
    print("Generated sitemap.xml with image support")
    
    robots = generate_robots(f"{SITE_CONFIG['baseUrl']}/sitemap.xml")
    Path("public/robots.txt").write_text(robots, encoding="utf-8")
    print("Generated robots.txt")
    
    # Copy static assets
    copy_assets()
    
    # Print stats
    duration = time.time() - stats["startTime"]
    print("\n" + "=" * 50)
    print("Site generation complete!")
    print(f"Generated {stats['pagesGenerated']} pages successfully")
    if stats["pagesFailed"] > 0:
        print(f"Failed: {stats['pagesFailed']} pages")
    print(f"Total pages: {len(urls)}")
    print(f"API calls: {stats['apiCalls']}")
    print(f"Cache hits: {stats['cacheHits']}")
    print(f"Duration: {duration:.2f}s")
    print("=" * 50)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Generation error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

