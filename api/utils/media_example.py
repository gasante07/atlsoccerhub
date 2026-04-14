"""
Example usage of the media service component.

Demonstrates MediaService for images and videos from Pexels, Pixabay, and Unsplash (images).
Uses config-driven soccer-themed queries from media.searchQueries when available.
"""

from api.utils.media_service import create_media_service
from api.utils.media_helpers import (
    generate_video_sources,
    generate_video_poster,
    generate_image_url,
    generate_og_image_url
)
from src.config.config_loader import load_config


def _hero_queries(config, key, default):
    """Get hero query list from media.searchQueries or pexels.searchQueries fallback."""
    site = config["site"]
    return (
        site.get("media", {}).get("searchQueries", {}).get(key)
        or site.get("pexels", {}).get("searchQueries", {}).get(key, default)
    )


def example_hero_video():
    """Example: Get a hero video using config-driven soccer queries."""
    config = load_config()
    media_service = create_media_service(config["site"])
    queries = _hero_queries(config, "heroVideo", ["pickup soccer", "soccer game", "casual soccer match"])
    video_result = media_service.get_hero_video(queries=queries)
    if video_result:
        video_sources = generate_video_sources(video_result)
        poster_url = generate_video_poster(video_result)
        print(f"Video URL: {video_result.url}")
        print(f"Poster URL: {poster_url}")
        print(f"Video Sources HTML:\n{video_sources}")
    else:
        print("No video found")


def example_hero_poster():
    """Example: Get a hero poster image using config-driven soccer queries."""
    config = load_config()
    media_service = create_media_service(config["site"])
    queries = _hero_queries(config, "heroPoster", ["soccer field", "pickup soccer", "casual soccer players"])
    image_result = media_service.get_hero_poster(queries=queries)
    if image_result:
        image_url = generate_image_url(image_result)
        print(f"Poster Image URL: {image_url} (provider: {image_result.provider})")
    else:
        print("No image found")


def example_search_videos():
    """Example: Search for videos with soccer-themed query (Pexels, Pixabay)."""
    config = load_config()
    media_service = create_media_service(config["site"])
    results = media_service.search_videos(query="soccer training", per_page=10)
    print(f"Found {len(results)} videos:")
    for result in results[:5]:
        print(f"  - {result.url} ({result.provider})")


def example_search_images():
    """Example: Search images with soccer-themed query (Pexels, Pixabay, Unsplash when configured)."""
    config = load_config()
    media_service = create_media_service(config["site"])
    results = media_service.search_images(
        query="soccer team",
        per_page=10
    )
    print(f"Found {len(results)} images:")
    for result in results[:5]:
        print(f"  - {result.url} ({result.provider})")


def example_search_images_unsplash():
    """Example: Search images including Unsplash (when apiKey is set in config)."""
    config = load_config()
    media_service = create_media_service(config["site"])
    # Include unsplash in provider order; service will use config order or try all
    results = media_service.search_images(
        query="soccer players",
        providers=["pexels", "pixabay", "unsplash"],
        per_page=10
    )
    print(f"Found {len(results)} images (may include Unsplash):")
    for result in results[:5]:
        print(f"  - {result.url} ({result.provider})")


def example_with_fallback():
    """Example: Using fallback when one provider fails"""
    config = load_config()
    media_service = create_media_service(config["site"])
    
    # Try Pexels first, fallback to Pixabay
    video_result = media_service.get_random_video(
        queries=["soccer match"],
        prefer_provider="pexels"  # Will try Pexels first, then Pixabay
    )
    
    if video_result:
        print(f"Got video from {video_result.provider}: {video_result.url}")


if __name__ == "__main__":
    print("=== Hero Video Example ===")
    example_hero_video()
    print("\n=== Hero Poster Example ===")
    example_hero_poster()
    print("\n=== Search Videos Example ===")
    example_search_videos()
    print("\n=== Search Images Example ===")
    example_search_images()
    print("\n=== Search Images (incl. Unsplash) Example ===")
    example_search_images_unsplash()
    print("\n=== Fallback Example ===")
    example_with_fallback()
