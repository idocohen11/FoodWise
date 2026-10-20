-- FoodWise - Day 5
-- Complex SQL Queries
-- MySQL 8.x
--
-- Each query is designed to be meaningful in the application
-- and to combine data from multiple tables.
--
-- Assumption: demo_user already exists and has pantry + favorites.

USE foodwise;

SET @username := 'demo_user';

-- =========================================================
-- QUERY 1 - PANTRY MATCH
-- "What can I cook with what I already have?"
--
-- Tables:
-- users, pantry, recipes, recipe_ingredients
--
-- Complexity:
-- JOINs + LEFT JOIN + GROUP BY + COUNT(DISTINCT) + percentage
-- =========================================================

SELECT
    r.recipe_id,
    r.name AS recipe_name,
    COUNT(DISTINCT ri.ingredient_id) AS total_ingredients,
    COUNT(DISTINCT p.ingredient_id) AS ingredients_in_pantry,
    COUNT(DISTINCT ri.ingredient_id)
        - COUNT(DISTINCT p.ingredient_id) AS missing_ingredients,
    ROUND(
        100.0 * COUNT(DISTINCT p.ingredient_id)
        / NULLIF(COUNT(DISTINCT ri.ingredient_id), 0),
        1
    ) AS pantry_match_percent
FROM recipes r
JOIN recipe_ingredients ri
    ON ri.recipe_id = r.recipe_id
LEFT JOIN pantry p
    ON p.ingredient_id = ri.ingredient_id
   AND p.user_id = (
       SELECT user_id
       FROM users
       WHERE username = @username
       LIMIT 1
   )
GROUP BY
    r.recipe_id,
    r.name
HAVING COUNT(DISTINCT ri.ingredient_id) > 0
ORDER BY
    pantry_match_percent DESC,
    missing_ingredients ASC,
    total_ingredients ASC,
    r.name
LIMIT 20;


-- =========================================================
-- QUERY 2 - MISSING INGREDIENTS
-- "What exactly am I missing for a selected recipe?"
--
-- Change the recipe name if you want.
-- Example chosen because it matched 100% in the demo.
--
-- Tables:
-- users, pantry, recipes, recipe_ingredients, ingredients
--
-- Complexity:
-- multi-table JOIN + anti-join logic using LEFT JOIN ... IS NULL
-- =========================================================

SET @selected_recipe := 'Kenyan chapati';

SELECT
    r.recipe_id,
    r.name AS recipe_name,
    i.ingredient_id,
    i.name AS missing_ingredient,
    ri.quantity,
    ri.unit,
    ri.note
FROM recipes r
JOIN recipe_ingredients ri
    ON ri.recipe_id = r.recipe_id
JOIN ingredients i
    ON i.ingredient_id = ri.ingredient_id
LEFT JOIN pantry p
    ON p.ingredient_id = i.ingredient_id
   AND p.user_id = (
       SELECT user_id
       FROM users
       WHERE username = @username
       LIMIT 1
   )
WHERE r.name = @selected_recipe
  AND p.ingredient_id IS NULL
ORDER BY ri.line_no;


-- =========================================================
-- QUERY 3 - SMART RECIPE FILTER
-- "Find recipes that fit time + nutrition + country/category."
--
-- Tables:
-- recipes, countries, recipe_categories
--
-- Complexity:
-- joins + multiple dynamic filters + calculated total time
--
-- Set variables to NULL to ignore a filter.
-- =========================================================

SET @max_total_minutes := 60;
SET @max_calories := 700;
SET @min_protein := 10;
SET @country_code := NULL;   -- e.g. 'ES'
SET @category_name := NULL;  -- e.g. 'main'

SELECT
    r.recipe_id,
    r.name AS recipe_name,
    c.name AS country,
    rc.name AS category,
    r.prep_minutes,
    r.cook_minutes,
    COALESCE(r.prep_minutes, 0) + COALESCE(r.cook_minutes, 0) AS total_minutes,
    r.calories_per_serving,
    r.protein_g_per_serving,
    r.fat_g_per_serving,
    r.carbs_g_per_serving
FROM recipes r
LEFT JOIN countries c
    ON c.country_code = r.country_code
LEFT JOIN recipe_categories rc
    ON rc.category_id = r.category_id
WHERE
    (@max_total_minutes IS NULL
        OR COALESCE(r.prep_minutes, 0) + COALESCE(r.cook_minutes, 0) <= @max_total_minutes)
    AND (@max_calories IS NULL
        OR r.calories_per_serving <= @max_calories)
    AND (@min_protein IS NULL
        OR r.protein_g_per_serving >= @min_protein)
    AND (@country_code IS NULL
        OR r.country_code = @country_code)
    AND (@category_name IS NULL
        OR rc.name = @category_name)
