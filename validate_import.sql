USE foodwise;

-- Row count per table
SELECT 'countries' AS table_name, COUNT(*) AS row_count FROM countries
UNION ALL SELECT 'recipe_categories', COUNT(*) FROM recipe_categories
UNION ALL SELECT 'recipes', COUNT(*) FROM recipes
UNION ALL SELECT 'ingredients', COUNT(*) FROM ingredients
UNION ALL SELECT 'recipe_ingredients', COUNT(*) FROM recipe_ingredients
UNION ALL SELECT 'recipe_steps', COUNT(*) FROM recipe_steps
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'pantry', COUNT(*) FROM pantry
UNION ALL SELECT 'favorites', COUNT(*) FROM favorites
UNION ALL SELECT 'food_categories', COUNT(*) FROM food_categories
UNION ALL SELECT 'food_items', COUNT(*) FROM food_items
UNION ALL SELECT 'nutrients', COUNT(*) FROM nutrients
UNION ALL SELECT 'food_nutrients', COUNT(*) FROM food_nutrients
UNION ALL SELECT 'ingredient_food_map', COUNT(*) FROM ingredient_food_map;

-- Total rows across all 14 tables
SELECT
    (SELECT COUNT(*) FROM countries) +
    (SELECT COUNT(*) FROM recipe_categories) +
    (SELECT COUNT(*) FROM recipes) +
    (SELECT COUNT(*) FROM ingredients) +
    (SELECT COUNT(*) FROM recipe_ingredients) +
    (SELECT COUNT(*) FROM recipe_steps) +
    (SELECT COUNT(*) FROM users) +
    (SELECT COUNT(*) FROM pantry) +
    (SELECT COUNT(*) FROM favorites) +
    (SELECT COUNT(*) FROM food_categories) +
    (SELECT COUNT(*) FROM food_items) +
    (SELECT COUNT(*) FROM nutrients) +
    (SELECT COUNT(*) FROM food_nutrients) +
    (SELECT COUNT(*) FROM ingredient_food_map)
    AS total_rows;

-- Quick integrity checks
SELECT COUNT(*) AS recipes_without_country
FROM recipes r
LEFT JOIN countries c ON c.country_code = r.country_code
WHERE r.country_code IS NOT NULL AND c.country_code IS NULL;

SELECT COUNT(*) AS orphan_food_nutrients
FROM food_nutrients fn
LEFT JOIN food_items f ON f.fdc_id = fn.fdc_id
LEFT JOIN nutrients n ON n.nutrient_id = fn.nutrient_id
WHERE f.fdc_id IS NULL OR n.nutrient_id IS NULL;

-- Example imported recipe data
SELECT
    r.recipe_id,
    r.name,
    r.country_code,
    rc.name AS category,
    COUNT(ri.recipe_ingredient_id) AS ingredient_count
FROM recipes r
LEFT JOIN recipe_categories rc ON rc.category_id = r.category_id
LEFT JOIN recipe_ingredients ri ON ri.recipe_id = r.recipe_id
GROUP BY r.recipe_id, r.name, r.country_code, rc.name
ORDER BY r.recipe_id
LIMIT 10;

-- Example USDA data
SELECT
    f.fdc_id,
    f.description,
    n.name AS nutrient,
    fn.amount,
    n.unit_name
FROM food_items f
JOIN food_nutrients fn ON fn.fdc_id = f.fdc_id
JOIN nutrients n ON n.nutrient_id = fn.nutrient_id
WHERE n.nutrient_id IN (1003, 1004, 1005, 1008, 1079, 1093)
ORDER BY f.fdc_id, n.nutrient_id
LIMIT 30;
