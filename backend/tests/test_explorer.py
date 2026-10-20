import json
import re

import mysql.connector
import pytest

from backend.db import session
from backend.explorer_metadata import DEFINITIONS, TABLES, RELATIONSHIPS, QUERY_JOINS
from backend.services.explorer_service import parse_tree
from backend.sql import explorer_queries, queries


def test_catalog_metadata_and_exact_sql(client, connector):
    response = client.get("/api/query-explorer/queries")
    assert response.status_code == 200
    data = response.json
    assert len(data["queries"]) == 6
    assert len(data["schema"]["tables"]) == 14
    assert len(data["schema"]["relationships"]) == 14
    for item in data["queries"]:
        assert item["sql"] == explorer_queries.SQL[item["key"]].strip()
        assert client.get("/api/query-explorer/" + item["key"]).json == item
    connector.assert_not_called()


@pytest.mark.parametrize("key", ["SELECT", "DROP", "delete", "pantry_match;DELETE", "not_a_query"])
def test_unknown_keys_never_connect(client, connector, key):
    assert client.get(f"/api/query-explorer/{key}").status_code == 404
    assert client.post(f"/api/query-explorer/{key}/explain", json={}).status_code == 404
    connector.assert_not_called()


@pytest.mark.parametrize("body", [
    {"sql": "DELETE FROM pantry"}, {"query": "SELECT 1"}, {"parameters": {"sql": "DROP TABLE users"}},
    {"parameters": {"user_id": 1}}, {"parameters": {"limit": 999999}}, {"parameters": []},
    {"parameters": None}, [], "DELETE FROM favorites",
])
def test_no_raw_sql_or_extra_parameters(client, connector, body):
    response = client.post("/api/query-explorer/pantry_match/explain", json=body)
    assert response.status_code == 400
    connector.assert_not_called()


@pytest.mark.parametrize("key,params", [
    ("smart_filter", {"max_minutes": -1}), ("smart_filter", {"min_protein": "NaN"}),
    ("smart_filter", {"country": ["ES"]}), ("smart_filter", {"name": "a" * 201}),
    ("missing_ingredients", {"recipe_id": True}), ("missing_ingredients", {"recipe_id": 0}),
    ("missing_ingredients", {"recipe_id": "1 OR 1=1"}), ("usda_comparison", {"min_protein": None}),
])
def test_invalid_inputs_never_connect(client, connector, key, params):
    assert client.post(f"/api/query-explorer/{key}/explain", json={"parameters": params}).status_code == 400
    connector.assert_not_called()


def test_bad_http_requests(client, connector):
    assert client.post("/api/query-explorer/pantry_match/explain", data="SELECT 1").status_code == 400
    assert client.post("/api/query-explorer/pantry_match/explain?sql=SELECT", json={}).status_code == 400
    assert client.get("/api/query-explorer/queries?sql=SELECT").status_code == 400
    assert client.post("/api/query-explorer/pantry_match/explain", data="{", content_type="application/json").status_code == 400
    assert client.delete("/api/query-explorer/pantry_match").status_code == 405
    connector.assert_not_called()


def prepare_cursor(connector):
    cursor = connector.return_value.cursor.return_value
    def execute(sql, params):
        if sql.startswith("EXPLAIN ANALYZE"):
            cursor.fetchone.return_value = {"EXPLAIN": "-> Limit: 20 row(s)  (cost=2 rows=3) (actual time=0.1..0.4 rows=3 loops=1)\n"}
        elif sql.startswith("EXPLAIN FORMAT=JSON"):
            cursor.fetchone.return_value = {"EXPLAIN": json.dumps({"query_block": {"table": {
                "table_name": "r", "access_type": "index", "key": "PRIMARY",
                "rows_examined_per_scan": 3, "filtered": "100.00",
            }}})}
        elif sql == queries.DEMO_USER:
            cursor.fetchone.return_value = {"user_id": 7}
        else:
            cursor.fetchone.return_value = {"recipe_id": 1}
        cursor.fetchall.return_value = [{"recipe_id": 1, "missing_ingredients": 1}]
    cursor.execute.side_effect = execute
    return cursor


