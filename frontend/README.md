# FoodWise frontend

A responsive HTML/CSS/vanilla JavaScript application, served by the existing Flask
backend. **No frontend build, npm install, external fonts, CDN, or authentication
is needed to run the app.** All recipe, pantry, favorite, and analytics data is
loaded from the real `/api` endpoints. Nothing is seeded by the UI.

## Start the complete application

Run these commands in PowerShell from `C:\FoodWise`.
On a new course machine, install Python 3.10+ and create the environment once:

```powershell
Set-Location C:\FoodWise
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

If the existing environment is already installed, skip those installation steps.
Start the existing MySQL container if needed:

```powershell
docker start foodwise-mysql
```

Set the connection for the current terminal session and start Flask:

```powershell
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3307"
$env:DB_NAME = "foodwise"
$env:DB_USER = "root"
$credential = Get-Credential -UserName root -Message "Enter the existing MySQL password"
$env:DB_PASSWORD = $credential.GetNetworkCredential().Password
.\.venv\Scripts\python.exe -m backend.app
```

If Flask is already running from before the frontend was added, stop that process
with Ctrl+C in its terminal, then run the last command again. Run only one server
on port 5000.

- **Frontend:** http://127.0.0.1:5000/
- **Backend API:** http://127.0.0.1:5000/api
- **Health check:** http://127.0.0.1:5000/api/health

Use the Flask URL; do not double-click `index.html` or run a separate frontend
server. Static assets are served from `/assets/`; the UI uses hash routes such
as `/#/pantry`, so refreshing or bookmarking a screen works without extra routing.
No CORS configuration is necessary.

The existing populated database and `demo_user` must already be present. Do not
recreate the schema or rerun imports to start the application.

## Screens

| Screen | Route | Data source |
| --- | --- | --- |
| Home | `/#/home` | Health, pantry, favorites, top pantry recommendation |
| Recipe search | `/#/recipes` | `/api/recipes` with all six supported filters |
| Recipe details | `/#/recipe/<id>` | Recipe details, missing ingredients, favorites |
| What Can I Cook? | `/#/recommendations` | `/api/recommendations/pantry` |
| My Pantry | `/#/pantry` | Pantry GET/POST/DELETE, ingredient lookup |
| Favorites | `/#/favorites` | Favorites GET/DELETE; add from recipe details |
| My Preferences | `/#/analytics` | `/api/analytics/preferences` |
| Query Explorer | `/#/query-explorer` | Fixed read-only query catalog, real results and MySQL plans |

The [Query Explorer guide](../docs/query-explorer.md) covers the interactive
14-table ERD, SQL highlighting, execution plans, source-data investigation,
spacing corrections, and exact demo/restart commands.

The dashboard shows actual pantry and favorites counts. It does not show a total
recipe count because the existing API does not expose one.

Search and recommendations show 12 items per page. A thirteenth SQL result is
requested to determine whether a next page exists; displayed order is unchanged.
Pantry and favorites fetch every API page so the complete user collection is
visible, including collections larger than the backend's default page size.
Recipe filters and page offsets are kept in the URL.

Missing nutrition is shown as “Not available,” not zero. Nutrition is per serving.
Preparation steps, ingredient quantities, and units come directly from the API.
Preferences uses the backend field `avg_protein_g` for average protein.

## Pantry entry

1. Search for an ingredient by name.
2. Select a real result; its database ID appears below the search.
3. Optionally enter quantity and unit.
4. Choose **Add to pantry** (or **Update pantry ingredient** if it is already present).

Users never need to guess IDs. Changing the search text clears the previous
selection. A search with many results offers pagination.

Saving an existing ingredient replaces quantity and unit. Leaving them blank
saves null values. Pantry matching is the original Day 5 presence-based match:
null or zero quantity still counts as an available ingredient, and units are not
converted. Removing an ingredient can be reversed by searching for it and adding
it again.

## Small backend additions

