#!/usr/bin/env python3
"""
FoodWise - Day 4 importer
Downloads and imports:
1) UniTools World Recipes (JSON)
2) USDA FoodData Central - SR Legacy (CSV ZIP)

Target schema: the FoodWise MySQL schema created in Day 3.

Usage examples:
    python import_data.py
    python import_data.py --host 127.0.0.1 --port 3307 --user root
    python import_data.py --skip-download
    python import_data.py --reset-data

The script asks for the MySQL password securely if MYSQL_PASSWORD is not set.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import json
import os
import re
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Iterable, Optional

import mysql.connector
from mysql.connector import Error

try:
    import pycountry
except ImportError:
    pycountry = None


UNITOOLS_URL = "https://theunitools.com/data/unitools-recipes-v1.json"
USDA_SR_LEGACY_URL = (
    "https://fdc.nal.usda.gov/fdc-datasets/"
    "FoodData_Central_sr_legacy_food_csv_2018-04.zip"
)

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"
UNITOOLS_FILE = "unitools-recipes-v1.json"
USDA_ZIP_FILE = "FoodData_Central_sr_legacy_food_csv_2018-04.zip"
USDA_EXTRACT_DIR = "usda_sr_legacy"


def log(message: str) -> None:
    print(f"[FoodWise] {message}", flush=True)


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        log(f"Download already exists: {destination}")
        return

    log(f"Downloading: {url}")
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "FoodWise academic project/1.0"},
        )
        with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as out:
            total = response.headers.get("Content-Length")
            total_bytes = int(total) if total and total.isdigit() else None
            downloaded = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if total_bytes:
                    pct = downloaded * 100 / total_bytes
                    print(f"\r  {pct:5.1f}% ({downloaded / 1_048_576:.1f} MB)", end="", flush=True)
            if total_bytes:
                print()
    except Exception:
        if destination.exists():
            destination.unlink()
        raise

    log(f"Saved: {destination} ({destination.stat().st_size / 1_048_576:.1f} MB)")


def extract_usda(zip_path: Path, extract_dir: Path) -> None:
    required = {"food.csv", "food_category.csv", "nutrient.csv", "food_nutrient.csv"}
    if extract_dir.exists():
        found = {p.name.lower() for p in extract_dir.rglob("*.csv")}
        if required.issubset(found):
            log(f"USDA archive already extracted: {extract_dir}")
            return

    log(f"Extracting USDA ZIP to: {extract_dir}")
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)


def find_csv(root: Path, filename: str) -> Path:
    matches = [p for p in root.rglob("*.csv") if p.name.lower() == filename.lower()]
    if not matches:
        raise FileNotFoundError(f"Could not find {filename} under {root}")
    if len(matches) > 1:
        log(f"Warning: multiple {filename} files found; using {matches[0]}")
    return matches[0]


def none_if_blank(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value != "" else None
    return value


def to_int(value: Any) -> Optional[int]:
    value = none_if_blank(value)
    return int(value) if value is not None else None


def to_float(value: Any) -> Optional[float]:
    value = none_if_blank(value)
    return float(value) if value is not None else None


def english_text(value: Any) -> Optional[str]:
    """Return English text from a UniTools multilingual value."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        candidate = value.get("en") or value.get("ru")
        return candidate.strip() if isinstance(candidate, str) and candidate.strip() else None
    return str(value)


def country_name(code: str) -> str:
    code = (code or "").strip().upper()
    if not code:
        return "Unknown"
    if pycountry is not None:
        try:
            item = pycountry.countries.get(alpha_2=code)
            if item is not None:
                return item.name
        except Exception:
            pass
    # Fallback keeps the database valid even if a non-standard code is present.
    return code


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def connect(args: argparse.Namespace):
    password = args.password or os.getenv("MYSQL_PASSWORD")
    if password is None:
        password = getpass.getpass("MySQL root password: ")

    log(f"Connecting to MySQL at {args.host}:{args.port}/{args.database} ...")
    conn = mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=password,
        database=args.database,
        autocommit=False,
        charset="utf8mb4",
        use_unicode=True,
        connection_timeout=15,
    )
    return conn


def verify_schema(conn) -> None:
    required = {
        "countries", "recipe_categories", "recipes", "ingredients",
        "recipe_ingredients", "recipe_steps", "users", "pantry", "favorites",
        "food_categories", "food_items", "nutrients", "food_nutrients",
        "ingredient_food_map",
    }
    cur = conn.cursor()
    cur.execute("SHOW TABLES")
    actual = {row[0] for row in cur.fetchall()}
    cur.close()

    missing = sorted(required - actual)
    if missing:
        raise RuntimeError(
            "FoodWise schema is incomplete. Missing tables: " + ", ".join(missing)
        )
    log(f"Schema verified: {len(required)} required tables found.")


