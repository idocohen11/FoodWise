from backend.db import session
from backend.errors import APIError
from backend.services.common import demo_user
from backend.sql import queries


def list_items(limit, offset):
    with session() as db:
        return db.all(queries.PANTRY_LIST, (demo_user(db), limit, offset))


def save_item(ingredient_id, quantity, unit):
    with session(write=True) as db:
        user_id = demo_user(db)
        if db.one(queries.INGREDIENT_EXISTS, (ingredient_id,)) is None:
            raise APIError("Ingredient not found.", 404)
        db.execute(
            queries.PANTRY_UPSERT,
            (user_id, ingredient_id, quantity, unit, quantity, unit),
        )
    return {"ingredient_id": ingredient_id, "quantity": quantity, "unit": unit}


def delete_item(ingredient_id):
    with session(write=True) as db:
        if db.execute(queries.PANTRY_DELETE, (demo_user(db), ingredient_id)) == 0:
            raise APIError("Pantry ingredient not found.", 404)
