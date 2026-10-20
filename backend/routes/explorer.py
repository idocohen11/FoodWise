from flask import Blueprint, jsonify, request

from backend.errors import APIError
from backend.routes.validation import query_params
from backend.services import explorer_service

bp = Blueprint("query_explorer", __name__, url_prefix="/api/query-explorer")


@bp.get("/queries")
def catalog():
    query_params(set())
    return jsonify(explorer_service.catalog())


@bp.get("/<query_key>")
def details(query_key):
    query_params(set())
    return jsonify(explorer_service.definition(query_key))


@bp.post("/<query_key>/explain")
def explain(query_key):
    explorer_service.definition(query_key)
    query_params(set())
    if not request.is_json:
        raise APIError("Send a JSON object with Content-Type: application/json.")
    body = request.get_json()
    if not isinstance(body, dict) or set(body) - {"parameters"}:
        raise APIError("Only a JSON object containing parameters is accepted. SQL cannot be submitted.")
    return jsonify(explorer_service.explain(query_key, body.get("parameters", {})))
