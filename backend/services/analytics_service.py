from backend.db import session
from backend.services.common import demo_user
from backend.sql import queries


def preferences():
    with session() as db:
        return db.all(queries.PREFERENCES, (demo_user(db),))
