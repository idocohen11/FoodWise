from datetime import datetime
from decimal import Decimal

import mysql.connector
import pytest

from backend.sql import queries


def cursor(connector):
    return connector.return_value.cursor.return_value


def test_health(client, connector):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok", "database": "connected"}
    cursor(connector).execute.assert_called_with(queries.HEALTH, ())
    connector.return_value.close.assert_called_once()


def test_search_all_filters_are_bound(client, connector):
    cursor(connector).fetchall.return_value = [{"recipe_id": 1, "calories_per_serving": Decimal("210.50")}]
    response = client.get("/api/recipes", query_string={
        "name": "chef's 100%_!", "country": "ES", "category": "main",
        "max_minutes": 60, "max_calories": 700, "min_protein": 10,
        "limit": 4, "offset": 2,
    })
    assert response.status_code == 200
    assert response.json["recipes"][0]["calories_per_serving"] == 210.5
    sql, params = cursor(connector).execute.call_args.args
    assert sql == queries.RECIPE_SEARCH
    assert "chef" not in sql
    assert params == {
        "name": "%chef's 100!%!_!!%", "country": "ES", "category": "main",
        "max_minutes": Decimal(60), "max_calories": Decimal(700),
        "min_protein": Decimal(10), "limit": 4, "offset": 2,
    }


def test_search_defaults_and_empty_results(client, connector):
    response = client.get("/api/recipes")
    assert response.json == {"recipes": [], "limit": 30, "offset": 0}
    assert cursor(connector).execute.call_args.args[1]["name"] is None


def test_recipe_details(client, connector):
    cursor(connector).fetchone.return_value = {"recipe_id": 1, "country": "Spain", "category": "main"}
    cursor(connector).fetchall.side_effect = [
        [{"ingredient_id": 2, "quantity": Decimal("2.000")}],
        [{"step_no": 1, "instruction": "Mix."}],
    ]
    response = client.get("/api/recipes/1")
    assert response.status_code == 200
    assert response.json["ingredients"][0]["quantity"] == 2
    assert response.json["steps"][0]["instruction"] == "Mix."


@pytest.mark.parametrize("path,key", [
    ("/api/pantry", "pantry"),
    ("/api/recommendations/pantry", "recipes"),
    ("/api/recipes/1/missing-ingredients", "missing_ingredients"),
    ("/api/favorites", "favorites"),
    ("/api/analytics/preferences", "preferences"),
])
def test_user_read_endpoints(client, connector, path, key):
    cursor(connector).fetchall.return_value = [{"value": Decimal("75.0"), "updated_at": datetime(2026, 1, 2)}]
    response = client.get(path)
    assert response.status_code == 200
    assert response.json[key][0] == {"value": 75, "updated_at": "2026-01-02T00:00:00"}
    assert cursor(connector).execute.call_args_list[0].args == (queries.DEMO_USER, ("demo_user",))
    assert not connector.return_value.commit.called


def test_pantry_upsert_commits(client, connector):
    response = client.post("/api/pantry", json={"ingredient_id": 123, "quantity": 2, "unit": "pcs"})
    assert response.status_code == 200
    assert response.json == {"ingredient_id": 123, "quantity": 2, "unit": "pcs"}
    cursor(connector).execute.assert_called_with(
        queries.PANTRY_UPSERT, (7, 123, Decimal(2), "pcs", Decimal(2), "pcs"))
    connector.return_value.commit.assert_called_once()


def test_pantry_unknown_quantity_allowed(client, connector):
    response = client.post("/api/pantry", json={"ingredient_id": 123})
    assert response.status_code == 200
    assert response.json["quantity"] is None
    assert response.json["unit"] is None


def test_favorite_add_commits(client, connector):
    assert client.post("/api/favorites/123").status_code == 200
    cursor(connector).execute.assert_called_with(queries.FAVORITES_ADD, (7, 123, 123))
    connector.return_value.commit.assert_called_once()


@pytest.mark.parametrize("path", ["/api/pantry/123", "/api/favorites/123"])
def test_delete_commits(client, connector, path):
    response = client.delete(path)
    assert response.status_code == 204
    assert response.data == b""
    connector.return_value.commit.assert_called_once()


