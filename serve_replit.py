#!/usr/bin/env python3
"""
Flask server optimized for Replit deployment
Serves the generated static site from public/ directory
Also includes API routes for form submissions
"""
from flask import Flask, send_file, request, jsonify
from flask_cors import CORS
from pathlib import Path
import os

# Import API routes
try:
    from api.routes.notify import notify_bp
    from api.routes.admin import admin_bp
    from api.routes.export import export_bp
    from api.routes.media import media_bp
    from api.routes.referral import referral_bp
    from api.utils.config import ALLOWED_ORIGINS, SECRET_KEY
    API_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] API routes not available: {e}")
    print("       Static site will be served, but API endpoints will not work.")
    API_AVAILABLE = False

_DEFAULT_SECRET = "dev-secret-key-change-in-production"

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "api", "templates"))
app.secret_key = os.environ.get("SECRET_KEY", _DEFAULT_SECRET) if not API_AVAILABLE else SECRET_KEY

if API_AVAILABLE and os.getenv("ENV", "production").lower() == "production":
    if SECRET_KEY == _DEFAULT_SECRET:
        raise ValueError(
            "CRITICAL: SECRET_KEY must be set to a strong random value in production. "
            'Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))" '
            "and set it in Replit Secrets."
        )

# CORS configuration if API is available
if API_AVAILABLE:
    CORS(app,
         origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else "*",
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization"],
         supports_credentials=True)

# Serve from public directory
PUBLIC_DIR = Path("public")


@app.after_request
def add_cache_control(response):
    """HTML and API responses stay fresh; versioned /assets/* can cache in the browser."""
    try:
        path = request.path or ""
    except RuntimeError:
        return response

    if path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=604800, immutable"
        response.headers.pop("Pragma", None)
        response.headers.pop("Expires", None)
    elif path in ("/robots.txt", "/sitemap.xml"):
        response.headers["Cache-Control"] = "public, max-age=3600"
        response.headers.pop("Pragma", None)
        response.headers.pop("Expires", None)
    else:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.route("/health")
def health():
    """Lightweight health check for Replit autoscale / monitors."""
    body = {"status": "ok", "api": API_AVAILABLE}
    return jsonify(body), 200


@app.route("/")
def index():
    """Serve hub (landing) page at root"""
    hub_path = PUBLIC_DIR / "index.html"
    if hub_path.exists():
        return send_file(hub_path)
    return (
        "Site not generated. Run 'python generate.py' first, then start the server.",
        503,
        {"Content-Type": "text/plain; charset=utf-8"},
    )


@app.route("/robots.txt")
def robots():
    """Serve robots.txt"""
    robots_path = PUBLIC_DIR / "robots.txt"
    if robots_path.exists():
        return send_file(robots_path), 200, {"Content-Type": "text/plain"}
    return "robots.txt not found", 404


@app.route("/sitemap.xml")
def sitemap():
    """Serve sitemap.xml"""
    sitemap_path = PUBLIC_DIR / "sitemap.xml"
    if sitemap_path.exists():
        return send_file(sitemap_path), 200, {"Content-Type": "application/xml"}
    return "sitemap.xml not found", 404


# Register API blueprints if available
if API_AVAILABLE:
    app.register_blueprint(notify_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(referral_bp)
    print("[OK] API routes registered")


@app.route("/<path:path>")
def serve_static(path):
    """Serve static files with proper routing"""
    if path.startswith("api/") or path.startswith("admin"):
        from flask import abort
        abort(404)

    file_path = PUBLIC_DIR / path

    # Check if it's a directory, serve index.html
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return send_file(index_file)
        return f"Directory not found: {path}", 404

    if file_path.exists() and file_path.is_file():
        mimetype_map = {
            ".css": "text/css",
            ".js": "application/javascript",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".xml": "application/xml",
            ".svg": "image/svg+xml",
            ".webp": "image/webp",
            ".woff2": "font/woff2",
            ".woff": "font/woff",
            ".ico": "image/x-icon",
        }
        ext = Path(path).suffix.lower()
        mimetype = mimetype_map.get(ext, "text/html")
        return send_file(file_path, mimetype=mimetype, conditional=True)

    # Try with index.html for directory paths (e.g., /uk/football/london/)
    if not path.endswith((".html", ".css", ".js", ".jpg", ".jpeg", ".png", ".mp4", ".xml", ".txt")):
        html_path = PUBLIC_DIR / path / "index.html"
        if html_path.exists():
            return send_file(html_path)

    return f"File not found: {path}", 404


@app.errorhandler(404)
def not_found(error):
    """Custom 404 handler"""
    return "Page not found. Please ensure the site has been generated with 'python generate.py'", 404


if __name__ == "__main__":
    # Replit uses PORT environment variable
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")

    # Check if public directory exists
    if not PUBLIC_DIR.exists():
        print("[WARN] public/ directory not found!")
        print("       Run 'python generate.py' first to generate the site.")
        print("       Server will start but pages will not be available.")

    print("=" * 60)
    print("Atlanta Soccer Hub - Replit Server")
    print("=" * 60)
    print(f"Serving from: {PUBLIC_DIR.absolute()}")
    print(f"Server running on {host}:{port}")
    print(f"Access via: http://localhost:{port}")
    print("=" * 60)

    app.run(host=host, port=port, debug=False)
