import pytest

from backend.sql import queries


def test_frontend_served_without_database(client, connector):
    response = client.get("/")
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"/assets/js/app.js" in response.data
    assert b"FoodWise" in response.data
    connector.assert_not_called()


@pytest.mark.parametrize("path,mimetype", [
    ("/assets/css/styles.css", "text/css"),
    ("/assets/js/app.js", "text/javascript"),
    ("/assets/favicon.svg", "image/svg+xml"),
])
def test_frontend_assets(client, connector, path, mimetype):
    response = client.get(path)
    assert response.status_code == 200
    assert response.mimetype in {mimetype, "application/javascript"}
    connector.assert_not_called()


def test_ingredient_search_uses_bound_literal_pattern(client, connector):
    cursor = connector.return_value.cursor.return_value
    cursor.fetchall.return_value = [{"ingredient_id": 1, "ingredient_name": "Salt"}]
    response = client.get("/api/ingredients", query_string={"name": "'%_!", "limit": 5, "offset": 10})
    assert response.status_code == 200
    assert response.json == {
        "ingredients": [{"ingredient_id": 1, "ingredient_name": "Salt"}],
        "limit": 5, "offset": 10,
    }
    cursor.execute.assert_called_once_with(queries.INGREDIENT_SEARCH, ("%'!%!_!!%", 5, 10))


@pytest.mark.parametrize("query", [
    "", "name=", "name=%20", "name=" + "x" * 151, "name=salt&limit=101",
    "name=salt&offset=-1", "name=a&name=b", "name=salt&user_id=1",
])
def test_ingredient_search_invalid_input(client, connector, query):
    assert client.get("/api/ingredients?" + query).status_code == 400
    connector.assert_not_called()


def test_ingredient_search_empty_results(client, connector):
    response = client.get("/api/ingredients?name=nonexistent")
    assert response.status_code == 200
    assert response.json == {"ingredients": [], "limit": 20, "offset": 0}


def test_static_path_cannot_read_backend(client, connector):
    assert client.get("/assets/../backend/config.py").status_code == 404
    connector.assert_not_called()
