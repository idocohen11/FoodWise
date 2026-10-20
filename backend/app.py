"""Run from the repository root: python -m backend.app."""

from datetime import date, datetime
from decimal import Decimal

from flask import Flask, jsonify
from flask.json.provider import DefaultJSONProvider
from werkzeug.exceptions import HTTPException

from backend.config import load_config
from backend.db import session
from backend.errors import APIError, DatabaseError
from backend.routes import analytics, favorites, pantry, recipes
from backend.sql import queries


class FoodWiseJSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(value):
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return DefaultJSONProvider.default(value)


def create_app(test_config=None):
    app = Flask(__name__)
    app.json = FoodWiseJSONProvider(app)
    app.config.update(load_config())
    if test_config:
        app.config.update(test_config)

    for blueprint in (recipes.bp, pantry.bp, favorites.bp, analytics.bp):
        app.register_blueprint(blueprint)

    @app.get("/api/health")
    def health():
        with session() as db:
            db.one(queries.HEALTH)
        return jsonify(status="ok", database="connected")

    @app.errorhandler(APIError)
    def api_error(error):
        return jsonify(error={"message": error.message}), error.status

    @app.errorhandler(DatabaseError)
    def database_error(error):
        return jsonify(error={"message": "The database request could not be completed. Please try again later."}), 500

    @app.errorhandler(HTTPException)
    def http_error(error):
        messages = {
            400: "Invalid request or malformed JSON.",
            404: "Endpoint not found.",
            405: "Method not allowed.",
            413: "Request body is too large.",
        }
        response = error.get_response()
        response.data = app.json.dumps({"error": {"message": messages.get(error.code, "Request could not be completed.")}})
        response.content_type = "application/json"
        return response

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.error("Unexpected request failure (%s)", type(error).__name__)
        return jsonify(error={"message": "An unexpected error occurred. Please try again later."}), 500

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
