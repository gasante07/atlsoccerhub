"""
Scalable media service component for fetching images and videos
from Pexels and Pixabay APIs with fallback support.
"""

import requests
import random
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class MediaType(Enum):
    """Media type enumeration"""
    IMAGE = "image"
    VIDEO = "video"
    ALL = "all"


@dataclass
class MediaResult:
    """Result from media API"""
    url: str
    thumbnail_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None  # For videos
    provider: str = ""  # "pexels", "pixabay", or "unsplash"
    id: Optional[str] = None
    author: Optional[str] = None
    author_url: Optional[str] = None


class PexelsClient:
    """Pexels API client for images and videos"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.pexels.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": api_key
        })
    
    def search_videos(self, query: str, per_page: int = 15, page: int = 1) -> List[MediaResult]:
        """Search for videos on Pexels"""
        if not self.api_key:
            return []
        
        try:
            url = f"{self.base_url}/videos/search"
            params = {
                "query": query,
                "per_page": min(per_page, 80),  # Pexels max is 80
                "page": page,
                "orientation": "landscape"  # Better for hero sections
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for video in data.get("videos", []):
                # Get the best quality video file
                video_files = video.get("video_files", [])
                if not video_files:
                    continue
                
                # Prefer HD quality, fallback to any available
                best_video = max(
                    video_files,
                    key=lambda x: x.get("width", 0) * x.get("height", 0)
                )
                
                results.append(MediaResult(
                    url=best_video.get("link", ""),
                    thumbnail_url=video.get("image", ""),
                    width=best_video.get("width"),
                    height=best_video.get("height"),
                    duration=video.get("duration"),
                    provider="pexels",
                    id=str(video.get("id", "")),
                    author=video.get("user", {}).get("name", ""),
                    author_url=video.get("user", {}).get("url", "")
                ))
            
            return results
        except Exception as e:
            print(f"Pexels video search error: {e}")
            return []
    
    def search_images(self, query: str, per_page: int = 20, page: int = 1) -> List[MediaResult]:
        """Search for images on Pexels"""
        if not self.api_key:
            return []
        
        try:
            url = f"{self.base_url}/v1/search"
            params = {
                "query": query,
                "per_page": min(per_page, 80),  # Pexels max is 80
                "page": page,
                "orientation": "landscape"  # Better for hero sections
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for photo in data.get("photos", []):
                # Get the best quality image
                src = photo.get("src", {})
                best_url = src.get("large") or src.get("medium") or src.get("original", "")
                
                results.append(MediaResult(
                    url=best_url,
                    thumbnail_url=src.get("medium", ""),
                    width=photo.get("width"),
                    height=photo.get("height"),
                    provider="pexels",
                    id=str(photo.get("id", "")),
                    author=photo.get("photographer", ""),
                    author_url=photo.get("photographer_url", "")
                ))
            
            return results
        except Exception as e:
            print(f"Pexels image search error: {e}")
            return []


class PixabayClient:
    """Pixabay API client for images and videos"""
    
    def __init__(self, api_key: str, base_url: str = "https://pixabay.com/api"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self._last_request_time = 0
        self._request_count = 0
        self._rate_limit_window = 60  # seconds
    
    def _check_rate_limit(self):
        """Simple rate limiting check"""
        current_time = time.time()
        if current_time - self._last_request_time > self._rate_limit_window:
            self._request_count = 0
            self._last_request_time = current_time
        
        if self._request_count >= 100:  # Pixabay free tier limit
            sleep_time = self._rate_limit_window - (current_time - self._last_request_time)
            if sleep_time > 0:
                time.sleep(sleep_time)
                self._request_count = 0
                self._last_request_time = time.time()
        
        self._request_count += 1
    
    def search_videos(self, query: str, per_page: int = 20, page: int = 1) -> List[MediaResult]:
        """Search for videos on Pixabay"""
        if not self.api_key:
            return []
        
        self._check_rate_limit()
        
        try:
            url = self.base_url
            params = {
                "key": self.api_key,
                "q": query,
                "video_type": "all",
                "per_page": min(per_page, 200),  # Pixabay max is 200
                "page": page,
                "image_type": "photo",  # Not used for videos but harmless
                "orientation": "horizontal"  # Better for hero sections
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for hit in data.get("hits", []):
                videos = hit.get("videos", {})
                if not videos:
                    continue
                
                # Get the best quality video
                best_video = None
                for quality in ["large", "medium", "small", "tiny"]:
                    if quality in videos and videos[quality].get("url"):
                        best_video = videos[quality]
                        break
                
                if not best_video:
                    continue
                
                results.append(MediaResult(
                    url=best_video.get("url", ""),
                    thumbnail_url=hit.get("picture_id") and f"https://i.vimeocdn.com/video/{hit['picture_id']}_640.jpg" or "",
                    width=best_video.get("width"),
                    height=best_video.get("height"),
                    duration=hit.get("duration"),
                    provider="pixabay",
                    id=str(hit.get("id", "")),
                    author=hit.get("user", ""),
                    author_url=hit.get("user_id") and f"https://pixabay.com/users/{hit['user_id']}" or ""
                ))
            
            return results
        except Exception as e:
            print(f"Pixabay video search error: {e}")
            return []
    
    def search_images(self, query: str, per_page: int = 20, page: int = 1) -> List[MediaResult]:
        """Search for images on Pixabay"""
        if not self.api_key:
            return []
        
        self._check_rate_limit()
        
        try:
            url = self.base_url
            params = {
                "key": self.api_key,
                "q": query,
                "image_type": "photo",
                "per_page": min(per_page, 200),  # Pixabay max is 200
                "page": page,
                "orientation": "horizontal",  # Better for hero sections
                "safesearch": "true"
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for hit in data.get("hits", []):
                # Get the best quality image
                best_url = hit.get("largeImageURL") or hit.get("webformatURL") or hit.get("previewURL", "")
                
                results.append(MediaResult(
                    url=best_url,
                    thumbnail_url=hit.get("webformatURL", ""),
                    width=hit.get("imageWidth"),
                    height=hit.get("imageHeight"),
                    provider="pixabay",
                    id=str(hit.get("id", "")),
                    author=hit.get("user", ""),
                    author_url=hit.get("user_id") and f"https://pixabay.com/users/{hit['user_id']}" or ""
                ))
            
            return results
        except Exception as e:
            print(f"Pixabay image search error: {e}")
            return []


class UnsplashClient:
    """Unsplash API client for images (no video search)."""

    def __init__(self, api_key: str, base_url: str = "https://api.unsplash.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def search_images(self, query: str, per_page: int = 20, page: int = 1) -> List[MediaResult]:
        """Search for images on Unsplash."""
        if not self.api_key:
            return []
        try:
            url = f"{self.base_url}/search/photos"
            params = {
                "query": query,
                "client_id": self.api_key,
                "per_page": min(per_page, 30),
                "page": page,
                "orientation": "landscape",
            }
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            results = []
            for photo in data.get("results", []):
                urls = photo.get("urls", {})
                results.append(MediaResult(
                    url=urls.get("regular") or urls.get("full") or urls.get("small", ""),
                    thumbnail_url=urls.get("small") or urls.get("thumb", ""),
                    width=photo.get("width"),
                    height=photo.get("height"),
                    provider="unsplash",
                    id=photo.get("id"),
                    author=photo.get("user", {}).get("name", ""),
                    author_url=photo.get("user", {}).get("links", {}).get("html", ""),
                ))
            return results
        except Exception as e:
            print(f"Unsplash image search error: {e}")
            return []


class MediaService:
    """
    Unified media service that can fetch from Pexels, Pixabay, and Unsplash
    with automatic fallback and config-driven provider order.
    """

    def __init__(
        self,
        pexels_config: Dict,
        pixabay_config: Dict,
        unsplash_config: Optional[Dict] = None,
    ):
        """Initialize media service with API configurations."""
        self.pexels = PexelsClient(
            api_key=pexels_config.get("apiKey", ""),
            base_url=pexels_config.get("apiBaseUrl", "https://api.pexels.com"),
        ) if pexels_config.get("apiKey") else None

        self.pixabay = PixabayClient(
            api_key=pixabay_config.get("apiKey", ""),
            base_url=pixabay_config.get("apiBaseUrl", "https://pixabay.com/api"),
        ) if pixabay_config.get("apiKey") else None

        unsplash_cfg = unsplash_config or {}
        self.unsplash = UnsplashClient(
            api_key=unsplash_cfg.get("apiKey", ""),
            base_url=unsplash_cfg.get("apiBaseUrl", "https://api.unsplash.com"),
        ) if unsplash_cfg.get("apiKey") else None
    
    def search_videos(
        self,
        query: str,
        providers: Optional[List[str]] = None,
        per_page: int = 15,
        prefer_provider: Optional[str] = None
    ) -> List[MediaResult]:
        """
        Search for videos across available providers with fallback.
        
        Args:
            query: Search query
            providers: List of providers to use (["pexels", "pixabay"] or None for all)
            per_page: Number of results per provider
            prefer_provider: Preferred provider to try first ("pexels" or "pixabay")
        
        Returns:
            List of MediaResult objects
        """
        if providers is None:
            providers = []
            if self.pexels:
                providers.append("pexels")
            if self.pixabay:
                providers.append("pixabay")
        
        if prefer_provider and prefer_provider in providers:
            providers = [prefer_provider] + [p for p in providers if p != prefer_provider]
        
        all_results = []
        for provider in providers:
            if provider == "pexels" and self.pexels:
                results = self.pexels.search_videos(query, per_page=per_page)
                all_results.extend(results)
            elif provider == "pixabay" and self.pixabay:
                results = self.pixabay.search_videos(query, per_page=per_page)
                all_results.extend(results)
            
            # If we got results from preferred provider, we can stop
            if all_results and provider == prefer_provider:
                break
        
        return all_results
    
    def search_images(
        self,
        query: str,
        providers: Optional[List[str]] = None,
        per_page: int = 20,
        prefer_provider: Optional[str] = None
    ) -> List[MediaResult]:
        """
        Search for images across available providers with fallback.
        
        Args:
            query: Search query
            providers: List of providers to use (["pexels", "pixabay"] or None for all)
            per_page: Number of results per provider
            prefer_provider: Preferred provider to try first ("pexels" or "pixabay")
        
        Returns:
            List of MediaResult objects
        """
        if providers is None:
            providers = []
            if self.pexels:
                providers.append("pexels")
            if self.pixabay:
                providers.append("pixabay")
            if self.unsplash:
                providers.append("unsplash")

        if prefer_provider and prefer_provider in providers:
            providers = [prefer_provider] + [p for p in providers if p != prefer_provider]

        all_results = []
        for provider in providers:
            if provider == "pexels" and self.pexels:
                results = self.pexels.search_images(query, per_page=per_page)
                all_results.extend(results)
            elif provider == "pixabay" and self.pixabay:
                results = self.pixabay.search_images(query, per_page=per_page)
                all_results.extend(results)
            elif provider == "unsplash" and self.unsplash:
                results = self.unsplash.search_images(query, per_page=per_page)
                all_results.extend(results)

            # If we got results from preferred provider, we can stop
            if all_results and provider == prefer_provider:
                break

        return all_results

    def get_random_video(
        self,
        queries: List[str],
        providers: Optional[List[str]] = None,
        prefer_provider: Optional[str] = "pexels"
    ) -> Optional[MediaResult]:
        """
        Get a random video from multiple search queries.
        
        Args:
            queries: List of search queries to try
            providers: List of providers to use
            prefer_provider: Preferred provider
        
        Returns:
            Random MediaResult or None if no results
        """
        all_results = []
        for query in queries:
            results = self.search_videos(query, providers=providers, prefer_provider=prefer_provider, per_page=10)
            all_results.extend(results)
        
        if not all_results:
            return None
        
        return random.choice(all_results)
    
    def get_random_image(
        self,
        queries: List[str],
        providers: Optional[List[str]] = None,
        prefer_provider: Optional[str] = "pexels"
    ) -> Optional[MediaResult]:
        """
        Get a random image from multiple search queries.
        
        Args:
            queries: List of search queries to try
            providers: List of providers to use
            prefer_provider: Preferred provider
        
        Returns:
            Random MediaResult or None if no results
        """
        all_results = []
        for query in queries:
            results = self.search_images(query, providers=providers, prefer_provider=prefer_provider, per_page=10)
            all_results.extend(results)
        
        if not all_results:
            return None
        
        return random.choice(all_results)
    
    def get_hero_video(self, queries: List[str]) -> Optional[MediaResult]:
        """
        Get a hero video optimized for hero sections.
        Prefers Pexels for videos, falls back to Pixabay.
        """
        return self.get_random_video(queries, prefer_provider="pexels")
    
    def get_hero_poster(self, queries: List[str]) -> Optional[MediaResult]:
        """
        Get a hero poster image optimized for hero sections.
        Prefers Pexels for images, falls back to Pixabay.
        """
        return self.get_random_image(queries, prefer_provider="pexels")


def create_media_service(config: Dict) -> MediaService:
    """
    Factory function to create a MediaService from configuration.

    Args:
        config: Configuration dictionary with 'pexels', 'pixabay', and optional 'unsplash' keys

    Returns:
        MediaService instance
    """
    pexels_config = config.get("pexels", {})
    pixabay_config = config.get("pixabay", {})
    unsplash_config = config.get("unsplash", {})
    return MediaService(pexels_config, pixabay_config, unsplash_config)
