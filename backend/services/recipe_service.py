from backend.db import session
from backend.errors import APIError
from backend.services.common import demo_user, require_recipe
from backend.sql import queries


def search(filters):
    with session() as db:
        return db.all(queries.RECIPE_SEARCH, filters)


def details(recipe_id):
    with session() as db:
        recipe = db.one(queries.RECIPE_DETAILS, (recipe_id,))
        if recipe is None:
            raise APIError("Recipe not found.", 404)
        recipe["ingredients"] = db.all(queries.RECIPE_INGREDIENTS, (recipe_id,))
        recipe["steps"] = db.all(queries.RECIPE_STEPS, (recipe_id,))
        return recipe


def pantry_match(limit, offset):
    with session() as db:
        return db.all(queries.PANTRY_MATCH, (demo_user(db), limit, offset))


def missing_ingredients(recipe_id):
    with session() as db:
        user_id = demo_user(db)
        require_recipe(db, recipe_id)
        return db.all(queries.MISSING_INGREDIENTS, (user_id, recipe_id))
