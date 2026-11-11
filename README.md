# FoodWise — Recipe Discovery & Pantry Management

A full-stack food management application built around a **MySQL 8 relational database**. Search recipes, manage pantry ingredients, discover what you can cook, save favorites, and explore the SQL behind the recommendations.

**Stack:** Python · Flask · MySQL 8 · mysql-connector-python · HTML · CSS · Vanilla JavaScript

## Highlights

- **Recipe discovery:** filter recipes by name, country, category, cooking time, calories, and protein.
- **Pantry management:** search for ingredients, add or update pantry entries, and remove them.
- **Pantry-based recommendations:** discover recipes based on available ingredients and inspect missing ingredients.
- **Favorites and analytics:** save recipes and explore preference summaries.
- **Query Explorer:** inspect six predefined, read-only SQL queries, their results, execution plans, and an interactive ERD.
- **Database-first design:** explicit parameterized SQL; joins, filters, sorting, and pagination execute in MySQL rather than being simulated in the UI.

## Architecture

```text
Browser (HTML/CSS/JavaScript)
          |
          v
Flask HTTP API (/api)
          |
          v
Routes -> Services -> DB helpers -> Parameterized SQL
                                  |
                                  v
                               MySQL 8
```

Flask also serves the frontend, so **no separate frontend server or build step** is necessary. The demo uses an existing populated database and a local `demo_user`; authentication and multi-user account management are not implemented.

## Getting started (Windows / PowerShell)

**Prerequisites:** Python 3.10+, MySQL 8, and an existing populated FoodWise database with `demo_user`. The included schema and importer are documented separately; do not rerun them against an existing populated database.

From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt

$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3307" # change if your MySQL instance uses another port
$env:DB_NAME = "foodwise"
$env:DB_USER = "root"
$credential = Get-Credential -UserName root -Message "Enter your MySQL password"
$env:DB_PASSWORD = $credential.GetNetworkCredential().Password

.\.venv\Scripts\python.exe -m backend.app
```

Open **http://127.0.0.1:5000/** (API: `http://127.0.0.1:5000/api`; health check: `/api/health`).

> The application expects the existing database to be available. Starting the Flask application does not create tables, import data, or seed demo records.

## Explore the project

| Area | What you'll find |
| --- | --- |
| [Frontend](frontend/README.md) | Screens, user journeys, frontend startup, and UI tests |
| [Backend](backend/README.md) | Flask API, environment variables, SQL architecture, and testing |
| [Query Explorer](docs/query-explorer.md) | Read-only SQL query explorer, ERD, and execution-plan explanations |
| [Database schema](schema.sql) | Relational schema |
| [Complex SQL queries](FoodWise_Day5_Complex_Queries.sql) | Workshop queries |

## Testing

Backend tests and optional frontend tests are documented in the [backend guide](backend/README.md) and [frontend guide](frontend/README.md). The project separates HTTP routing, application services, and SQL execution to make behavior testable.

## Scope

This is a database-focused educational project. It intentionally uses explicit SQL without an ORM, an existing dataset, and a single demo user. It is not presented as a production-ready authenticated service.

---

**Maintained by [Ido Cohen](https://github.com/idocohen11).**
