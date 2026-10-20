"""Optional read-only checks against an already populated database."""

import os

import pytest

from backend.app import create_app

pytestmark = pytest.mark.skipif(
    os.getenv("FOODWISE_RUN_LIVE_SMOKE") != "1",
    reason="Set FOODWISE_RUN_LIVE_SMOKE=1 and DB_* to check existing data read-only.",
)


@pytest.fixture(scope="module")
def existing_client():
    return create_app({"TESTING": True}).test_client()


@pytest.mark.parametrize("path,key", [
    ("/api/health", "database"),
    ("/api/recipes", "recipes"),
    ("/api/pantry", "pantry"),
    ("/api/recommendations/pantry", "recipes"),
    ("/api/favorites", "favorites"),
    ("/api/analytics/preferences", "preferences"),
])
def test_existing_database_reads(existing_client, path, key):
    response = existing_client.get(path)
    assert response.status_code == 200
    assert key in response.json


@pytest.mark.parametrize("suffix,key", [("", "steps"), ("/missing-ingredients", "missing_ingredients")])
def test_existing_recipe_reads(existing_client, suffix, key):
    response = existing_client.get("/api/recipes?limit=1")
    assert response.status_code == 200
    assert response.json["recipes"], "The live smoke database must contain recipes."
    recipe_id = response.json["recipes"][0]["recipe_id"]
    response = existing_client.get(f"/api/recipes/{recipe_id}{suffix}")
    assert response.status_code == 200
    assert isinstance(response.json[key], list)
