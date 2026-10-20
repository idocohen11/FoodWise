FOODWISE - DAY 4: IMPORT + 100K ROWS
=========================================

What this package does
----------------------
1. Downloads UniTools World Recipes (501 recipes).
2. Downloads USDA FoodData Central SR Legacy CSV ZIP.
3. Extracts the USDA CSV files.
4. Imports both datasets into the FoodWise MySQL schema.
5. Prints row counts and checks whether the project has 100,000+ rows.

Sources
-------
UniTools:
https://theunitools.com/data/unitools-recipes-v1.json

USDA FoodData Central SR Legacy:
https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip

Requirements
------------
- Python 3.10+
- FoodWise MySQL Docker container running on 127.0.0.1:3307
- The Day 3 schema.sql already executed successfully
- Internet connection for the first run

Windows steps
-------------
1. Put these files in your FoodWise project folder.

2. Open CMD / PowerShell in that folder.

3. Create a virtual environment:
   py -m venv .venv

4. Activate it in CMD:
   .venv\Scripts\activate

   Or in PowerShell:
   .\.venv\Scripts\Activate.ps1

5. Install dependencies:
   python -m pip install -r requirements.txt

6. Make sure MySQL is running:
   docker ps

   You should see:
   foodwise-mysql ... 0.0.0.0:3307->3306/tcp

7. Run the importer:
   python import_data.py

8. Enter the MySQL root password when prompted.
   The password is not shown on screen while typing. That is normal.

9. Wait for the importer to finish.
   USDA food_nutrients is a large table, so this can take a few minutes.

Expected result
---------------
At the end the script prints counts for all 14 tables and a TOTAL.

The important line is:
SUCCESS: Database contains at least 100,000 rows.

Then open validate_import.sql in MySQL Workbench and run it.

Re-running
----------
The importer is designed to be mostly idempotent.

If you want a clean re-import:
   python import_data.py --reset-data

If downloads already exist:
   python import_data.py --skip-download

Only recipes:
   python import_data.py --recipes-only

Only USDA:
   python import_data.py --usda-only

Files created automatically
---------------------------
data/
  unitools-recipes-v1.json
  FoodData_Central_sr_legacy_food_csv_2018-04.zip
  usda_sr_legacy/
    ... USDA CSV files ...

Important design choice
-----------------------
ingredient_food_map is intentionally not auto-filled yet.
A recipe ingredient such as "tomato" can correspond to many USDA foods
(raw tomato, canned tomato, puree, juice, etc.). We will create verified
mappings separately rather than silently inserting bad matches.
