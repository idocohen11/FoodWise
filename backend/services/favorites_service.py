from backend.db import session
from backend.errors import APIError
from backend.services.common import demo_user, require_recipe
from backend.sql import queries


def list_items(limit, offset):
    with session() as db:
        return db.all(queries.FAVORITES_LIST, (demo_user(db), limit, offset))


def add(recipe_id):
    with session(write=True) as db:
        user_id = demo_user(db)
        require_recipe(db, recipe_id)
        db.execute(queries.FAVORITES_ADD, (user_id, recipe_id, recipe_id))
    return {"recipe_id": recipe_id, "status": "saved"}


def delete(recipe_id):
    with session(write=True) as db:
        if db.execute(queries.FAVORITES_DELETE, (demo_user(db), recipe_id)) == 0:
            raise APIError("Favorite not found.", 404)
