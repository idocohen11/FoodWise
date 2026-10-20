from flask import Blueprint, jsonify

from backend.routes.validation import integer, pagination, query_params, search_filters
from backend.services import recipe_service

bp = Blueprint("recipes", __name__, url_prefix="/api")


@bp.get("/recipes")
def search():
    filters = search_filters()
    return jsonify(recipes=recipe_service.search(filters),
                   limit=filters["limit"], offset=filters["offset"])


@bp.get("/recipes/<recipe_id>")
def details(recipe_id):
    return jsonify(recipe_service.details(integer(recipe_id, "recipe_id")))


@bp.get("/recommendations/pantry")
def pantry_match():
    query_params({"limit", "offset"})
    limit, offset = pagination(default=20)
    return jsonify(recipes=recipe_service.pantry_match(limit, offset), limit=limit, offset=offset)


@bp.get("/recipes/<recipe_id>/missing-ingredients")
def missing_ingredients(recipe_id):
    recipe_id = integer(recipe_id, "recipe_id")
    return jsonify(recipe_id=recipe_id,
                   missing_ingredients=recipe_service.missing_ingredients(recipe_id))
