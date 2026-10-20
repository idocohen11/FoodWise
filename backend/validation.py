"""HTTP-independent scalar validation shared by routes and application services."""

import re
from decimal import Decimal, InvalidOperation

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
