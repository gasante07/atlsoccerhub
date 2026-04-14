"""Admin panel routes"""
from flask import Blueprint, request, render_template, session, redirect, url_for, jsonify
from werkzeug.security import check_password_hash
from api.models.database import db
from api.utils.config import ADMIN_PASSWORD_HASH, SECRET_KEY, SITE_DISPLAY_NAME

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/admin", methods=["GET"])
def admin_login_page():
    """Admin login page"""
    if session.get("admin_logged_in"):
        return redirect(url_for("admin.admin_dashboard"))
    return render_template("admin.html", logged_in=False, site_name=SITE_DISPLAY_NAME)

@admin_bp.route("/admin/login", methods=["POST"])
def admin_login():
    """Admin login"""
    password = request.form.get("password", "")
    
    if not ADMIN_PASSWORD_HASH:
        return jsonify({"error": "Admin password not configured"}), 500

    if check_password_hash(ADMIN_PASSWORD_HASH, password):
        session["admin_logged_in"] = True
        return redirect(url_for("admin.admin_dashboard"))
    else:
        return render_template("admin.html", logged_in=False, error="Invalid password")

@admin_bp.route("/admin/dashboard", methods=["GET"])
def admin_dashboard():
    """Admin dashboard"""
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin.admin_login_page"))

    # Get filters
    city = request.args.get("city", "")
    organizer_interest = request.args.get("organizer_interest", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    page = int(request.args.get("page", 1))
    per_page = 50
    offset = (page - 1) * per_page

    # Get leads
    leads = db.get_leads(
        city=city if city else None,
        organizer_interest=organizer_interest if organizer_interest else None,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None,
        limit=per_page,
        offset=offset
    )

    # Get counts
    total = db.count_leads(
        city=city if city else None,
        organizer_interest=organizer_interest if organizer_interest else None,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None
    )

    # Get stats
    stats = db.get_stats()

    return render_template(
        "admin.html",
        logged_in=True,
        site_name=SITE_DISPLAY_NAME,
        leads=leads,
        stats=stats,
        filters={
            "city": city,
            "organizer_interest": organizer_interest,
            "date_from": date_from,
            "date_to": date_to
        },
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page
        }
    )

@admin_bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    """Admin logout"""
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin.admin_login_page"))