def reset_imported_data(conn) -> None:
    """Clear imported dataset data while preserving the demo/user domain."""
    log("Resetting imported recipe/USDA data ...")
    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for table in [
        "ingredient_food_map",
        "recipe_steps",
        "recipe_ingredients",
        "favorites",
        "pantry",
        "recipes",
        "ingredients",
        "recipe_categories",
        "countries",
        "food_nutrients",
        "food_items",
        "nutrients",
        "food_categories",
    ]:
        cur.execute(f"TRUNCATE TABLE `{table}`")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    cur.close()
    log("Imported data reset complete.")


def executemany_chunks(conn, sql: str, rows: Iterable[tuple], batch_size: int = 5000) -> int:
    cur = conn.cursor()
    batch: list[tuple] = []
    total = 0

    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            cur.executemany(sql, batch)
            conn.commit()
            total += len(batch)
            log(f"  inserted/processed {total:,} rows")
            batch.clear()

    if batch:
        cur.executemany(sql, batch)
        conn.commit()
        total += len(batch)

    cur.close()
    return total


def import_usda(conn, usda_dir: Path) -> None:
    log("=== Importing USDA SR Legacy ===")
    food_category_csv = find_csv(usda_dir, "food_category.csv")
    nutrient_csv = find_csv(usda_dir, "nutrient.csv")
    food_csv = find_csv(usda_dir, "food.csv")
    food_nutrient_csv = find_csv(usda_dir, "food_nutrient.csv")

    # 1) Food categories
    with food_category_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = (
            (
                to_int(r.get("id")),
                none_if_blank(r.get("description")) or none_if_blank(r.get("name")) or f"Category {r.get('id')}",
            )
            for r in reader
            if none_if_blank(r.get("id"))
        )
        count = executemany_chunks(
            conn,
            """
            INSERT INTO food_categories (food_category_id, name)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE name = VALUES(name)
            """,
            rows,
            batch_size=500,
        )
    log(f"Food categories processed: {count:,}")

    # 2) Nutrients
    with nutrient_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = (
            (
                to_int(r.get("id")),
                none_if_blank(r.get("name")) or f"Nutrient {r.get('id')}",
                none_if_blank(r.get("unit_name")),
            )
            for r in reader
            if none_if_blank(r.get("id"))
        )
        count = executemany_chunks(
            conn,
            """
            INSERT INTO nutrients (nutrient_id, name, unit_name)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                unit_name = VALUES(unit_name)
            """,
            rows,
            batch_size=1000,
        )
    log(f"Nutrients processed: {count:,}")

    # 3) Food items
    with food_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = (
            (
                to_int(r.get("fdc_id")),
                normalize_spaces(none_if_blank(r.get("description")) or "Unknown food"),
                none_if_blank(r.get("data_type")),
                to_int(r.get("food_category_id")),
            )
            for r in reader
            if none_if_blank(r.get("fdc_id"))
        )
        count = executemany_chunks(
            conn,
            """
            INSERT INTO food_items (fdc_id, description, data_type, food_category_id)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                description = VALUES(description),
                data_type = VALUES(data_type),
                food_category_id = VALUES(food_category_id)
            """,
            rows,
            batch_size=3000,
        )
    log(f"Food items processed: {count:,}")

    # 4) Food nutrients (largest table)
    with food_nutrient_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        def nutrient_rows():
            for r in reader:
                if not none_if_blank(r.get("id")):
                    continue
                amount = to_float(r.get("amount"))
                yield (
                    to_int(r.get("id")),
                    to_int(r.get("fdc_id")),
                    to_int(r.get("nutrient_id")),
                    amount,
                )

        count = executemany_chunks(
            conn,
            """
            INSERT INTO food_nutrients
                (food_nutrient_id, fdc_id, nutrient_id, amount)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                fdc_id = VALUES(fdc_id),
                nutrient_id = VALUES(nutrient_id),
                amount = VALUES(amount)
            """,
            nutrient_rows(),
            batch_size=5000,
        )
    log(f"Food nutrients processed: {count:,}")


