# FoodWise backend

Flask + `mysql-connector-python`, with explicit SQL and the existing MySQL 8
schema. There is no ORM and the application never creates or migrates tables.
Run all commands below from `C:\FoodWise` (the repository root).

## Installation and startup

Install Python 3.10+ if it is not already available, then in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt

$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3307"
$env:DB_NAME = "foodwise"
$env:DB_USER = "root"
$credential = Get-Credential -UserName root -Message "Enter the existing MySQL password"
$env:DB_PASSWORD = $credential.GetNetworkCredential().Password

.\.venv\Scripts\python.exe -m backend.app
```

The development server listens at `http://127.0.0.1:5000`, with debug mode off.
It also serves the FoodWise frontend at `http://127.0.0.1:5000/`; no separate
frontend process is needed. See [frontend documentation](../frontend/README.md)
for the UI, demo flow, and optional frontend tests.
The exact start command after setup is:

```powershell
.\.venv\Scripts\python.exe -m backend.app
```

Alternatively, in an activated virtual environment: `python -m backend.app`.
Runtime-only installation: `python -m pip install -r backend/requirements.txt`.
The root `requirements.txt` remains the importer's dependency list.

MySQL must already be running and contain the imported schema and `demo_user`.
The importer uses `MYSQL_PASSWORD`; this backend deliberately uses `DB_PASSWORD`.
Do not rerun `schema.sql` against your populated database.

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `DB_HOST` | `127.0.0.1` | MySQL host |
| `DB_PORT` | `3307` | MySQL TCP port |
| `DB_NAME` | `foodwise` | Existing database |
| `DB_USER` | `root` | MySQL account |
| `DB_PASSWORD` | None; required | Password supplied through the environment |
| `DB_CONNECT_TIMEOUT` | `10` | Connection timeout in seconds |

An unset password produces a safe 500 response when accessing the database.
An explicitly empty password is passed through if your test database permits it.
No password is hardcoded or logged. `.env` files are ignored by Git but are **not
automatically loaded**; set process environment variables as shown above.

## Structure

```text
backend/
  app.py                    App factory, health endpoint, JSON errors/serialization
  config.py                 Environment configuration
  db.py                     Connections, cursors, transactions, SQL execution
  errors.py                 Safe application exceptions
  routes/                   HTTP parsing and validation
  services/                 Application operations and demo-user lookup
  sql/queries.py            Explicit parameterized SQL
  tests/                    API, isolated MySQL, and read-only live tests
```

Routes call services; services execute named SQL through the database layer.
Filtering, joins, counts, averages, sorting, and pagination happen in MySQL.
Connections are opened per service operation, reused within that operation, and
always closed. Writes commit only after the complete operation succeeds; failures
roll back. Recipe details use one connection for recipe, ingredient, and step reads.

## API

All endpoints are under `/api`. This initial local demo always uses `demo_user`;
there is no authentication or user switching.

Query Explorer adds `GET /api/query-explorer/queries`,
`GET /api/query-explorer/<query_key>`, and
`POST /api/query-explorer/<query_key>/explain`. It only runs six server-defined
SELECT queries in read-only transactions. See the
[Query Explorer guide](../docs/query-explorer.md) for parameters, SQL provenance,
plan semantics, validation, and safe execution details.

| Method | Path | Response |
| --- | --- | --- |
| GET | `/health` | `{"status":"ok","database":"connected"}` |
| GET | `/recipes` | `{"recipes":[...],"limit":30,"offset":0}` |
| GET | `/recipes/<recipe_id>` | Recipe object with `ingredients` and `steps` arrays |
| GET | `/ingredients?name=<text>` | `{"ingredients":[...],"limit":20,"offset":0}` |
| GET | `/pantry` | `{"pantry":[...],"limit":30,"offset":0}` |
| POST | `/pantry` | Saved ingredient ID, quantity, unit; 200 |
| DELETE | `/pantry/<ingredient_id>` | 204, no body |
| GET | `/recommendations/pantry` | `{"recipes":[...],"limit":20,"offset":0}` |
| GET | `/recipes/<recipe_id>/missing-ingredients` | `{"recipe_id":123,"missing_ingredients":[...]}` |
| GET | `/favorites` | `{"favorites":[...],"limit":30,"offset":0}` |
| POST | `/favorites/<recipe_id>` | `{"recipe_id":123,"status":"saved"}`; 200 |
| DELETE | `/favorites/<recipe_id>` | 204, no body |
| GET | `/analytics/preferences` | `{"preferences":[...]}` |

### Recipe search and list pagination

Search accepts any combination of:

| Parameter | Meaning |
| --- | --- |
| `name` | Literal substring of recipe name; `%` and `_` are escaped |
| `country` | Exact country code (e.g. `ES`) or country name (e.g. `Spain`) |
| `category` | Exact category name |
| `max_minutes` | Non-negative upper bound on prep + cook time |
| `max_calories` | Non-negative upper bound on calories per serving |
| `min_protein` | Non-negative lower bound on protein grams per serving |

Names follow the existing database collation for case/accent matching.
Search results keep Day 5's protein descending, total time ascending, calories
ascending ordering, with recipe ID as a deterministic tie-breaker.

Search, pantry, favorites, and recommendations accept `limit` (1–100) and
`offset` (0–2147483647). Defaults are 30 and 0, except recommendations default to
20. Request subsequent pages until a page is shorter than `limit`. Unknown or
repeated query parameters on these list endpoints return 400.

Recipe objects include `recipe_id`, `recipe_name`, `source_slug`, `native_name`,
`summary`, `difficulty`, `base_servings`, `country_code`, `country`, `category`,
`prep_minutes`, `cook_minutes`, `total_minutes`, and the four per-serving
nutrition fields. Details also include ingredient lines (quantity, unit, scaling,
note) and preparation steps ordered by step number.
SQL DECIMAL results are JSON numbers; missing values are `null`.
Timestamps are ISO 8601 strings without a timezone, reflecting existing MySQL
DATETIME values.

