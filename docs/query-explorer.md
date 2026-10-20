# FoodWise Query Explorer

Open **http://127.0.0.1:5000/#/query-explorer**.

The explorer is part of the existing Flask/vanilla JavaScript application. It is
a teaching tool for six fixed, read-only queries, not an SQL console. No new
runtime dependencies, schema changes, indexes, authentication, or seed data are
required.

## Duplicate-looking pantry records

The investigation found these real database records:

| Ingredient ID | Source ID | Display name | Recipes referencing the ID |
| --- | --- | --- | --- |
| 6 | `pepper` | Black pepper | 48 |
| 107 | `blackpepper` | Black pepper | 3 |
| 287 | `pepper2` | Black pepper | 1 |

All three are in demo_user's pantry. There are no duplicate `source_ingredient_id`
values. The importer uses source ID identity, not display-name uniqueness, and
the demo seed selects ingredient IDs independently.

The public [UniTools source feed](https://theunitools.com/data/unitools-recipes-v1.json)
also contains the separate `blackpepper` and `pepper2` identifiers. It uses
`blackpepper` for entries named “Black pepper,” “Black peppercorns,” and
“Ground black pepper” in different recipes. The importer retains the name from
the first occurrence of an ID during import.

This is inconsistent ingredient naming/granularity in the source, faithfully
retained by the importer. It is **not duplicated UI rendering**, and the records
are not necessarily three different culinary ingredients.

Matching remains ID-based:

- Having ID 6 does not automatically satisfy a requirement for ID 107 or 287.
- `COUNT(DISTINCT ingredient_id)` deduplicates repeated uses of the **same ID**.
  It does not deduplicate identical names attached to different IDs.
- Recipe 105, **Ackee and saltfish**, references two different Black pepper IDs,
  so both contribute to its distinct-ingredient count.
- Automatically merging by name could change existing recipe matches and lose
  source distinctions. No records were merged, renamed, deleted, or rewritten.

The Pantry UI now labels repeated names with their actual ingredient IDs and
shows a short explanation. Remove buttons also identify the ID for accessibility.
The pantry's 20 rows and eight favorites remain intact.

## Shared spacing fix

All screens now use a consistent top gap below the sticky header (52px on larger
screens, 40px on small screens). Scroll/focus offsets track the header's measured
height, including the expanded mobile navigation.

The router resets scrolling **after** asynchronous page content has rendered,
and main-content scroll anchoring is disabled. This avoids retaining a previous
page's scroll position underneath the sticky header. The skip link focuses the
main content without accidentally changing the hash route.

The extra navigation item uses the existing compact menu below 1191px. A CSS
layer/`!important` conflict affecting the menu toggle was removed. Typography,
colors, cards, and overall visual identity are retained.

The DOM tests check navigation and scroll-reset timing. Actual browser layout
and screenshots remain unverified because no browser was connected.

## Query catalog and provenance

| Key | Query | SQL source / adaptation |
| --- | --- | --- |
| `pantry_match` | Pantry Match | Existing `queries.PANTRY_MATCH`, verbatim |
| `missing_ingredients` | Missing Ingredients | Existing `queries.MISSING_INGREDIENTS`, verbatim |
| `smart_filter` | Smart Recipe Filter | Existing `queries.RECIPE_SEARCH`, verbatim |
| `top_ingredients_country` | Top Ingredients by Country | Day 5 query 4, same CTE/ranking, outer bound LIMIT 20 |
| `favorite_preferences` | Favorites Preferences | Existing `queries.PREFERENCES`, verbatim |
| `usda_comparison` | USDA Nutrition Comparison | Day 5 query 6, bound protein threshold/LIMIT and an equivalent nutrient-name prefilter |

The USDA prefilter keeps the six nutrient names referenced by the conditional
aggregations. Other names contribute NULL to every macro expression. Removing
them cannot change the final results, which require non-NULL protein. A live
test compares the complete filtered result, by food ID, with the original Day 5
SQL. This optimization was needed after the unfiltered query exceeded the
explorer's time budget on the populated database.

No queries or results are mocked. The screen displays the exact server-side
statement used for EXPLAIN and result execution. Placeholders remain visible;
resolved parameter values and positional binding order appear with each run.

The three user-specific operations use the same demo-user lookup as the app.
That separate prerequisite is shown explicitly. Pantry Match's main statement
uses **three** tables; `users` is used by the separate ID lookup, not silently
added to the displayed statement or its plan.

## Architecture and safe execution

```text
frontend/js/explorer.js + erd.js
    → backend/routes/explorer.py
    → backend/services/explorer_service.py
    → backend/db.py
    → backend/sql/explorer_queries.py (fixed SQL registry)
```

`backend/explorer_metadata.py` holds the teaching descriptions, actual schema
keys/relationships, and step annotations. It does not provide executable SQL.
Shared numeric validation lives in `backend/validation.py`; existing route
imports remain compatible.

Endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/query-explorer/queries` | Six definitions and the 14-table ERD metadata |
| GET | `/api/query-explorer/<query_key>` | One definition and its exact SQL template |
| POST | `/api/query-explorer/<query_key>/explain` | Execute read-only plans and result preview |

Example:

```powershell
Invoke-RestMethod -Method Post `
  http://127.0.0.1:5000/api/query-explorer/pantry_match/explain `
  -ContentType application/json -Body '{}'

Invoke-RestMethod -Method Post `
  http://127.0.0.1:5000/api/query-explorer/smart_filter/explain `
  -ContentType application/json `
  -Body '{"parameters":{"max_minutes":60,"max_calories":700,"min_protein":10}}'
```

The POST body accepts only `parameters`. Unknown keys, unknown parameters, SQL
fields, arbitrary limits, and user IDs are rejected. Unknown query keys return
404, invalid input returns 400, and unexpected database failures return safe JSON
500 responses. Existing handling also covers malformed JSON and oversized bodies.

Execution uses:

1. An existing connection from the common DB layer.
2. `start_transaction(readonly=True)`.
3. Fixed `SET SESSION max_execution_time = 8000`, affecting only that connection.
4. Resolved/validated, connector-bound values.
5. `EXPLAIN ANALYZE FORMAT=TREE` + the allowlisted SELECT.
6. `EXPLAIN FORMAT=JSON` + the **same** SELECT and bindings.
7. The same SELECT again for the result preview.
8. Rollback/end the read transaction and close the connection.

The SQL registry is immutable. No request text is interpolated into SQL syntax.
Names and numeric filters can only become bound values. The client cannot choose
statements, table names, methods of explaining, usernames, or session controls.
Only developer-authored SELECT/CTE queries are reachable through these endpoints.
The read-only transaction is a second safeguard; integration tests verify that
MySQL rejects a deliberate DELETE inside such a transaction in the disposable
test database.

The main bounded queries return up to 20 rows. Missing ingredient lines and
preference groups reuse their application SQL without an extra LIMIT; their
response preview is capped at 20, with a truncation flag and returned-row count.
The original application queries remain unchanged.

## Presentation walkthrough

1. Select **Pantry Match**.
2. Use **Next step** or select a numbered step:
   - recipes;
   - join recipe ingredient lines;
   - LEFT JOIN this user's pantry;
   - group by recipe;
   - count distinct IDs;
   - calculate match percentage;
   - order/limit the result;
   - inspect MySQL's real plan.
3. Watch the active tables, join edges, and SQL lines change together.
4. Click a table (or focus it and press Enter/Space) to inspect PK/FK details.
5. Choose **Run / Explain Query**. It starts the logical walkthrough at step 1
   and retrieves actual query results and execution plans.
6. Compare the live ranking with the application's **What Can I Cook?** screen.
   With the preserved demo state, the first three results are Spanish tortilla
   (100%), Kenyan chapati (80%), and Baursak (75%). These are database results,
   not frontend constants.
7. Open **Actual execution**, **Access paths**, and the full JSON estimate.
8. Try the CTE/window query or the conditional-aggregation USDA query.

**Previous step**, **Next step**, direct step selection, and **Reset** work without
timed animation. Reset also restores default parameters and clears the old plan.
Parameter edits invalidate old results. Navigating away prevents stale responses
from replacing the new screen.

Missing Ingredients defaults to the first partially matched recipe among the
top 20 actual recommendations, falling back to the first recommendation if all
are complete. The resolved recipe ID is shown in the run details. It can also
be supplied explicitly.

ERD colors:

- Green: table/relationship used by the selected main query.
- Amber: used in the current logical step.
- Dimmed: unrelated to this query.
- Solid arrow: actual FK → referenced key.
- Dashed arrow: actual query equality without a direct FK constraint, such as
  `recipe_ingredients.ingredient_id = pantry.ingredient_id`.

All 14 tables and all 14 FK relationships are represented. Composite primary
keys and PK/FK overlap are labeled. Non-key fields are a representative subset.
The whole graph remains horizontally scrollable on narrow screens.

## Reading the plan correctly

The diagram describes **logical SQL flow**, not the optimizer's physical order.

- The raw ANALYZE tree is preserved.
- Root timing/rows/loops and estimated rows are shown only when reliably parsed.
- Iterator times are milliseconds and include child iterators; when an iterator
  loops, time and rows are reported per loop. Nested times must not be added.
- The root last-row time is not HTTP latency or page-load time.
- Access type, chosen index, estimated rows, and filtering percentage come from
  `EXPLAIN FORMAT=JSON` and are labeled as **estimates**.
- If parsing cannot recognize a metric, it is omitted; the raw plan remains
  available.
- EXPLAIN ANALYZE executes the SELECT. The result preview executes it again, so
  cached pages and server load can make repeated timings differ.

References: [MySQL EXPLAIN documentation](https://dev.mysql.com/doc/refman/8.0/en/explain.html)
and [statement execution limits](https://dev.mysql.com/doc/refman/8.0/en/optimizer-hints.html).

## Restart the complete application

Stop the old Flask process with Ctrl+C in its terminal, then run:

```powershell
Set-Location C:\FoodWise
docker start foodwise-mysql
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3307"
$env:DB_NAME = "foodwise"
$env:DB_USER = "root"
$credential = Get-Credential -UserName root -Message "Enter the existing MySQL password"
$env:DB_PASSWORD = $credential.GetNetworkCredential().Password
.\.venv\Scripts\python.exe -m backend.app
```

If the current server was started in the background, use this first to stop only
the verified FoodWise listener (not an unrelated service using the same port):

```powershell
$listener = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $server = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $listener.OwningProcess)
    if ($server.CommandLine -notmatch 'backend\.app') {
        throw "Port 5000 belongs to another application; nothing was stopped."
    }
    Stop-Process -Id $listener.OwningProcess
}
```

Install dependencies only if setting up a new environment:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
```

Frontend: http://127.0.0.1:5000/  
Explorer: http://127.0.0.1:5000/#/query-explorer  
API: http://127.0.0.1:5000/api

No frontend build or npm installation is needed to run the application.

## Tests and limitations

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q

# Optional read-only tests against the existing populated database:
$env:FOODWISE_RUN_LIVE_SMOKE = "1"
.\.venv\Scripts\python.exe -m pytest backend/tests/test_live_smoke.py backend/tests/test_explorer_live.py -q
Remove-Item Env:FOODWISE_RUN_LIVE_SMOKE

# Optional DOM tests (Node 24.15+ on the 24.x line):
npm.cmd --prefix frontend ci
$env:FOODWISE_TEST_WRITES = "1"
npm.cmd --prefix frontend test
Remove-Item Env:FOODWISE_TEST_WRITES
```

The existing backend documentation explains the separate, disposable MySQL
integration configuration. Never point destructive test fixtures at the populated
`foodwise` database.

Automated coverage includes query allowlisting, rejected SQL payloads, bound
injection strings, read-only transactions, rollback/cleanup, plan parsing,
metadata consistency with MySQL, all six queries on both isolated and real data,
USDA equivalence, UI steps/highlights, result/plan rendering, and existing app
regressions. Full pantry/favorite records, including timestamps, are compared
before and after verification.

Verified implementation results:

- 129 backend regression/integration tests passed on disposable MySQL; the 16
  opt-in live tests were skipped in that run.
- All 16 live tests then passed separately against the populated database.
- All 17 frontend DOM tests passed, including the existing reversible write
  tests and all six explorer queries.
- Python compilation, JavaScript syntax, and `git diff --check` passed.
- Full-record snapshots confirmed 20 unchanged pantry rows and eight unchanged
  favorites, including timestamps.

No browser is connected in the current environment. DOM interaction tests and
syntax checks do not verify actual rendered layout, screenshots, or the browser
console. Those remain manual checks at desktop/mobile widths.

The eight-second statement budget can return a safe error on a much slower or
busy course machine; the client allows 45 seconds for the combined request.
Client cancellation discards the response but does not guarantee immediate MySQL
cancellation; the server-side time limit remains in effect. This is a local demo,
without authentication or a concurrent-load benchmark.

## File changes

Added:

- `backend/explorer_metadata.py`
- `backend/sql/explorer_queries.py`
- `backend/services/explorer_service.py`
- `backend/routes/explorer.py`
- `backend/validation.py` (extracted shared scalar validators)
- `backend/tests/test_explorer.py`
- `backend/tests/test_explorer_live.py`
- `frontend/js/explorer.js`
- `frontend/js/erd.js`
- `frontend/css/explorer.css`
- `docs/query-explorer.md`

Updated:

- `backend/app.py`, `backend/db.py`, `backend/routes/validation.py`
- `backend/tests/test_mysql_integration.py`
- `frontend/index.html`, `frontend/js/app.js`, `frontend/js/api.js`
- `frontend/js/pantry.js`, `frontend/css/styles.css`
- `frontend/tests/live-ui.test.js`
- Root, backend, and frontend READMEs

The schema, importer, Day 5 SQL file, existing application query constants, and
imported recipe/USDA records were not changed. No commit was made.