def get_or_create_category(conn, cache: dict[str, int], name: str) -> int:
    name = (name or "other").strip().lower()
    if name in cache:
        return cache[name]

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO recipe_categories (name)
        VALUES (%s)
        ON DUPLICATE KEY UPDATE category_id = LAST_INSERT_ID(category_id)
        """,
        (name,),
    )
    category_id = cur.lastrowid
    if not category_id:
        cur.execute("SELECT category_id FROM recipe_categories WHERE name = %s", (name,))
        category_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    cache[name] = int(category_id)
    return int(category_id)


def get_or_create_ingredient(
    conn,
    cache: dict[str, int],
    source_id: str,
    name: str,
) -> int:
    source_id = source_id.strip()
    if source_id in cache:
        return cache[source_id]

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ingredients (source_ingredient_id, name)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE
            ingredient_id = LAST_INSERT_ID(ingredient_id),
            name = VALUES(name)
        """,
        (source_id, name),
    )
    ingredient_id = cur.lastrowid
    if not ingredient_id:
        cur.execute(
            "SELECT ingredient_id FROM ingredients WHERE source_ingredient_id = %s",
            (source_id,),
        )
        ingredient_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    cache[source_id] = int(ingredient_id)
    return int(ingredient_id)


def import_unitools(conn, json_path: Path) -> None:
    log("=== Importing UniTools World Recipes ===")
    with json_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    recipes = payload.get("recipes", []) if isinstance(payload, dict) else payload
    if not isinstance(recipes, list):
        raise ValueError("UniTools JSON does not contain a recipe list.")

    log(f"Recipes in source: {len(recipes):,}")

    category_cache: dict[str, int] = {}
    ingredient_cache: dict[str, int] = {}

    cur = conn.cursor()

    # Preload caches for idempotent re-runs.
    cur.execute("SELECT category_id, name FROM recipe_categories")
    for category_id, name in cur.fetchall():
        category_cache[str(name).lower()] = int(category_id)

    cur.execute("SELECT ingredient_id, source_ingredient_id FROM ingredients WHERE source_ingredient_id IS NOT NULL")
    for ingredient_id, source_id in cur.fetchall():
        ingredient_cache[str(source_id)] = int(ingredient_id)

    cur.close()

    imported_recipes = 0
    imported_lines = 0
    imported_steps = 0

    for index, recipe in enumerate(recipes, start=1):
        slug = str(recipe["slug"]).strip()
        code = str(recipe.get("country") or "ZZ").strip().upper()
        c_name = country_name(code)

        # Country
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO countries (country_code, name)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE name = VALUES(name)
            """,
            (code, c_name),
        )
        conn.commit()
        cur.close()

        # Category
        category_id = get_or_create_category(
            conn, category_cache, str(recipe.get("category") or "other")
        )

        nutrition = recipe.get("nutritionPerServing") or {}

        # Recipe
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO recipes (
                source_slug, country_code, category_id, name, native_name, summary,
                difficulty, base_servings, prep_minutes, cook_minutes,
                calories_per_serving, protein_g_per_serving,
                fat_g_per_serving, carbs_g_per_serving
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                recipe_id = LAST_INSERT_ID(recipe_id),
                country_code = VALUES(country_code),
                category_id = VALUES(category_id),
                name = VALUES(name),
                native_name = VALUES(native_name),
                summary = VALUES(summary),
                difficulty = VALUES(difficulty),
                base_servings = VALUES(base_servings),
                prep_minutes = VALUES(prep_minutes),
                cook_minutes = VALUES(cook_minutes),
                calories_per_serving = VALUES(calories_per_serving),
                protein_g_per_serving = VALUES(protein_g_per_serving),
                fat_g_per_serving = VALUES(fat_g_per_serving),
                carbs_g_per_serving = VALUES(carbs_g_per_serving)
            """,
            (
                slug,
                code,
                category_id,
                english_text(recipe.get("name")) or slug,
                none_if_blank(recipe.get("nativeName")),
                english_text(recipe.get("summary")),
                none_if_blank(recipe.get("difficulty")),
                to_int(recipe.get("baseServings")),
                to_int(recipe.get("prepMinutes")),
                to_int(recipe.get("cookMinutes")),
                to_float(nutrition.get("calories")),
                to_float(nutrition.get("protein")),
                to_float(nutrition.get("fat")),
                to_float(nutrition.get("carbs")),
            ),
        )
        recipe_id = cur.lastrowid
        if not recipe_id:
            cur.execute("SELECT recipe_id FROM recipes WHERE source_slug = %s", (slug,))
            recipe_id = cur.fetchone()[0]

        # Replace child rows on re-run so the source stays authoritative.
        cur.execute("DELETE FROM recipe_steps WHERE recipe_id = %s", (recipe_id,))
        cur.execute("DELETE FROM recipe_ingredients WHERE recipe_id = %s", (recipe_id,))
        conn.commit()
        cur.close()

        # Ingredients
        ri_rows = []
        for line_no, item in enumerate(recipe.get("ingredients") or [], start=1):
            source_id = str(item.get("id") or f"{slug}-ingredient-{line_no}").strip()
            item_name = english_text(item.get("name")) or source_id
            ingredient_id = get_or_create_ingredient(
                conn, ingredient_cache, source_id, item_name
            )
            ri_rows.append(
                (
                    recipe_id,
                    ingredient_id,
                    line_no,
                    to_float(item.get("quantity")),
                    none_if_blank(item.get("unit")),
                    none_if_blank(item.get("scaling")),
                    english_text(item.get("note")),
                )
            )

        if ri_rows:
            cur = conn.cursor()
            cur.executemany(
                """
                INSERT INTO recipe_ingredients (
                    recipe_id, ingredient_id, line_no, quantity, unit, scaling, note
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                ri_rows,
            )
            conn.commit()
            cur.close()
            imported_lines += len(ri_rows)

        # Steps
        step_rows = []
        for step_no, step in enumerate(recipe.get("steps") or [], start=1):
            instruction = english_text(step.get("text"))
            if not instruction:
                continue
            step_rows.append(
                (
                    recipe_id,
                    step_no,
                    instruction,
                    to_int(step.get("minutes")),
                )
            )

        if step_rows:
            cur = conn.cursor()
            cur.executemany(
                """
                INSERT INTO recipe_steps (recipe_id, step_no, instruction, minutes)
                VALUES (%s, %s, %s, %s)
                """,
                step_rows,
            )
            conn.commit()
            cur.close()
            imported_steps += len(step_rows)

        imported_recipes += 1
        if index % 50 == 0 or index == len(recipes):
            log(f"  recipes imported: {index:,}/{len(recipes):,}")

    log(
        f"UniTools complete: {imported_recipes:,} recipes, "
        f"{imported_lines:,} recipe ingredient rows, "
        f"{imported_steps:,} steps."
    )
    log(
        "ingredient_food_map intentionally remains curated/empty for now; "
        "we will build verified mappings in a later step."
    )


def report_counts(conn) -> int:
    tables = [
        "countries",
        "recipe_categories",
        "recipes",
        "ingredients",
        "recipe_ingredients",
        "recipe_steps",
        "users",
        "pantry",
        "favorites",
        "food_categories",
        "food_items",
        "nutrients",
        "food_nutrients",
        "ingredient_food_map",
    ]

    cur = conn.cursor()
    grand_total = 0
    print("\n=== FOODWISE ROW COUNTS ===")
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM `{table}`")
        count = int(cur.fetchone()[0])
        grand_total += count
        print(f"{table:24s} {count:>12,}")
    print("-" * 38)
    print(f"{'TOTAL':24s} {grand_total:>12,}")
    print("===========================\n")
    cur.close()

    if grand_total >= 100_000:
        log("SUCCESS: Database contains at least 100,000 rows.")
    else:
        log("WARNING: Database is below the 100,000-row course requirement.")
    return grand_total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import FoodWise datasets into MySQL.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3307)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default=None, help="Prefer MYSQL_PASSWORD env var or prompt.")
    parser.add_argument("--database", default="foodwise")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--reset-data", action="store_true")
    parser.add_argument("--recipes-only", action="store_true")
    parser.add_argument("--usda-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.recipes_only and args.usda_only:
        print("Choose only one of --recipes-only / --usda-only.", file=sys.stderr)
        return 2

    data_dir: Path = args.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    unitools_path = data_dir / UNITOOLS_FILE
    usda_zip_path = data_dir / USDA_ZIP_FILE
    usda_extract_dir = data_dir / USDA_EXTRACT_DIR

    try:
        if not args.skip_download:
            if not args.usda_only:
                download_file(UNITOOLS_URL, unitools_path)
            if not args.recipes_only:
                download_file(USDA_SR_LEGACY_URL, usda_zip_path)

        if not args.recipes_only:
            if not usda_zip_path.exists():
                raise FileNotFoundError(
                    f"USDA ZIP is missing: {usda_zip_path}. "
                    "Run without --skip-download or place the ZIP there manually."
                )
            extract_usda(usda_zip_path, usda_extract_dir)

        if not args.usda_only and not unitools_path.exists():
            raise FileNotFoundError(
                f"UniTools JSON is missing: {unitools_path}. "
                "Run without --skip-download or place the JSON there manually."
            )

        conn = connect(args)
        try:
            verify_schema(conn)

            if args.reset_data:
                reset_imported_data(conn)

            if not args.recipes_only:
                import_usda(conn, usda_extract_dir)

            if not args.usda_only:
                import_unitools(conn, unitools_path)

            total = report_counts(conn)
        finally:
            conn.close()

        return 0 if total >= 100_000 else 1

    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130
    except (Error, OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
