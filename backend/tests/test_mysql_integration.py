"""Opt-in real MySQL tests. Only an EMPTY, separately provisioned *_test DB is used."""

import os
import re
from pathlib import Path

import mysql.connector
import pytest

from backend.app import create_app

pytestmark = pytest.mark.skipif(
    os.getenv("FOODWISE_RUN_INTEGRATION") != "1",
    reason="Set FOODWISE_RUN_INTEGRATION=1 and TEST_DB_* for disposable MySQL.",
)


@pytest.fixture(scope="module")
def mysql_config():
    name = os.environ["TEST_DB_NAME"]
    if not re.fullmatch(r"[a-zA-Z0-9_]+_test", name):
        pytest.fail("TEST_DB_NAME must be a simple identifier ending in _test.")
    config = {
        "host": os.environ["TEST_DB_HOST"],
        "port": int(os.getenv("TEST_DB_PORT", "3306")),
        "user": os.getenv("TEST_DB_USER", "root"),
        "password": os.environ["TEST_DB_PASSWORD"],
    }
    connection = mysql.connector.connect(**config)
    try:
        cur = connection.cursor()
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s", (name,))
        if cur.fetchone()[0]:
            pytest.fail("Integration tests require an empty disposable database.")
        schema = (Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8")
        # Execute the project's original schema, changing only the test DB name.
        for statement in schema.replace("foodwise", name).split(";"):
            if statement.strip():
                cur.execute(statement)
                if cur.with_rows:
                    cur.fetchall()
        cur.execute("INSERT INTO countries VALUES ('ES', 'Spain'), ('KE', 'Kenya')")
        cur.execute("INSERT INTO recipe_categories (category_id, name) VALUES (1, 'main'), (2, 'dessert')")
        cur.execute("""
            INSERT INTO recipes
                (recipe_id, source_slug, name, country_code, category_id,
                 prep_minutes, cook_minutes, calories_per_serving, protein_g_per_serving)
            VALUES (1, 'test-one', 'Test stew', 'ES', 1, 10, 20, 300, 20),
                   (2, 'test-two', 'Test cake', 'KE', 2, 5, 45, 600, 5),
                   (3, 'test-three', 'Test empty', NULL, NULL, NULL, NULL, NULL, NULL),
                   (4, 'test-four', 'Test soup', 'ES', 1, NULL, NULL, NULL, NULL)
        """)
        cur.execute("INSERT INTO ingredients (ingredient_id, name) VALUES (1, 'Flour'), (2, 'Salt'), (3, 'Sugar')")
        cur.execute("""
            INSERT INTO recipe_ingredients (recipe_id, ingredient_id, line_no, quantity, unit)
            VALUES (1, 1, 1, 2, 'cups'), (1, 1, 2, 1, 'cups'), (1, 2, 3, 1, 'tsp'),
                   (2, 1, 1, 2, 'cups'), (2, 3, 2, 1, 'cups'), (4, 2, 1, 1, 'tsp')
        """)
        cur.execute("""
            INSERT INTO recipe_steps (recipe_id, step_no, instruction)
            VALUES (1, 2, 'Cook.'), (1, 1, 'Mix.')
        """)
        cur.execute("INSERT INTO users (username) VALUES ('other_user')")
        connection.commit()
        cur.close()
    finally:
        connection.close()
    return {**config, "database": name}


@pytest.fixture
def live_client(mysql_config):
    connection = mysql.connector.connect(**mysql_config)
    try:
        cur = connection.cursor()
        cur.execute("DELETE FROM pantry")
        cur.execute("DELETE FROM favorites")
        cur.execute("""
            INSERT INTO pantry (user_id, ingredient_id, quantity, unit)
            SELECT user_id, 1, 0, 'cups' FROM users WHERE username = 'demo_user'
        """)
        cur.execute("""
            INSERT INTO pantry (user_id, ingredient_id, quantity, unit)
            SELECT user_id, 2, 1, 'tsp' FROM users WHERE username = 'other_user'
        """)
        cur.execute("""
            INSERT INTO favorites (user_id, recipe_id)
            SELECT u.user_id, r.recipe_id FROM users u CROSS JOIN recipes r
            WHERE u.username = 'demo_user' AND r.recipe_id IN (1, 4)
        """)
        connection.commit()
        cur.close()
    finally:
        connection.close()
    app = create_app({
        "TESTING": True,
        **{"DB_" + k.upper(): v for k, v in mysql_config.items() if k != "database"},
        "DB_NAME": mysql_config["database"],
    })
    return app.test_client()


def test_mysql_health(live_client):
    assert live_client.get("/api/health").json == {"status": "ok", "database": "connected"}


def test_mysql_search_filters_and_pagination(live_client):
    response = live_client.get("/api/recipes?name=stew&country=Spain&category=main&max_minutes=30&max_calories=300&min_protein=20")
    assert response.status_code == 200
    assert [r["recipe_id"] for r in response.json["recipes"]] == [1]
    assert live_client.get("/api/recipes?country=ES").json["recipes"][0]["recipe_id"] == 1
    assert live_client.get("/api/recipes?max_minutes=29&min_protein=1").json["recipes"] == []
    assert live_client.get("/api/recipes?max_calories=299").json["recipes"] == []
    assert live_client.get("/api/recipes?min_protein=21").json["recipes"] == []
    assert live_client.get("/api/recipes?limit=1&offset=1").json["recipes"][0]["recipe_id"] == 2
    assert live_client.get("/api/recipes", query_string={"name": "' OR 1=1 --"}).json["recipes"] == []
    assert live_client.get("/api/recipes?name=%25").json["recipes"] == []


def test_mysql_details(live_client):
    response = live_client.get("/api/recipes/1")
    assert response.status_code == 200
    assert response.json["country"] == "Spain"
    assert response.json["category"] == "main"
    assert len(response.json["ingredients"]) == 3
    assert [s["step_no"] for s in response.json["steps"]] == [1, 2]
    assert live_client.get("/api/recipes/999").status_code == 404
    assert live_client.get("/api/recipes/3").json["ingredients"] == []


def test_mysql_pantry_crud(live_client):
    assert [i["ingredient_id"] for i in live_client.get("/api/pantry").json["pantry"]] == [1]
    body = {"ingredient_id": 2, "quantity": 2.125, "unit": "pcs"}
    assert live_client.post("/api/pantry", json=body).status_code == 200
    body["quantity"] = 3
    assert live_client.post("/api/pantry", json=body).status_code == 200
    items = live_client.get("/api/pantry").json["pantry"]
    assert len(items) == 2
    assert items[1]["quantity"] == 3
    assert live_client.delete("/api/pantry/2").status_code == 204
    assert live_client.delete("/api/pantry/2").status_code == 404
    assert live_client.post("/api/pantry", json={"ingredient_id": 999}).status_code == 404


def test_mysql_pantry_match_distinct_presence_and_order(live_client):
    response = live_client.get("/api/recommendations/pantry")
    assert response.status_code == 200
    rows = response.json["recipes"]
    assert [r["recipe_id"] for r in rows] == [2, 1, 4]  # Name breaks the 50% tie.
    assert rows[1]["total_ingredients"] == 2  # Duplicate flour lines count once.
    assert rows[1]["ingredients_in_pantry"] == 1  # Zero quantity still means presence (Day 5).
    assert rows[1]["missing_ingredients"] == 1
    assert rows[1]["pantry_match_percent"] == 50
    assert rows[2]["pantry_match_percent"] == 0  # Other user's salt is excluded.
    assert live_client.post("/api/pantry", json={"ingredient_id": 2}).status_code == 200
    rows = live_client.get("/api/recommendations/pantry").json["recipes"]
    assert [r["recipe_id"] for r in rows] == [4, 1, 2]
    assert rows[0]["pantry_match_percent"] == 100
    assert live_client.get("/api/recommendations/pantry?limit=1&offset=1").json["recipes"][0]["recipe_id"] == 1
    assert live_client.delete("/api/pantry/1").status_code == 204
    assert live_client.delete("/api/pantry/2").status_code == 204
    assert all(r["pantry_match_percent"] == 0 for r in live_client.get("/api/recommendations/pantry").json["recipes"])


def test_mysql_missing_ingredients(live_client):
    response = live_client.get("/api/recipes/1/missing-ingredients")
    assert response.status_code == 200
    assert [i["ingredient_id"] for i in response.json["missing_ingredients"]] == [2]
    assert live_client.post("/api/pantry", json={"ingredient_id": 2}).status_code == 200
    assert live_client.get("/api/recipes/1/missing-ingredients").json["missing_ingredients"] == []
    assert live_client.get("/api/recipes/999/missing-ingredients").status_code == 404


def test_mysql_favorites_crud(live_client):
    assert len(live_client.get("/api/favorites").json["favorites"]) == 2
    assert live_client.post("/api/favorites/2").status_code == 200
    assert live_client.post("/api/favorites/2").status_code == 200
    assert len(live_client.get("/api/favorites").json["favorites"]) == 3
    assert live_client.delete("/api/favorites/2").status_code == 204
    assert live_client.delete("/api/favorites/2").status_code == 404
    assert live_client.post("/api/favorites/999").status_code == 404


def test_mysql_analytics_averages_and_empty_results(live_client):
    response = live_client.get("/api/analytics/preferences")
    assert response.status_code == 200
    assert response.json["preferences"] == [{
        "category": "main", "favorite_count": 2, "avg_calories": 300,
        "avg_protein_g": 20, "avg_total_minutes": 15,
    }]
    assert live_client.post("/api/favorites/3").status_code == 200
    rows = live_client.get("/api/analytics/preferences").json["preferences"]
    assert rows[1] == {"category": None, "favorite_count": 1, "avg_calories": None,
                       "avg_protein_g": None, "avg_total_minutes": 0}
    for recipe_id in (1, 3, 4):
        assert live_client.delete(f"/api/favorites/{recipe_id}").status_code == 204
    assert live_client.get("/api/analytics/preferences").json["preferences"] == []
