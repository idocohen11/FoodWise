"""Fixed-key, read-only query execution and conservative MySQL plan extraction."""

import json
import re
from copy import deepcopy

from backend.db import session
from backend.errors import APIError
from backend.explorer_metadata import DEFINITIONS, TABLES, RELATIONSHIPS, QUERY_JOINS
from backend.validation import integer, number
from backend.services.common import demo_user, require_recipe
from backend.sql import explorer_queries, queries

PREVIEW_LIMIT = 20
BINDINGS = {
    "pantry_match": ["user_id", "limit", "offset"],
    "missing_ingredients": ["user_id", "recipe_id"],
    "smart_filter": None,  # Named placeholders already present in application SQL.
    "top_ingredients_country": ["limit"],
    "favorite_preferences": ["user_id"],
    "usda_comparison": ["min_protein", "limit"],
}


def definition(key):
    if key not in explorer_queries.SQL:
        raise APIError("Unknown predefined query.", 404)
    return {**deepcopy(DEFINITIONS[key]), "key": key,
            "sql": explorer_queries.SQL[key].strip(),
            "binding_order": BINDINGS[key],
            "lookup_sql": queries.DEMO_USER if DEFINITIONS[key].get("user_lookup") else None}


def catalog():
    return {
        "queries": [definition(key) for key in explorer_queries.SQL],
        "schema": {"tables": TABLES, "relationships": RELATIONSHIPS, "query_joins": QUERY_JOINS},
        "preview_limit": PREVIEW_LIMIT,
    }


def validate_parameters(key, supplied):
    spec = definition(key)["parameters"]  # Reject key before any DB access.
    if not isinstance(supplied, dict):
        raise APIError("parameters must be a JSON object.")
    if set(supplied) - set(spec):
        raise APIError("Only the predefined parameters for this query are accepted.")
    values = {}
    for name, field in spec.items():
        value = supplied.get(name, field["default"])
        if value is None or value == "":
            values[name] = None
        elif field["type"] == "integer":
            values[name] = integer(value, name)
        elif field["type"] == "number":
            values[name] = number(value, name)
        else:
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > field["max_length"]:
                raise APIError(f"{name} must contain 1 to {field['max_length']} characters.")
            values[name] = value.strip()
    if key == "usda_comparison" and values["min_protein"] is None:
        raise APIError("min_protein is required for USDA comparison.")
    return values


def bind_parameters(db, key, values):
    """No table names, clauses, SQL fragments, or usernames come from the client."""
    resolved = dict(values)
    if DEFINITIONS[key].get("user_lookup"):
        resolved["user_id"] = demo_user(db)
    if key == "missing_ingredients":
        if resolved["recipe_id"] is None:
            # Reuse actual recommendations; prefer a partially matched recipe.
            candidates = db.all(queries.PANTRY_MATCH, (resolved["user_id"], 20, 0))
            if not candidates:
                raise APIError("No recipe with ingredients is available for this demonstration.", 404)
            choice = next((r for r in candidates if r["missing_ingredients"] > 0), candidates[0])
            resolved["recipe_id"] = choice["recipe_id"]
        require_recipe(db, resolved["recipe_id"])
    if key == "smart_filter":
        # Identical literal LIKE escaping to the existing recipe search.
        if resolved["name"] is not None:
            name = resolved["name"].replace("!", "!!").replace("%", "!%").replace("_", "!_")
            resolved["name"] = f"%{name}%"
        resolved.update(limit=PREVIEW_LIMIT, offset=0)
        return resolved, resolved
    if key in ("pantry_match", "top_ingredients_country", "usda_comparison"):
        resolved["limit"] = PREVIEW_LIMIT
    if key == "pantry_match":
        resolved["offset"] = 0
    return tuple(resolved[name] for name in BINDINGS[key]), resolved


# Parse only MySQL's trailing iterator fields, not arbitrary text inside a filter.
NUM = r"[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?"
ACTUAL = re.compile(
    rf"\(actual time=({NUM})\.\.({NUM}) rows=({NUM}) loops=({NUM})\)\s*$")
ESTIMATE = re.compile(rf"\(cost={NUM} rows=({NUM})\)")


def parse_tree(raw):
    nodes = []
    for line in raw.splitlines():
        if not line.lstrip().startswith("->"):
            continue
        item = {"text": line.strip(), "depth": (len(line) - len(line.lstrip())) // 4}
        actual = ACTUAL.search(line)
        if actual:
            item.update(zip(
                ("first_row_ms", "last_row_ms", "actual_rows_per_loop", "loops"),
                (float(value) for value in actual.groups()),
            ))
        estimate = ESTIMATE.search(line)
        if estimate:
            item["estimated_rows"] = float(estimate.group(1))
        nodes.append(item)
    # The root's last-row time is useful; summing nested timings is misleading.
    root = nodes[0] if nodes else {}
    metrics = {key: root[key] for key in (
        "first_row_ms", "last_row_ms", "actual_rows_per_loop", "loops", "estimated_rows"
    ) if key in root}
    return nodes, metrics


def access_paths(plan):
    paths = []
    if isinstance(plan, dict):
        if "table_name" in plan:
            paths.append({key: plan[key] for key in (
                "table_name", "access_type", "possible_keys", "key",
                "rows_examined_per_scan", "rows_produced_per_join", "filtered",
            ) if key in plan})
        for value in plan.values():
            paths.extend(access_paths(value))
    elif isinstance(plan, list):
        for value in plan:
            paths.extend(access_paths(value))
    return paths


def explain(key, supplied):
    values = validate_parameters(key, supplied)
    sql = explorer_queries.SQL[key]  # Sole source of executable query text.
    with session(readonly=True) as db:
        db.execute(explorer_queries.TIME_LIMIT)
        bound, resolved = bind_parameters(db, key, values)
        analyze = db.one("EXPLAIN ANALYZE FORMAT=TREE " + sql, bound)
        estimate = db.one("EXPLAIN FORMAT=JSON " + sql, bound)
        rows = db.all(sql, bound)
        raw_tree = str(next(iter(analyze.values())))
        raw_json = str(next(iter(estimate.values())))
    nodes, metrics = parse_tree(raw_tree)
    try:
        estimates = json.loads(raw_json)
        paths = access_paths(estimates)
    except (ValueError, TypeError):
        # MySQL output remains inspectable even if a future format changes.
        paths = []
    return {
        "key": key, "sql": sql.strip(), "parameters": resolved,
        "binding_order": BINDINGS[key],
        "lookup_sql": definition(key)["lookup_sql"],
        "plan": {"analyze_tree": raw_tree, "estimate_json": raw_json,
                 "iterators": nodes, "root_metrics": metrics, "access_paths": paths},
        "results": {"columns": list(rows[0]) if rows else [],
                    "rows": rows[:PREVIEW_LIMIT], "returned_row_count": len(rows),
                    "preview_limit": PREVIEW_LIMIT, "truncated": len(rows) > PREVIEW_LIMIT},
        "notes": [
            "The same SQL and bindings are used for both EXPLAIN statements and the result SELECT.",
            "EXPLAIN ANALYZE executes the read-only SELECT. The preview executes it again in the same transaction.",
            "Iterator times are milliseconds, include child iterators, and are averaged per loop; do not add them.",
            "JSON access paths are optimizer estimates, not actual measurements.",
            "The step diagram explains logical SQL flow, not the optimizer's physical execution order.",
        ],
    }
