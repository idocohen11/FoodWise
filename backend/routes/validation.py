import re
from decimal import Decimal, InvalidOperation

from flask import request

from backend.errors import APIError

MAX_ID = 9223372036854775807


def integer(value, name, minimum=1, maximum=MAX_ID):
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]{1,19}", str(value)):
        raise APIError(f"{name} must be an integer between {minimum} and {maximum}.")
    value = int(value)
    if not minimum <= value <= maximum:
        raise APIError(f"{name} must be between {minimum} and {maximum}.")
    return value


def number(value, name, maximum=Decimal("99999999.99"), places=None):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise APIError(f"{name} must be a non-negative number.")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        raise APIError(f"{name} must be a non-negative number.") from None
    if not parsed.is_finite() or not 0 <= parsed <= maximum:
        raise APIError(f"{name} must be between 0 and {maximum}.")
    if places is not None and parsed != parsed.quantize(Decimal(10) ** -places):
        raise APIError(f"{name} must have at most {places} decimal places.")
    return parsed


def query_params(allowed):
    for key in request.args:
        if key not in allowed:
            raise APIError(f"Unsupported query parameter: {key}.")
        if len(request.args.getlist(key)) != 1:
            raise APIError(f"Query parameter {key} must appear only once.")


def pagination(default=30):
    return (
        integer(request.args.get("limit", default), "limit", maximum=100),
        integer(request.args.get("offset", 0), "offset", minimum=0, maximum=2147483647),
    )


def search_filters():
    query_params({"name", "country", "category", "max_minutes", "max_calories",
                  "min_protein", "limit", "offset"})
    filters = {}
    for key, max_length in (("name", 200), ("country", 100), ("category", 100)):
        value = request.args.get(key)
        if value is not None:
            value = value.strip()
            if not value or len(value) > max_length:
                raise APIError(f"{key} must contain 1 to {max_length} characters.")
        filters[key] = value
    if filters["name"] is not None:
        value = filters["name"].replace("!", "!!").replace("%", "!%").replace("_", "!_")
        filters["name"] = f"%{value}%"
    for key in ("max_minutes", "max_calories", "min_protein"):
        value = request.args.get(key)
        filters[key] = number(value, key) if value is not None else None
    filters["limit"], filters["offset"] = pagination()
    return filters


def pantry_body():
    if not request.is_json:
        raise APIError("Send a JSON object with Content-Type: application/json.")
    body = request.get_json()
    if not isinstance(body, dict):
        raise APIError("Request body must be a JSON object.")
    if set(body) - {"ingredient_id", "quantity", "unit"}:
        raise APIError("Allowed fields are ingredient_id, quantity, and unit.")
    ingredient_id = integer(body.get("ingredient_id"), "ingredient_id")
    quantity = body.get("quantity")
    if quantity is not None:
        quantity = number(quantity, "quantity", maximum=Decimal("9999999.999"), places=3)
    unit = body.get("unit")
    if unit is not None:
        if not isinstance(unit, str) or not unit.strip() or len(unit.strip()) > 50:
            raise APIError("unit must contain 1 to 50 characters, or be null.")
        unit = unit.strip()
    return ingredient_id, quantity, unit
