# Media Service Component

A scalable, component-based media service for fetching images and videos from Pexels and Pixabay APIs with automatic fallback support.

## Features

- **Dual Provider Support**: Fetch from both Pexels and Pixabay APIs
- **Automatic Fallback**: If one provider fails, automatically tries the other
- **Rate Limiting**: Built-in rate limiting for Pixabay API
- **Scalable Architecture**: Component-based design for easy extension
- **Error Handling**: Graceful error handling with fallbacks
- **Type Safety**: Uses dataclasses and type hints for better code quality

## Components

### 1. MediaService (`media_service.py`)

Main service class that provides a unified interface for both APIs.

**Key Classes:**
- `PexelsClient`: Handles Pexels API requests
- `PixabayClient`: Handles Pixabay API requests with rate limiting
- `MediaService`: Unified service with fallback support
- `MediaResult`: Dataclass for media results

### 2. Media Helpers (`media_helpers.py`)

Utility functions for generating HTML from media results.

**Functions:**
- `generate_video_sources()`: Generate HTML `<source>` tags
- `generate_video_poster()`: Get poster URL for videos
- `generate_image_url()`: Get image URL
- `generate_og_image_url()`: Get Open Graph image URL

### 3. API Routes (`routes/media.py`)

RESTful API endpoints for media fetching.

**Endpoints:**
- `GET /api/media/video?query=...`: Search for videos
- `GET /api/media/image?query=...`: Search for images
- `GET /api/media/hero/video`: Get random hero video
- `GET /api/media/hero/poster`: Get random hero poster image

## Usage

### Basic Usage

```python
from api.utils.media_service import create_media_service
from src.config.config_loader import load_config

# Load configuration
config = load_config()

# Create media service
media_service = create_media_service(config["site"])

# Get a hero video
video = media_service.get_hero_video([
    "5-a-side football",
    "casual football match"
])

if video:
    print(f"Video URL: {video.url}")
    print(f"Provider: {video.provider}")
```

### Search Videos

```python
# Search videos from both providers
results = media_service.search_videos(
    query="football training",
    per_page=10
)

# Prefer a specific provider
results = media_service.search_videos(
    query="football training",
    prefer_provider="pexels"  # Will try Pexels first, fallback to Pixabay
)
```

### Search Images

```python
# Search images
results = media_service.search_images(
    query="football team",
    per_page=20
)
```

### Generate HTML

```python
from api.utils.media_helpers import generate_video_sources, generate_video_poster

video = media_service.get_hero_video(["football"])

if video:
    # Generate video sources HTML
    sources_html = generate_video_sources(video)
    # Output: <source src="..." type="video/mp4">
    
    # Get poster URL
    poster_url = generate_video_poster(video)
    # Output: "https://..."
```

### API Endpoints

#### Search Videos
```bash
GET /api/media/video?query=football&provider=pexels&per_page=15
```

#### Search Images
```bash
GET /api/media/image?query=football&provider=pixabay&per_page=20
```

#### Get Hero Video
```bash
GET /api/media/hero/video?queries=football,5-a-side
```

#### Get Hero Poster
```bash
GET /api/media/hero/poster?queries=football pitch,stadium
```

## Configuration

API keys can be configured in two ways:

1. **Config File** (`src/config/site.config.json`):
```json
{
  "pexels": {
    "apiKey": "your-key-here",
    "apiBaseUrl": "https://api.pexels.com"
  },
  "pixabay": {
    "apiKey": "your-key-here",
    "apiBaseUrl": "https://pixabay.com/api"
  }
}
```

2. **Environment Variables** (takes precedence):
```bash
PEXELS_API_KEY=your-key-here
PIXABAY_API_KEY=your-key-here
```

## Error Handling

The service handles errors gracefully:
- If an API request fails, it automatically tries the fallback provider
- If no results are found, returns empty list or None
- All exceptions are caught and logged, preventing crashes

## Rate Limiting

Pixabay has rate limits (100 requests per minute for free tier). The `PixabayClient` includes built-in rate limiting to prevent exceeding limits.

## Extending the Service

To add a new media provider:

1. Create a new client class (similar to `PexelsClient` or `PixabayClient`)
2. Implement `search_videos()` and `search_images()` methods
3. Add the client to `MediaService.__init__()`
4. Update `search_videos()` and `search_images()` to use the new provider

## Examples

See `api/utils/media_example.py` for complete usage examples.