@pytest.mark.parametrize("path", ["/api/pantry/123", "/api/favorites/123"])
def test_delete_missing_is_404(client, connector, path):
    cursor(connector).rowcount = 0
    assert client.delete(path).status_code == 404
    connector.return_value.commit.assert_not_called()
    connector.return_value.rollback.assert_called()


def test_missing_recipe(client, connector):
    cursor(connector).fetchone.return_value = None
    assert client.get("/api/recipes/999").status_code == 404


@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/recipes/999/missing-ingredients", None),
    ("post", "/api/favorites/999", None),
    ("post", "/api/pantry", {"ingredient_id": 999}),
])
def test_missing_related_record(client, connector, method, path, body):
    cursor(connector).fetchone.side_effect = [{"user_id": 7}, None]
    assert getattr(client, method)(path, json=body).status_code == 404
    connector.return_value.commit.assert_not_called()


def test_missing_demo_user(client, connector):
    cursor(connector).fetchone.return_value = None
    assert client.get("/api/pantry").status_code == 404


@pytest.mark.parametrize("query", [
    "max_minutes=-1", "max_minutes=abc", "max_calories=NaN",
    "min_protein=Infinity", "limit=0", "limit=101", "offset=-1",
    "limit=1.5", "name=", "country=", "category=",
    "max_minutes=1&max_minutes=2", "unknown=1", "max_calories=1e100",
])
def test_invalid_search_never_connects(client, connector, query):
    assert client.get("/api/recipes?" + query).status_code == 400
    connector.assert_not_called()


@pytest.mark.parametrize("body", [
    [], None, {}, {"ingredient_id": True}, {"ingredient_id": -1},
    {"ingredient_id": 1.2}, {"ingredient_id": 9223372036854775808},
    {"ingredient_id": 1, "quantity": -1}, {"ingredient_id": 1, "quantity": "NaN"},
    {"ingredient_id": 1, "quantity": True}, {"ingredient_id": 1, "quantity": []},
    {"ingredient_id": 1, "quantity": 10000000},
    {"ingredient_id": 1, "quantity": "0.0001"},
    {"ingredient_id": 1, "unit": 3}, {"ingredient_id": 1, "unit": ""},
    {"ingredient_id": 1, "unit": "x" * 51}, {"ingredient_id": 1, "user_id": 100},
])
def test_invalid_pantry_body_never_connects(client, connector, body):
    assert client.post("/api/pantry", json=body).status_code == 400
    connector.assert_not_called()


@pytest.mark.parametrize("path", ["/api/recipes/abc", "/api/recipes/-1", "/api/recipes/0"])
def test_invalid_ids(client, connector, path):
    assert client.get(path).status_code == 400
    connector.assert_not_called()


def test_malformed_json(client):
    response = client.post("/api/pantry", data='{"ingredient_id":', content_type="application/json")
    assert response.status_code == 400
    assert response.is_json


def test_json_http_errors(client):
    assert client.get("/unknown").status_code == 404
    assert client.get("/unknown").is_json
    response = client.patch("/api/pantry")
    assert response.status_code == 405
    assert "GET" in response.headers["Allow"]
    response = client.post("/api/pantry", data="x" * 17000, content_type="application/json")
    assert response.status_code == 413
    assert response.is_json


@pytest.mark.parametrize("stage", ["connect", "execute", "commit"])
def test_database_errors_are_safe_and_close_resources(client, connector, stage):
    error = mysql.connector.Error("secret-password SQL trace details", errno=2003)
    if stage == "connect":
        connector.side_effect = error
    elif stage == "execute":
        cursor(connector).execute.side_effect = error
    else:
        connector.return_value.commit.side_effect = error
    response = client.post("/api/favorites/123")
    assert response.status_code == 500
    assert "secret" not in response.get_data(as_text=True)
    assert "trace" not in response.get_data(as_text=True)
    if stage != "connect":
        connector.return_value.close.assert_called_once()
        connector.return_value.rollback.assert_called()


def test_missing_password_returns_safe_error(app, connector):
    app.config["DB_PASSWORD"] = None
    response = app.test_client().get("/api/health")
    assert response.status_code == 500
    connector.assert_not_called()


def test_unexpected_error_is_json(client, connector):
    cursor(connector).execute.side_effect = RuntimeError("secret internal failure")
    response = client.get("/api/health")
    assert response.status_code == 500
    assert "secret" not in response.get_data(as_text=True)
