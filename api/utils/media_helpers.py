"""
Helper utilities for generating HTML from media results.
"""

from typing import Optional, List
from api.utils.media_service import MediaResult


def generate_video_sources(media_result: Optional[MediaResult]) -> str:
    """
    Generate HTML <source> tags for a video MediaResult.
    
    Args:
        media_result: MediaResult from media service
    
    Returns:
        HTML string with <source> tags
    """
    if not media_result or not media_result.url:
        return ""
    
    # For Pexels videos, we might have multiple qualities
    # For now, we'll use the main URL
    source_tag = f'<source src="{media_result.url}" type="video/mp4">'
    
    return source_tag


def generate_video_poster(media_result: Optional[MediaResult]) -> str:
    """
    Get poster URL from a video MediaResult.
    
    Args:
        media_result: MediaResult from media service
    
    Returns:
        Poster URL string or empty string
    """
    if not media_result:
        return ""
    
    # Prefer thumbnail_url, fallback to empty
    return media_result.thumbnail_url or ""


def generate_image_url(media_result: Optional[MediaResult]) -> str:
    """
    Get image URL from a MediaResult.
    
    Args:
        media_result: MediaResult from media service
    
    Returns:
        Image URL string or empty string
    """
    if not media_result or not media_result.url:
        return ""
    
    return media_result.url


def generate_og_image_url(media_result: Optional[MediaResult], fallback: str = "") -> str:
    """
    Get Open Graph image URL from a MediaResult.
    
    Args:
        media_result: MediaResult from media service
        fallback: Fallback URL if no media result
    
    Returns:
        Image URL string
    """
    if media_result and media_result.url:
        return media_result.url
    
    return fallback
