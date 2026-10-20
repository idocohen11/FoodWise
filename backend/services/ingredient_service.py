from backend.db import session
from backend.sql import queries


def search(name, limit, offset):
    # Literal substring search: user input never changes the SQL.
    pattern = "%" + name.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
    with session() as db:
        return db.all(queries.INGREDIENT_SEARCH, (pattern, limit, offset))
