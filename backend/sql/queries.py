"""Adapted from FoodWise_Day5_Complex_Queries.sql (queries 1, 2, 3, 5).

Only trusted SQL constants are composed. All client values use connector bindings.
"""

HEALTH = "SELECT 1 AS connected"
DEMO_USER = "SELECT user_id FROM users WHERE username = %s"
RECIPE_EXISTS = "SELECT recipe_id FROM recipes WHERE recipe_id = %s"
INGREDIENT_EXISTS = "SELECT ingredient_id FROM ingredients WHERE ingredient_id = %s"
INGREDIENT_SEARCH = """
SELECT ingredient_id, name AS ingredient_name
FROM ingredients
WHERE name LIKE %s ESCAPE '!'
ORDER BY name, ingredient_id
LIMIT %s OFFSET %s
"""

RECIPE_COLUMNS = """
    r.recipe_id, r.source_slug, r.name AS recipe_name, r.native_name,
    r.summary, r.difficulty, r.base_servings, r.country_code,
    c.name AS country, rc.name AS category, r.prep_minutes, r.cook_minutes,
    COALESCE(r.prep_minutes, 0) + COALESCE(r.cook_minutes, 0) AS total_minutes,
    r.calories_per_serving, r.protein_g_per_serving,
    r.fat_g_per_serving, r.carbs_g_per_serving
"""
RECIPE_JOINS = """
    FROM recipes r
    LEFT JOIN countries c ON c.country_code = r.country_code
    LEFT JOIN recipe_categories rc ON rc.category_id = r.category_id
"""

# Day 5 query 3: optional SQL filters and original nutrition/time ordering.
RECIPE_SEARCH = "SELECT " + RECIPE_COLUMNS + RECIPE_JOINS + """
WHERE (%(name)s IS NULL OR r.name LIKE %(name)s ESCAPE '!')
  AND (%(country)s IS NULL OR r.country_code = %(country)s OR c.name = %(country)s)
  AND (%(category)s IS NULL OR rc.name = %(category)s)
  AND (%(max_minutes)s IS NULL OR
       COALESCE(r.prep_minutes, 0) + COALESCE(r.cook_minutes, 0) <= %(max_minutes)s)
  AND (%(max_calories)s IS NULL OR r.calories_per_serving <= %(max_calories)s)
  AND (%(min_protein)s IS NULL OR r.protein_g_per_serving >= %(min_protein)s)
ORDER BY r.protein_g_per_serving DESC, total_minutes ASC,
         r.calories_per_serving ASC, r.recipe_id ASC
LIMIT %(limit)s OFFSET %(offset)s
"""
RECIPE_DETAILS = "SELECT " + RECIPE_COLUMNS + RECIPE_JOINS + " WHERE r.recipe_id = %s"
RECIPE_INGREDIENTS = """
SELECT ri.recipe_ingredient_id, ri.line_no, i.ingredient_id, i.name AS ingredient_name,
       ri.quantity, ri.unit, ri.scaling, ri.note
FROM recipe_ingredients ri
JOIN ingredients i ON i.ingredient_id = ri.ingredient_id
WHERE ri.recipe_id = %s
ORDER BY ri.line_no, ri.recipe_ingredient_id
"""
RECIPE_STEPS = """
SELECT step_no, instruction, minutes FROM recipe_steps
WHERE recipe_id = %s ORDER BY step_no
"""

PANTRY_LIST = """
SELECT p.ingredient_id, i.name AS ingredient_name, p.quantity, p.unit, p.updated_at
FROM pantry p JOIN ingredients i ON i.ingredient_id = p.ingredient_id
WHERE p.user_id = %s ORDER BY i.name, i.ingredient_id
LIMIT %s OFFSET %s
"""
PANTRY_UPSERT = """
INSERT INTO pantry (user_id, ingredient_id, quantity, unit)
VALUES (%s, %s, %s, %s)
ON DUPLICATE KEY UPDATE quantity = %s, unit = %s, updated_at = CURRENT_TIMESTAMP
"""
PANTRY_DELETE = "DELETE FROM pantry WHERE user_id = %s AND ingredient_id = %s"

# Day 5 query 1: distinct ingredient presence, not quantities/unit conversion.
PANTRY_MATCH = """
SELECT r.recipe_id, r.name AS recipe_name,
       COUNT(DISTINCT ri.ingredient_id) AS total_ingredients,
       COUNT(DISTINCT p.ingredient_id) AS ingredients_in_pantry,
       COUNT(DISTINCT ri.ingredient_id) - COUNT(DISTINCT p.ingredient_id)
           AS missing_ingredients,
       ROUND(100.0 * COUNT(DISTINCT p.ingredient_id)
           / NULLIF(COUNT(DISTINCT ri.ingredient_id), 0), 1) AS pantry_match_percent
FROM recipes r
JOIN recipe_ingredients ri ON ri.recipe_id = r.recipe_id
LEFT JOIN pantry p ON p.ingredient_id = ri.ingredient_id AND p.user_id = %s
GROUP BY r.recipe_id, r.name
HAVING COUNT(DISTINCT ri.ingredient_id) > 0
ORDER BY pantry_match_percent DESC, missing_ingredients ASC,
         total_ingredients ASC, r.name, r.recipe_id
LIMIT %s OFFSET %s
"""

# Day 5 query 2: anti-join, with an unambiguous recipe ID instead of name.
MISSING_INGREDIENTS = """
SELECT r.recipe_id, r.name AS recipe_name, i.ingredient_id,
       i.name AS missing_ingredient, ri.quantity, ri.unit, ri.note
FROM recipes r
JOIN recipe_ingredients ri ON ri.recipe_id = r.recipe_id
JOIN ingredients i ON i.ingredient_id = ri.ingredient_id
LEFT JOIN pantry p ON p.ingredient_id = i.ingredient_id AND p.user_id = %s
WHERE r.recipe_id = %s AND p.ingredient_id IS NULL
ORDER BY ri.line_no, ri.recipe_ingredient_id
"""

FAVORITES_LIST = "SELECT " + RECIPE_COLUMNS + ", f.created_at " + RECIPE_JOINS + """
JOIN favorites f ON f.recipe_id = r.recipe_id
WHERE f.user_id = %s
ORDER BY f.created_at DESC, r.recipe_id
LIMIT %s OFFSET %s
"""
FAVORITES_ADD = """
INSERT INTO favorites (user_id, recipe_id) VALUES (%s, %s)
ON DUPLICATE KEY UPDATE recipe_id = %s
"""
FAVORITES_DELETE = "DELETE FROM favorites WHERE user_id = %s AND recipe_id = %s"

# Day 5 query 5: AVG ignores unknown nutrition; unknown time contributes zero.
PREFERENCES = """
SELECT rc.name AS category, COUNT(*) AS favorite_count,
       ROUND(AVG(r.calories_per_serving), 1) AS avg_calories,
       ROUND(AVG(r.protein_g_per_serving), 1) AS avg_protein_g,
       ROUND(AVG(COALESCE(r.prep_minutes, 0) + COALESCE(r.cook_minutes, 0)), 1)
           AS avg_total_minutes
FROM users u
JOIN favorites f ON f.user_id = u.user_id
JOIN recipes r ON r.recipe_id = f.recipe_id
LEFT JOIN recipe_categories rc ON rc.category_id = r.category_id
WHERE u.user_id = %s
GROUP BY rc.name
ORDER BY favorite_count DESC, avg_protein_g DESC, rc.name
"""
