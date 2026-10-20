"""Opt-in, read-only checks against the existing populated database."""

import os
import re
from pathlib import Path

import pytest

from backend.app import create_app
from backend.db import session
from backend.explorer_metadata import RELATIONSHIPS, TABLES
from backend.sql import explorer_queries

pytestmark = pytest.mark.skipif(
    os.getenv("FOODWISE_RUN_LIVE_SMOKE") != "1",
    reason="Set FOODWISE_RUN_LIVE_SMOKE=1 with DB_* for populated-database reads.",
)


@pytest.fixture(scope="module")
def explorer_live_client():
    app = create_app({"TESTING": True})
    client = app.test_client()
    before = (client.get("/api/pantry?limit=100").json, client.get("/api/favorites?limit=100").json)
    yield client
    after = (client.get("/api/pantry?limit=100").json, client.get("/api/favorites?limit=100").json)
    assert after == before, "Read-only explorer must preserve full demo records, including timestamps."


@pytest.mark.parametrize("key", list(explorer_queries.SQL))
def test_live_explorer(explorer_live_client, key):
    response = explorer_live_client.post(f"/api/query-explorer/{key}/explain", json={})
    assert response.status_code == 200, response.json
    data = response.json
    assert "actual time=" in data["plan"]["analyze_tree"]
    assert data["plan"]["access_paths"]
    assert data["results"]["rows"]
    if key == "pantry_match":
        assert data["results"]["rows"] == explorer_live_client.get("/api/recommendations/pantry?limit=20").json["recipes"]
    elif key == "smart_filter":
        expected = explorer_live_client.get("/api/recipes?max_minutes=60&max_calories=700&min_protein=10&limit=20").json["recipes"]
        assert data["results"]["rows"] == expected
    elif key == "missing_ingredients":
        recipe_id = data["parameters"]["recipe_id"]
        expected = explorer_live_client.get(f"/api/recipes/{recipe_id}/missing-ingredients").json["missing_ingredients"]
        assert data["results"]["rows"] == expected[:20]
    elif key == "favorite_preferences":
        assert data["results"]["rows"] == explorer_live_client.get("/api/analytics/preferences").json["preferences"]


def test_live_usda_equivalent_to_original_day5(explorer_live_client):
    # Compare the complete filtered results by food ID, avoiding arbitrary order
    # between tied rows at the preview boundary. All aggregation stays in MySQL.
    source = (Path(__file__).resolve().parents[2] / "FoodWise_Day5_Complex_Queries.sql").read_text(encoding="utf-8")
    section = source.split("-- QUERY 6", 1)[1]
    original = section[section.index("WITH food_macros AS"):].strip()
    original = re.sub(r"LIMIT 30;\s*$", "", original)
    optimized = re.sub(r"LIMIT %s\s*$", "", explorer_queries.USDA_COMPARISON)
    with explorer_live_client.application.app_context(), session(readonly=True) as db:
        # Longer verification budget for the unoptimized reference only.
        db.execute("SET SESSION max_execution_time = 60000")
        expected = db.all(original)
        actual = db.all(optimized, (20,))
    assert expected
    assert {row["fdc_id"]: row for row in actual} == {row["fdc_id"]: row for row in expected}


def test_live_erd_matches_database(explorer_live_client):
    with explorer_live_client.application.app_context(), session(readonly=True) as db:
        rows = db.all("""
            SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
        """)
        tables = db.all("SELECT TABLE_NAME FROM information_schema.tables WHERE TABLE_SCHEMA = DATABASE()")
    assert {row["TABLE_NAME"] for row in tables} == {t["name"] for t in TABLES}
    assert {(f"{r['TABLE_NAME']}.{r['COLUMN_NAME']}",
             f"{r['REFERENCED_TABLE_NAME']}.{r['REFERENCED_COLUMN_NAME']}") for r in rows} == {
        (r["source"], r["target"]) for r in RELATIONSHIPS}
