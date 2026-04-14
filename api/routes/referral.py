"""Referral system endpoints"""
from flask import Blueprint, request, jsonify
from api.models.database import db
from api.utils.security import check_rate_limit, sanitize_input, validate_email
from api.utils.referral_utils import generate_referral_code
from api.utils.logger import get_logger, log_error

referral_bp = Blueprint("referral", __name__)
logger = get_logger(__name__)

@referral_bp.route("/api/referral/generate", methods=["POST"])
def generate_code():
    """Generate referral code for a user"""
    try:
        # Get client IP for rate limiting
        ip = request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr)
        if ip:
            ip = ip.split(",")[0].strip()

        # Rate limiting
        if not check_rate_limit(ip, 10, 3600):  # 10 requests per hour
            return jsonify({"error": "Rate limit exceeded"}), 429

        # Get data
        if request.is_json:
            data = request.json
        else:
            data = request.form.to_dict()

        email = sanitize_input(data.get("email", ""))
        
        if not email or not validate_email(email):
            return jsonify({"error": "Valid email is required"}), 400

        # Check if user already has a referral code
        existing = db.get_referral_code(email)
        if existing:
            return jsonify({
                "ok": True,
                "referral_code": existing["referral_code"],
                "existing": True
            })

        # Generate new code
        referral_code = generate_referral_code(db)
        
        # Create referral code
        success = db.create_referral_code(email, referral_code)
        
        if not success:
            logger.warning(f"Failed to create referral code for {email}")
            return jsonify({"error": "Failed to create referral code"}), 500

        logger.info(f"Generated referral code for {email}: {referral_code}")
        return jsonify({
            "ok": True,
            "referral_code": referral_code,
            "existing": False
        })

    except Exception as e:
        log_error(e, context="generate_code")
        return jsonify({"error": "Internal server error"}), 500

@referral_bp.route("/api/referral/stats", methods=["GET"])
def get_stats():
    """Get referral stats for a user"""
    try:
        email = sanitize_input(request.args.get("email", ""))
        
        if not email or not validate_email(email):
            return jsonify({"error": "Valid email is required"}), 400

        # Get referral code
        referral_code_data = db.get_referral_code(email)
        if not referral_code_data:
            return jsonify({
                "ok": True,
                "has_code": False,
                "referral_count": 0,
                "badges": [],
                "rank": None
            })

        # Get stats
        referral_count = db.get_referral_count(email)
        badges = db.get_user_badges(email)
        rank = db.get_user_rank(email)

        return jsonify({
            "ok": True,
            "has_code": True,
            "referral_code": referral_code_data["referral_code"],
            "referral_count": referral_count,
            "badges": [{"type": b["badge_type"], "earned_at": b["earned_at"]} for b in badges],
            "rank": rank
        })

    except Exception as e:
        log_error(e, context="get_stats")
        return jsonify({"error": "Internal server error"}), 500

@referral_bp.route("/api/referral/leaderboard", methods=["GET"])
def get_leaderboard():
    """Get referral leaderboard"""
    try:
        limit = int(request.args.get("limit", 50))
        limit = min(limit, 100)  # Cap at 100

        leaderboard = db.get_leaderboard(limit)

        return jsonify({
            "ok": True,
            "leaderboard": leaderboard
        })

    except Exception as e:
        log_error(e, context="get_leaderboard")
        return jsonify({"error": "Internal server error"}), 500

@referral_bp.route("/api/referral/code/<code>", methods=["GET"])
def validate_code(code):
    """Validate referral code and get referrer info"""
    try:
        sanitized_code = sanitize_input(code)
        
        referral_data = db.get_referral_code_by_code(sanitized_code)
        
        if not referral_data:
            logger.debug(f"Invalid referral code attempted: {sanitized_code}")
            return jsonify({
                "ok": False,
                "valid": False,
                "error": "Invalid referral code"
            }), 404

        # Get referrer name from leads if available
        referrer_name = None
        leads = db.get_leads(limit=1)
        for lead in leads:
            if lead.get("email") == referral_data["user_email"]:
                referrer_name = lead.get("name")
                break

        return jsonify({
            "ok": True,
            "valid": True,
            "referrer_email": referral_data["user_email"],
            "referrer_name": referrer_name or "A friend"
        })

    except Exception as e:
        log_error(e, context="validate_code")
        return jsonify({"error": "Internal server error"}), 500
