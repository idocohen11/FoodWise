from flask import Blueprint, jsonify

from backend.routes.validation import integer, pagination, pantry_body, query_params
from backend.services import pantry_service

bp = Blueprint("pantry", __name__, url_prefix="/api")


@bp.get("/pantry")
def list_items():
    query_params({"limit", "offset"})
    limit, offset = pagination()
    return jsonify(pantry=pantry_service.list_items(limit, offset), limit=limit, offset=offset)


@bp.post("/pantry")
def save_item():
    return jsonify(pantry_service.save_item(*pantry_body()))


@bp.delete("/pantry/<ingredient_id>")
def delete_item(ingredient_id):
    pantry_service.delete_item(integer(ingredient_id, "ingredient_id"))
    return "", 204