- Flask serves `frontend/index.html` at `/` and frontend assets at `/assets/`.
- `GET /api/ingredients?name=tomato&limit=20&offset=0` searches existing ingredient
  names using a bound, escaped SQL `LIKE` expression. It returns:

  ```json
  {
    "ingredients": [{"ingredient_id": 50, "ingredient_name": "Tomato"}],
    "limit": 20,
    "offset": 0
  }
  ```

  The example illustrates the response structure; the UI uses actual results.
  `name` is required (1–150 characters). `limit` is 1–100, default 20; `offset`
  defaults to zero. Ordering is by ingredient name, then ID.

The lookup follows the existing route → service → DB helper → explicit SQL
architecture. Existing endpoint shapes, matching logic, schema, imported data,
and authentication behavior are unchanged.

## Course demonstration

1. Open **Home**. Point out the live connection and pantry/favorite counts.
2. Open **Pantry** and show the ingredients already available to `demo_user`.
3. Choose **What can I cook?** Explain the match percentage and missing count.
4. Open a leading result. With the current seed data, Spanish tortilla is first
   at 100%; this is returned by SQL, not hardcoded in the UI.
5. Show ingredients, quantities, steps, and **Missing from your pantry**.
6. Click **Add to favorites**.
7. Open **Favorites** to see the saved recipe.
8. Open **My Preferences** to see category counts and average nutrition/time.
9. Open **Recipes**. Try max time `60`, max calories `700`, minimum protein `10`,
   then add a name, country, or category.
10. Optionally search for a real ingredient in **Pantry**, add it, and revisit
    recommendations to show how the SQL result changes.

Favorites and pantry writes persist in MySQL. Remove anything added solely for
the demo if you want to return to the original demo state.

## Code layout

```text
frontend/
  index.html
  favicon.svg
  css/styles.css
  js/
    api.js          Shared fetch, timeout, response validation, pagination
    app.js          Hash routing and responsive navigation
    ui.js           Escaping, common components, status/error feedback
    home.js
    recipes.js      Search, recommendations, details
    pantry.js
    favorites.js
    analytics.js
  tests/live-ui.test.js
  package.json      Optional test tooling only
  package-lock.json
```

The app uses native JavaScript modules. API errors are handled centrally. Page
navigation aborts old reads; mutations are awaited before showing success.
Database text is HTML-escaped. There are no database credentials in frontend code.
The frontend does not calculate recipe matches or nutrition aggregates.

## Validation

Backend tests:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

See `backend/README.md` for optional disposable-MySQL integration tests and
read-only live smoke checks.

Optional frontend interaction tests require Node.js 24.15+ (24.x) and a running Flask
server. Node/npm are **not needed to demonstrate or run FoodWise**.

```powershell
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend test
```

By default these run read-only against `http://127.0.0.1:5000`. Set
`FOODWISE_TEST_URL` to change the server. To also test pantry and favorites writes:

```powershell
$env:FOODWISE_TEST_WRITES = "1"
npm.cmd --prefix frontend test
Remove-Item Env:FOODWISE_TEST_WRITES
```

Write tests select real ingredients/recipes not already in the user collection,
add temporary records, verify UI behavior and analytics, and remove those records
in `finally` blocks. They never alter imported recipe or USDA records. Run them
without concurrently editing the same demo account.

These are DOM-runtime tests using jsdom, not a rendered-browser test. They verify
live data, controls, pagination, navigation, error handling, and DOM console
errors. A browser connection was not available during implementation, so actual
visual layout and browser-console verification remain manual.

Implementation verification: 14 frontend tests passed, including reversible
pantry/favorites writes against the real API. The backend regression run passed
86 tests, including nine on disposable MySQL; eight opt-in live-smoke tests were
skipped in that run. The frontend suite separately exercised the live API.
The original 20 pantry items and eight favorites were confirmed after testing.

Manual browser checks:

- At desktop width and around 390px width, inspect every screen for overflow.
- On small screens, open/close **Menu** and try keyboard navigation.
- Open browser developer tools → Console, then follow the demonstration flow.
- Verify there are no JavaScript errors; inspect failed network requests if any.
- Try a search with no matches and stop/restart Flask to check the API error/retry
  state.

No animations, chart libraries, remote assets, or frontend build tools are used.
