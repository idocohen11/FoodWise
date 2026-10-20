from flask import Blueprint, jsonify

from backend.services import analytics_service

bp = Blueprint("analytics", __name__, url_prefix="/api")


@bp.get("/analytics/preferences")
def preferences():
    return jsonify(preferences=analytics_service.preferences())
