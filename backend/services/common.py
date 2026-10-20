from backend.errors import APIError
from backend.sql import queries


def demo_user(db):
    user = db.one(queries.DEMO_USER, ("demo_user",))
    if user is None:
        raise APIError("The demo user was not found. Load the existing demo seed data.", 404)
    return user["user_id"]


def require_recipe(db, recipe_id):
    if db.one(queries.RECIPE_EXISTS, (recipe_id,)) is None:
        raise APIError("Recipe not found.", 404)
