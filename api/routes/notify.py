"""Lead submission endpoint"""
from flask import Blueprint, request, jsonify
from api.models.database import db
from api.utils.security import check_rate_limit, validate_honeypot, sanitize_input, validate_email
from api.utils.config import RATE_LIMIT_PER_HOUR
from api.utils.logger import get_logger, log_error

notify_bp = Blueprint("notify", __name__)
logger = get_logger(__name__)

@notify_bp.route("/api/notify", methods=["POST", "OPTIONS"])
def notify():
    """Handle lead submission"""
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return "", 200
    
    try:
        # Get client IP
        ip = request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr)
        if ip:
            ip = ip.split(",")[0].strip()

        # Rate limiting
        if not check_rate_limit(ip, RATE_LIMIT_PER_HOUR, 3600):
            logger.warning(f"Rate limit exceeded for IP: {ip}")
            return jsonify({"error": "Rate limit exceeded"}), 429

        # Get data
        if request.is_json:
            data = request.json
        else:
            data = request.form.to_dict()

        # Validate honeypot
        honeypot = data.get("website", "")
        if not validate_honeypot(honeypot):
            # Silently reject (don't reveal it's a honeypot)
            logger.info(f"Honeypot triggered for IP: {ip}")
            return jsonify({"ok": True})

        # Validate required fields
        email = sanitize_input(data.get("email", ""))
        city = sanitize_input(data.get("city", ""))

        if not email or not validate_email(email):
            return jsonify({"error": "Valid email is required"}), 400

        if not city:
            return jsonify({"error": "City is required"}), 400

        # Handle referral code
        referral_code = sanitize_input(data.get("referral_code", ""))
        referred_by = None
        
        if referral_code:
            # Validate referral code and get referrer
            referral_data = db.get_referral_code_by_code(referral_code)
            if referral_data:
                referred_by = referral_data["user_email"]
                # Prevent self-referral
                if referred_by.lower() == email.lower():
                    referred_by = None
                    referral_code = None

        # Prepare data
        lead_data = {
            "email": email,
            "city": city,
            "name": sanitize_input(data.get("name", "")),
            "phone": sanitize_input(data.get("phone", "")),
            "skill_level": sanitize_input(data.get("skill_level", "")),
            "organizer_interest": sanitize_input(data.get("organizer_interest", "no")),
            "preferred_times": sanitize_input(data.get("preferred_times", "")),
            "page_url": sanitize_input(data.get("page_url", "")),
            "utm_json": sanitize_input(data.get("utm_json", "")),
            "ip": ip,
            "user_agent": request.headers.get("User-Agent", ""),
            "consent": data.get("consent") == "on" or data.get("consent") is True,
            "honeypot": honeypot,
            "referral_code": referral_code if referral_code else None,
            "referred_by": referred_by
        }

        # Insert into database
        lead_id = db.insert_lead(lead_data)

        # Handle referral tracking and badge awarding
        referral_created = False
        if referred_by and referral_code:
            # Create referral record
            try:
                db.create_referral(referred_by, email, referral_code)
                referral_created = True
                
                # Get current referral count
                referral_count = db.get_referral_count(referred_by)
                
                # Award badges based on milestones
                badge_milestones = {
                    1: "first_referral",
                    5: "five_referrals",
                    10: "ten_referrals",
                    25: "twenty_five_referrals",
                    50: "fifty_referrals"
                }
                
                for milestone, badge_type in badge_milestones.items():
                    if referral_count == milestone:
                        db.award_badge(referred_by, badge_type, f"Reached {milestone} referrals")
                        break
                        
            except Exception as e:
                log_error(e, context="referral_creation", email=email)
                # Don't fail the lead submission if referral tracking fails

        # Generate referral code for new user (if they don't have one)
        user_referral_code = None
        try:
            from api.utils.referral_utils import generate_referral_code
            
            existing_code = db.get_referral_code(email)
            if not existing_code:
                # Generate code for new user
                new_code = generate_referral_code(db)
                success = db.create_referral_code(email, new_code)
                if success:
                    user_referral_code = new_code
                    logger.info(f"Generated referral code for user: {email}")
                else:
                    logger.warning(f"Failed to create referral code for user: {email}")
            else:
                user_referral_code = existing_code["referral_code"]
        except Exception as e:
            log_error(e, context="referral_code_generation", email=email)

        logger.info(f"Lead submitted successfully: {email} from {city} (ID: {lead_id})")
        return jsonify({
            "ok": True,
            "id": lead_id,
            "referral_code": user_referral_code,
            "referred_by": referred_by if referral_created else None
        })

    except Exception as e:
        log_error(e, context="notify_endpoint", ip=ip if 'ip' in locals() else None)
        return jsonify({"error": "Internal server error"}), 500

