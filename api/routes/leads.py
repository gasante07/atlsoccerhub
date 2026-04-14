"""Leads proxy: forward submissions to Google Apps Script (avoids CORS)."""
import requests
from flask import Blueprint, request, jsonify
from api.utils.config import LEADS_WEB_APP_URL
from api.utils.logger import get_logger

leads_bp = Blueprint("leads", __name__)
logger = get_logger(__name__)


@leads_bp.route("/api/leads", methods=["POST", "OPTIONS"])
def leads_proxy():
    """Forward lead payload to GAS web app; same-origin so no CORS."""
    if request.method == "OPTIONS":
        return "", 200

    if not LEADS_WEB_APP_URL:
        logger.error("LEADS_WEB_APP_URL not configured")
        return jsonify({"success": False, "error": "Leads endpoint not configured"}), 503

    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Content-Type must be application/json"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Invalid JSON body"}), 400

        resp = requests.post(
            LEADS_WEB_APP_URL,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )

        try:
            result = resp.json()
        except Exception:
            result = {}

        if not resp.ok:
            return jsonify(result if result else {"success": False, "error": f"Upstream error: {resp.status_code}"}), resp.status_code

        return jsonify(result)
    except requests.RequestException as e:
        logger.exception("Leads proxy request failed")
        return jsonify({"success": False, "error": "Unable to connect. Please try again."}), 502
    except Exception as e:
        logger.exception("Leads proxy error")
        return jsonify({"success": False, "error": "Internal server error"}), 500
