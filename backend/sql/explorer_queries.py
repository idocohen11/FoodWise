"""Fixed read-only query registry. Never populated from request data.

The four existing application queries are reused verbatim. The two CTE queries
retain Day 5 logic, with a bound outer LIMIT for a small, repeatable demo result.
USDA drops unrelated nutrient names before aggregation; these rows contribute
only NULL to every CASE expression and cannot affect the final protein filter.
"""

from types import MappingProxyType

from backend.sql import queries

TOP_INGREDIENTS_COUNTRY = """
WITH ingredient_usage AS (
    SELECT c.country_code, c.name AS country_name,
           i.ingredient_id, i.name AS ingredient_name,
           COUNT(DISTINCT r.recipe_id) AS recipes_using_ingredient
    FROM countries c
    JOIN recipes r ON r.country_code = c.country_code
    JOIN recipe_ingredients ri ON ri.recipe_id = r.recipe_id
    JOIN ingredients i ON i.ingredient_id = ri.ingredient_id
    GROUP BY c.country_code, c.name, i.ingredient_id, i.name
),
ranked AS (
    SELECT *,
           DENSE_RANK() OVER (
               PARTITION BY country_code
               ORDER BY recipes_using_ingredient DESC, ingredient_name
           ) AS ingredient_rank
    FROM ingredient_usage
)
SELECT country_code, country_name, ingredient_rank,
       ingredient_name, recipes_using_ingredient
FROM ranked
WHERE ingredient_rank <= 5
ORDER BY country_name, ingredient_rank, ingredient_name
LIMIT %s
"""

USDA_COMPARISON = """
WITH food_macros AS (
    SELECT f.fdc_id, f.description, fc.name AS food_category,
           MAX(CASE WHEN n.name = 'Protein'
                    THEN fn.amount END) AS protein_g,
           MAX(CASE WHEN n.name = 'Total lipid (fat)'
                    THEN fn.amount END) AS fat_g,
           MAX(CASE WHEN n.name = 'Carbohydrate, by difference'
                    THEN fn.amount END) AS carbs_g,
           MAX(CASE WHEN n.name = 'Energy' AND n.unit_name = 'KCAL'
                    THEN fn.amount END) AS calories_kcal,
           MAX(CASE WHEN n.name = 'Fiber, total dietary'
                    THEN fn.amount END) AS fiber_g,
           MAX(CASE WHEN n.name = 'Sodium, Na'
                    THEN fn.amount END) AS sodium_mg
    FROM food_items f
    LEFT JOIN food_categories fc ON fc.food_category_id = f.food_category_id
    JOIN food_nutrients fn ON fn.fdc_id = f.fdc_id
    JOIN nutrients n ON n.nutrient_id = fn.nutrient_id
    WHERE n.name IN (
        'Protein', 'Total lipid (fat)', 'Carbohydrate, by difference',
        'Energy', 'Fiber, total dietary', 'Sodium, Na'
    )
    GROUP BY f.fdc_id, f.description, fc.name
)
SELECT fdc_id, description, food_category, protein_g, fat_g,
       carbs_g, calories_kcal, fiber_g, sodium_mg
FROM food_macros
WHERE protein_g IS NOT NULL AND protein_g >= %s
ORDER BY protein_g DESC, calories_kcal ASC
LIMIT %s
"""

SQL = MappingProxyType({
    "pantry_match": queries.PANTRY_MATCH,
    "missing_ingredients": queries.MISSING_INGREDIENTS,
    "smart_filter": queries.RECIPE_SEARCH,
    "top_ingredients_country": TOP_INGREDIENTS_COUNTRY,
    "favorite_preferences": queries.PREFERENCES,
    "usda_comparison": USDA_COMPARISON,
})

# Fixed session controls; these affect this connection only, not stored data.
TIME_LIMIT = "SET SESSION max_execution_time = 8000"
