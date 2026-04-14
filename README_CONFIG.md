# Configuration Guide

## Environment-Based Configuration

The generator supports environment-based configuration through the `ENV` environment variable.

### Available Environments

- **production** (default): Uses production URLs and settings
- **development**: Uses localhost URLs for local development
- **staging**: Uses staging URLs (if configured)

### Usage

```bash
# Production (default)
python generate.py

# Development
ENV=development python generate.py

# Staging
ENV=staging python generate.py
```

## Configuration Files

### Main Configuration Files

1. **`src/config/site.config.json`**: Base site configuration
2. **`src/config/uk-volleyball.config.json`**: UK volleyball-specific configuration (cities, areas, etc.)

### Environment-Specific Overrides

- **`src/config/site.config.development.json`**: Development overrides
- **`src/config/site.config.staging.json`**: Staging overrides
- **`src/config/site.config.production.json`**: Production overrides (optional)

Environment-specific files override values from the base config file.

## Environment Variables

The following environment variables can override config values:

- **`BASE_URL`**: Overrides `baseUrl` in config
- **`PEXELS_API_KEY`**: Overrides Pexels API key (required for generation in production; set via Replit Secrets or .env, do not commit real keys to `site.config.json`)
- **`PIXABAY_API_KEY`**: Overrides Pixabay API key (required for generation in production; set via Replit Secrets or .env, do not commit real keys to `site.config.json`)
- **`ENV`**: Sets the environment (development/staging/production)

## Fallback Behavior

If JSON config files are not found, the generator falls back to hardcoded configuration in `generate.py`. This ensures backward compatibility.

## Example: Development Setup

1. Create `src/config/site.config.development.json`:
```json
{
  "baseUrl": "http://localhost:8000"
}
```

2. Run with development environment:
```bash
ENV=development python generate.py
```

The generator will:
- Load `src/config/site.config.json` (base config)
- Apply overrides from `src/config/site.config.development.json`
- Use `http://localhost:8000` as the base URL