@pytest.mark.parametrize("key", list(explorer_queries.SQL))
def test_explain_uses_same_fixed_sql_and_bindings_in_readonly_transaction(client, connector, key):
    cursor = prepare_cursor(connector)
    response = client.post(f"/api/query-explorer/{key}/explain", json={})
    assert response.status_code == 200, response.json
    data = response.json
    assert data["plan"]["root_metrics"]["last_row_ms"] == .4
    assert data["plan"]["access_paths"][0]["key"] == "PRIMARY"
    assert data["results"]["rows"] == [{"recipe_id": 1, "missing_ingredients": 1}]
    calls = cursor.execute.call_args_list[-3:]
    sql = explorer_queries.SQL[key]
    assert [call.args[0] for call in calls] == [
        "EXPLAIN ANALYZE FORMAT=TREE " + sql, "EXPLAIN FORMAT=JSON " + sql, sql,
    ]
    assert calls[0].args[1] == calls[1].args[1] == calls[2].args[1]
    connector.return_value.start_transaction.assert_called_once_with(readonly=True)
    connector.return_value.commit.assert_not_called()
    connector.return_value.rollback.assert_called()
    connector.return_value.close.assert_called_once()


def test_injection_is_only_a_bound_string(client, connector):
    cursor = prepare_cursor(connector)
    payload = "'; DELETE FROM pantry; --%_!"
    response = client.post("/api/query-explorer/smart_filter/explain", json={"parameters": {"name": payload}})
    assert response.status_code == 200
    for call in cursor.execute.call_args_list:
        assert "DELETE FROM" not in call.args[0]
    params = cursor.execute.call_args_list[-1].args[1]
    assert params["name"] == "%'; DELETE FROM pantry; --!%!_!!%"


def test_database_failure_is_safe_and_rolls_back(client, connector):
    connector.return_value.cursor.return_value.execute.side_effect = mysql.connector.Error("private sql password", errno=3024)
    response = client.post("/api/query-explorer/usda_comparison/explain", json={})
    assert response.status_code == 500
    assert "password" not in response.get_data(as_text=True)
    connector.return_value.rollback.assert_called()
    connector.return_value.close.assert_called_once()


def test_readonly_cannot_be_combined_with_write(app, connector):
    with app.app_context(), pytest.raises(ValueError):
        with session(write=True, readonly=True):
            pass
    connector.assert_not_called()


def test_parser_omits_unknown_metrics_and_handles_scientific_notation():
    raw = "-> Filter: ('actual time=fake') (cost=2 rows=1e+3) (actual time=2e-3..1.2e+1 rows=2.5 loops=4)\n    -> Never executed (never executed)"
    nodes, metrics = parse_tree(raw)
    assert metrics == {"first_row_ms": .002, "last_row_ms": 12, "actual_rows_per_loop": 2.5, "loops": 4, "estimated_rows": 1000}
    assert "actual_rows_per_loop" not in nodes[1]
    assert parse_tree("unrecognized future plan") == ([], {})


def test_registry_and_metadata_are_select_only_and_consistent():
    tables = {item["name"] for item in TABLES}
    edges = {item["id"]: item for item in RELATIONSHIPS + QUERY_JOINS}
    assert set(DEFINITIONS) == set(explorer_queries.SQL)
    for key, sql in explorer_queries.SQL.items():
        assert sql.lstrip().startswith(("SELECT", "WITH"))
        assert ";" not in sql
        assert not re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|CALL|INTO|OUTFILE|SLEEP)\b", sql, re.I)
        meta = DEFINITIONS[key]
        assert set(meta["tables"]) <= tables
        for relationship in meta["relationships"]:
            assert edges[relationship]["source"].split(".")[0] in meta["tables"]
            assert edges[relationship]["target"].split(".")[0] in meta["tables"]
        for step in meta["steps"]:
            assert set(step["tables"]) <= set(meta["tables"])
            assert set(step["relationships"]) <= set(meta["relationships"])
            assert all(clause in sql for clause in step["clauses"])
    with pytest.raises(TypeError):
        explorer_queries.SQL["custom"] = "SELECT 1"
