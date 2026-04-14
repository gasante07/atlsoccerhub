"""Flask application"""
import os
import time
from flask import Flask, session, jsonify, request, g
from flask_cors import CORS
from api.routes.notify import notify_bp
from api.routes.leads import leads_bp
from api.routes.admin import admin_bp
from api.routes.export import export_bp
from api.routes.media import media_bp
from api.routes.referral import referral_bp
from api.utils.config import SECRET_KEY, ALLOWED_ORIGINS, SITE_DISPLAY_NAME
from api.utils.logger import setup_logging, get_logger, log_request, log_error
from datetime import datetime

# Setup logging first
setup_logging()
logger = get_logger(__name__)

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))
app.secret_key = SECRET_KEY

# Security: Validate secret key in production
if os.getenv("ENV", "production").lower() == "production":
    default_secret = "dev-secret-key-change-in-production"
    if SECRET_KEY == default_secret:
        error_msg = (
            "CRITICAL: SECRET_KEY must be set to a strong random value in production. "
            "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
        logger.critical(error_msg)
        raise ValueError(error_msg)

logger.info("Flask application initialized")

# CORS configuration - allow preflight requests
CORS(app, 
     origins=ALLOWED_ORIGINS,
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization"],
     supports_credentials=True)

# Register blueprints
app.register_blueprint(notify_bp)
app.register_blueprint(leads_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(export_bp)
app.register_blueprint(media_bp)
app.register_blueprint(referral_bp)

@app.route("/")
def index():
    """Health check"""
    return {"status": "ok", "service": f"{SITE_DISPLAY_NAME} API"}

@app.route("/health")
def health():
    """Detailed health check endpoint"""
    try:
        from api.models.database import db
        
        with db.get_connection() as conn:
            cur = db._cursor(conn)
            db._execute(cur, "SELECT 1")
            cur.fetchone()
        
        logger.debug("Health check passed")
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "service": f"{SITE_DISPLAY_NAME} API"
        }), 200
    except Exception as e:
        log_error(e, context="health_check")
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 503


# Request logging middleware
@app.before_request
def before_request():
    """Log request start time"""
    g.start_time = time.time()


@app.after_request
def after_request(response):
    """Log request completion"""
    duration_ms = (time.time() - g.start_time) * 1000 if hasattr(g, 'start_time') else None
    log_request(request, response, duration_ms)
    return response


# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    logger.warning(f"404 Not Found: {request.path}")
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    log_error(error, context="internal_server_error", path=request.path)
    return jsonify({"error": "Internal server error"}), 500


@app.errorhandler(Exception)
def handle_exception(error):
    """Handle unhandled exceptions"""
    log_error(error, context="unhandled_exception", path=request.path)
    return jsonify({"error": "An unexpected error occurred"}), 500

if __name__ == "__main__":
    # Debug mode only in development
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)

