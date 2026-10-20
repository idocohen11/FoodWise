from flask import Blueprint, jsonify

from backend.routes.validation import integer, pagination, query_params
from backend.services import favorites_service

bp = Blueprint("favorites", __name__, url_prefix="/api")


@bp.get("/favorites")
def list_items():
    query_params({"limit", "offset"})
    limit, offset = pagination()
    return jsonify(favorites=favorites_service.list_items(limit, offset), limit=limit, offset=offset)


@bp.post("/favorites/<recipe_id>")
def add(recipe_id):
    return jsonify(favorites_service.add(integer(recipe_id, "recipe_id")))


@bp.delete("/favorites/<recipe_id>")
def delete(recipe_id):
    favorites_service.delete(integer(recipe_id, "recipe_id"))
    return "", 204
