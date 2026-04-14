"""CSV export endpoint"""
from flask import Blueprint, request, Response, session
from api.models.database import db
import csv
import io

export_bp = Blueprint("export", __name__)

@export_bp.route("/api/export", methods=["GET"])
def export_csv():
    """Export leads as CSV"""
    # Check authentication
    if not session.get("admin_logged_in"):
        return Response("Unauthorized", status=401)

    # Get filters
    city = request.args.get("city", "")
    organizer_interest = request.args.get("organizer_interest", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    # Get all leads (no pagination for export; high limit for full backup)
    leads = db.get_leads(
        city=city if city else None,
        organizer_interest=organizer_interest if organizer_interest else None,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None,
        limit=500000,
        offset=0
    )

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header (include referral columns)
    writer.writerow([
        "ID", "Created At", "Email", "City", "Name", "Phone",
        "Skill Level", "Organizer Interest", "Preferred Times",
        "Page URL", "UTM JSON", "IP", "User Agent", "Consent",
        "Referral Code", "Referred By"
    ])

    # Rows
    for lead in leads:
        writer.writerow([
            lead.get("id"),
            lead.get("created_at"),
            lead.get("email"),
            lead.get("city"),
            lead.get("name") or "",
            lead.get("phone") or "",
            lead.get("skill_level") or "",
            lead.get("organizer_interest") or "",
            lead.get("preferred_times") or "",
            lead.get("page_url") or "",
            lead.get("utm_json") or "",
            lead.get("ip") or "",
            lead.get("user_agent") or "",
            "Yes" if lead.get("consent") else "No",
            lead.get("referral_code") or "",
            lead.get("referred_by") or ""
        ])

    # Create response
    response = Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=soccer_leads.csv"
        }
    )

    return response

