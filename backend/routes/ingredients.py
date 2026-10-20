from flask import Blueprint, jsonify, request

from backend.errors import APIError
from backend.routes.validation import pagination, query_params
from backend.services import ingredient_service

bp = Blueprint("ingredients", __name__, url_prefix="/api")


@bp.get("/ingredients")
def search():
    query_params({"name", "limit", "offset"})
    name = request.args.get("name", "").strip()
    if not 1 <= len(name) <= 150:
        raise APIError("name must contain 1 to 150 characters.")
    limit, offset = pagination(default=20)
    return jsonify(ingredients=ingredient_service.search(name, limit, offset),
                   limit=limit, offset=offset)