### Pantry and matching semantics

Ingredient lookup: `GET /api/ingredients?name=tomato&limit=20&offset=0` returns
existing `ingredient_id` and `ingredient_name` values for a literal substring
search. `name` is required (1–150 characters); `limit` is 1–100 (default 20).
This lets the frontend select real IDs without schema changes. Filtering and
sorting by name/ID happen in SQL. Unknown and repeated query parameters return
400. See `routes/ingredients.py`, `services/ingredient_service.py`, and
`sql/queries.py`.

POST `/pantry` accepts:

```json
{"ingredient_id":123,"quantity":2,"unit":"pcs"}
```

`ingredient_id` must refer to an existing ingredient. `quantity` and `unit` may
be omitted or null, matching the existing seed data and schema. Quantity must
be non-negative, at most 9999999.999, and have no more than three decimal places.
Unit must contain 1–50 characters when supplied. Unknown fields return 400.
Posting an existing ingredient **replaces** its quantity and unit; it does not
add quantities. Omitted quantity/unit replace previous values with null.

Pantry recommendations return `recipe_id`, `recipe_name`, `total_ingredients`,
`ingredients_in_pantry`, `missing_ingredients`, and `pantry_match_percent`.
They preserve Day 5 query 1: count distinct ingredient IDs and rank by match
percentage descending, then missing count, total count, name, and recipe ID.
Recipes with no ingredient lines are excluded.

Matching tests ingredient **presence**, without checking quantity or converting
units. Zero and null pantry quantities still count as available, exactly as in
Day 5. Missing ingredients use Day 5 query 2's anti-join and return recipe lines
in line order; an ingredient repeated in multiple missing lines stays repeated.
Missing ingredients for an existing recipe can be an empty array.

### Favorites and analytics

Adding an existing favorite is idempotent and retains its original timestamp.
Deleting a missing favorite or pantry item returns 404.

Preferences reuse Day 5 query 5 and return one row per favorite category:

```json
{
  "preferences": [
    {
      "category": "main",
      "favorite_count": 3,
      "avg_calories": 410.5,
      "avg_protein_g": 22.3,
      "avg_total_minutes": 35.0
    }
  ]
}
```

The example is illustrative. SQL AVG ignores unknown nutrition. As in Day 5,
missing prep/cook times contribute zero to total time in search and analytics.
Uncategorized favorites are grouped under `category: null`. No favorites returns
an empty array.

### Errors

Errors use `{"error":{"message":"A user-friendly explanation."}}`.
Bad IDs, filters, or request bodies return 400; missing recipes, ingredients,
pantry entries, favorites, or demo user return 404. Unexpected database errors
return 500 without SQL details, credentials, or stack traces. Unsupported HTTP
methods return JSON 405; bodies over 16 KiB return JSON 413.

## Example requests

PowerShell:

```powershell
$base = "http://127.0.0.1:5000/api"
Invoke-RestMethod "$base/health"
Invoke-RestMethod "$base/recipes?name=chicken&country=ES&category=main&max_minutes=60&max_calories=700&min_protein=10&limit=10"

# Use IDs from your actual data; IDs below are illustrative.
Invoke-RestMethod "$base/recipes/123"
Invoke-RestMethod "$base/pantry"
Invoke-RestMethod -Method Post "$base/pantry" -ContentType "application/json" `
  -Body '{"ingredient_id":123,"quantity":2,"unit":"pcs"}'
Invoke-RestMethod "$base/recommendations/pantry?limit=20"
Invoke-RestMethod "$base/recipes/123/missing-ingredients"
Invoke-RestMethod -Method Delete "$base/pantry/123"

Invoke-RestMethod "$base/favorites"
Invoke-RestMethod -Method Post "$base/favorites/123"
Invoke-RestMethod "$base/analytics/preferences"
Invoke-RestMethod -Method Delete "$base/favorites/123"
```

## Tests

Default tests mock only the connector boundary, exercising routes, services,
SQL parameter binding, JSON conversion, cleanup, and commit/rollback behavior.
They do not need MySQL and never change real data:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

The real MySQL integration suite is opt-in. Provision a **separate, disposable**
MySQL 8 instance and an empty/nonexistent database whose name ends in `_test`.
It loads the original schema there, seeds known fixtures, and tests actual SQL,
CRUD, matching, filtering, pagination, and averages. It refuses a nonempty
database and never uses `DB_*` for its fixture connection:

```powershell
$env:FOODWISE_RUN_INTEGRATION = "1"
$env:TEST_DB_HOST = "127.0.0.1"
$env:TEST_DB_PORT = "3308" # Your disposable instance, not the existing 3307 database.
$env:TEST_DB_NAME = "foodwise_backend_test"
$env:TEST_DB_USER = "root"
$env:TEST_DB_PASSWORD = $testCredential.GetNetworkCredential().Password
.\.venv\Scripts\python.exe -m pytest backend/tests -q
Remove-Item Env:FOODWISE_RUN_INTEGRATION
```

Obtain `$testCredential` using `Get-Credential` for that disposable instance first.
Provision a fresh empty test database for each integration run. Test fixture
data remains there until you remove the disposable instance.

To check all eight GET endpoint types against your populated database without
writing any data, set the normal `DB_*` environment variables, then run:

```powershell
$env:FOODWISE_RUN_LIVE_SMOKE = "1"
.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_smoke.py -q
Remove-Item Env:FOODWISE_RUN_LIVE_SMOKE
```

The integration and live smoke suites are skipped unless explicitly enabled.
