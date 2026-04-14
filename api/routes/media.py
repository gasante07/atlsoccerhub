"""
API routes for media fetching from Pexels, Pixabay, and Unsplash (images only).
"""

from flask import Blueprint, jsonify, request
from api.utils.media_service import create_media_service
from src.config.config_loader import load_config

media_bp = Blueprint("media", __name__, url_prefix="/api/media")


@media_bp.route("/video", methods=["GET"])
def search_video():
    """
    Search for videos.
    
    Query params:
        - query: Search query (required)
        - provider: Preferred provider ("pexels" or "pixabay"; optional)
        - per_page: Number of results (default: 15)
    """
    query = request.args.get("query")
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400
    
    config = load_config()
    media_service = create_media_service(config["site"])
    
    provider = request.args.get("provider")
    per_page = int(request.args.get("per_page", 15))
    
    providers = None
    if provider:
        providers = [provider]
    
    results = media_service.search_videos(
        query=query,
        providers=providers,
        per_page=per_page,
        prefer_provider=provider
    )
    
    # Convert MediaResult objects to dictionaries
    videos = []
    for result in results:
        videos.append({
            "url": result.url,
            "thumbnail_url": result.thumbnail_url,
            "width": result.width,
            "height": result.height,
            "duration": result.duration,
            "provider": result.provider,
            "id": result.id,
            "author": result.author,
            "author_url": result.author_url
        })
    
    return jsonify({
        "query": query,
        "count": len(videos),
        "videos": videos
    })


@media_bp.route("/image", methods=["GET"])
def search_image():
    """
    Search for images.
    
    Query params:
        - query: Search query (required)
        - provider: Preferred provider ("pexels", "pixabay", or "unsplash"; optional)
        - per_page: Number of results (default: 20)
    """
    query = request.args.get("query")
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400
    
    config = load_config()
    media_service = create_media_service(config["site"])
    
    provider = request.args.get("provider")
    per_page = int(request.args.get("per_page", 20))
    
    providers = None
    if provider:
        providers = [provider]
    
    results = media_service.search_images(
        query=query,
        providers=providers,
        per_page=per_page,
        prefer_provider=provider
    )
    
    # Convert MediaResult objects to dictionaries
    images = []
    for result in results:
        images.append({
            "url": result.url,
            "thumbnail_url": result.thumbnail_url,
            "width": result.width,
            "height": result.height,
            "provider": result.provider,
            "id": result.id,
            "author": result.author,
            "author_url": result.author_url
        })
    
    return jsonify({
        "query": query,
        "count": len(images),
        "images": images
    })


@media_bp.route("/hero/video", methods=["GET"])
def get_hero_video():
    """
    Get a random hero video using configured search queries.
    
    Query params:
        - queries: Comma-separated list of search queries (optional, uses config default if not provided)
    """
    config = load_config()
    media_service = create_media_service(config["site"])
    
    queries_param = request.args.get("queries")
    if queries_param:
        queries = [q.strip() for q in queries_param.split(",")]
    else:
        # Single source: media.searchQueries or pexels.searchQueries fallback
        site = config["site"]
        queries = (
            site.get("media", {}).get("searchQueries", {}).get("heroVideo")
            or site.get("pexels", {}).get("searchQueries", {}).get("heroVideo", ["pickup soccer", "soccer game", "casual soccer match"])
        )
    result = media_service.get_hero_video(queries)
    
    if not result:
        return jsonify({"error": "No videos found"}), 404
    
    return jsonify({
        "url": result.url,
        "thumbnail_url": result.thumbnail_url,
        "width": result.width,
        "height": result.height,
        "duration": result.duration,
        "provider": result.provider,
        "id": result.id,
        "author": result.author,
        "author_url": result.author_url
    })


@media_bp.route("/hero/poster", methods=["GET"])
def get_hero_poster():
    """
    Get a random hero poster image using configured search queries.
    
    Query params:
        - queries: Comma-separated list of search queries (optional, uses config default if not provided)
    """
    config = load_config()
    media_service = create_media_service(config["site"])
    
    queries_param = request.args.get("queries")
    if queries_param:
        queries = [q.strip() for q in queries_param.split(",")]
    else:
        # Single source: media.searchQueries or pexels.searchQueries fallback
        site = config["site"]
        queries = (
            site.get("media", {}).get("searchQueries", {}).get("heroPoster")
            or site.get("pexels", {}).get("searchQueries", {}).get("heroPoster", ["soccer field", "pickup soccer", "casual soccer players"])
        )
    result = media_service.get_hero_poster(queries)
    
    if not result:
        return jsonify({"error": "No images found"}), 404
    
    return jsonify({
        "url": result.url,
        "thumbnail_url": result.thumbnail_url,
        "width": result.width,
        "height": result.height,
        "provider": result.provider,
        "id": result.id,
        "author": result.author,
        "author_url": result.author_url
    })
