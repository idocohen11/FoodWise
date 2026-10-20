# FoodWise

A Workshop in Data Management project: a MySQL 8 database, explicit SQL through
`mysql-connector-python`, a Flask backend, and a lightweight HTML/CSS/JavaScript UI.

Start the complete application from this directory after setting `DB_PASSWORD`
and installing the backend requirements:

```powershell
.\.venv\Scripts\python.exe -m backend.app
```

Open **http://127.0.0.1:5000/**. The API is at
**http://127.0.0.1:5000/api**. There is no separate frontend server or build.

- [Frontend setup, exact commands, and course demo](frontend/README.md)
- [Backend setup, API reference, and tests](backend/README.md)
- [Query Explorer, SQL provenance, and presentation guide](docs/query-explorer.md)
- [Existing schema](schema.sql)
- [Day 5 complex SQL queries](FoodWise_Day5_Complex_Queries.sql)
- [Original importer instructions](README_DAY4.txt)

The app uses the existing populated database and `demo_user`. Starting it does
not create tables, seed data, or import datasets.