ORDER BY
    r.protein_g_per_serving DESC,
    total_minutes ASC,
    r.calories_per_serving ASC
LIMIT 30;


-- =========================================================
-- QUERY 4 - TOP INGREDIENTS BY COUNTRY
-- "Which ingredients are most common in each country's recipes?"
--
-- Tables:
-- countries, recipes, recipe_ingredients, ingredients
--
-- Complexity:
-- CTE + aggregation + window function (DENSE_RANK)
-- =========================================================

WITH ingredient_usage AS (
    SELECT
        c.country_code,
        c.name AS country_name,
        i.ingredient_id,
        i.name AS ingredient_name,
        COUNT(DISTINCT r.recipe_id) AS recipes_using_ingredient
    FROM countries c
    JOIN recipes r
        ON r.country_code = c.country_code
    JOIN recipe_ingredients ri
        ON ri.recipe_id = r.recipe_id
    JOIN ingredients i
        ON i.ingredient_id = ri.ingredient_id
    GROUP BY
        c.country_code,
        c.name,
        i.ingredient_id,
        i.name
),
ranked AS (
    SELECT
        *,
        DENSE_RANK() OVER (
            PARTITION BY country_code
            ORDER BY recipes_using_ingredient DESC, ingredient_name
        ) AS ingredient_rank
    FROM ingredient_usage
)
SELECT
    country_code,
    country_name,
    ingredient_rank,
    ingredient_name,
    recipes_using_ingredient
FROM ranked
WHERE ingredient_rank <= 5
ORDER BY
    country_name,
    ingredient_rank,
    ingredient_name;


-- =========================================================
-- QUERY 5 - FAVORITES INSIGHTS
-- "What does the user's favorites list say about their preferences?"
--
-- Tables:
-- users, favorites, recipes, countries, recipe_categories
--
-- Complexity:
-- 5-table join + grouping + aggregation
-- =========================================================

SELECT
    u.username,
    rc.name AS favorite_category,
    COUNT(*) AS favorite_count,

    ROUND(AVG(r.calories_per_serving), 1) AS avg_calories,
    ROUND(AVG(r.protein_g_per_serving), 1) AS avg_protein_g,

    ROUND(
        AVG(
            COALESCE(r.prep_minutes, 0)
            + COALESCE(r.cook_minutes, 0)
        ),
        1
    ) AS avg_total_minutes

FROM users u

JOIN favorites f
    ON f.user_id = u.user_id

JOIN recipes r
    ON r.recipe_id = f.recipe_id

LEFT JOIN recipe_categories rc
    ON rc.category_id = r.category_id

WHERE u.username = 'demo_user'

GROUP BY
    u.username,
    rc.name

ORDER BY
    favorite_count DESC,
    avg_protein_g DESC;


-- =========================================================
-- QUERY 6 - USDA NUTRITION COMPARISON (BONUS / BACKUP)
-- "Find high-protein foods and compare key nutrients."
--
-- Tables:
-- food_items, food_categories, food_nutrients, nutrients
--
-- Complexity:
-- 4-table join + conditional aggregation (pivot) + HAVING
-- =========================================================

WITH food_macros AS (
    SELECT
        f.fdc_id,
        f.description,
        fc.name AS food_category,
        MAX(CASE WHEN n.name = 'Protein'
                 THEN fn.amount END) AS protein_g,
        MAX(CASE WHEN n.name = 'Total lipid (fat)'
                 THEN fn.amount END) AS fat_g,
        MAX(CASE WHEN n.name = 'Carbohydrate, by difference'
                 THEN fn.amount END) AS carbs_g,
        MAX(CASE WHEN n.name = 'Energy'
                  AND n.unit_name = 'KCAL'
                 THEN fn.amount END) AS calories_kcal,
        MAX(CASE WHEN n.name = 'Fiber, total dietary'
                 THEN fn.amount END) AS fiber_g,
        MAX(CASE WHEN n.name = 'Sodium, Na'
                 THEN fn.amount END) AS sodium_mg
    FROM food_items f
    LEFT JOIN food_categories fc
        ON fc.food_category_id = f.food_category_id
    JOIN food_nutrients fn
        ON fn.fdc_id = f.fdc_id
    JOIN nutrients n
        ON n.nutrient_id = fn.nutrient_id
    GROUP BY
        f.fdc_id,
        f.description,
        fc.name
)
SELECT
    fdc_id,
    description,
    food_category,
    protein_g,
    fat_g,
    carbs_g,
    calories_kcal,
    fiber_g,
    sodium_mg
FROM food_macros
WHERE protein_g IS NOT NULL
  AND protein_g >= 20
ORDER BY
    protein_g DESC,
    calories_kcal ASC
LIMIT 30;
