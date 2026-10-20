-- FoodWise - Demo seed data
-- Purpose:
--   1) Give demo_user a realistic pantry
--   2) Give demo_user some favorites
--   3) Provide validation queries
--
-- Safe to re-run:
--   Uses INSERT ... ON DUPLICATE KEY UPDATE / INSERT IGNORE.

USE foodwise;

-- =========================================================
-- 1. Ensure demo user exists
-- =========================================================

INSERT INTO users (username)
VALUES ('demo_user')
ON DUPLICATE KEY UPDATE username = 'demo_user';

SET @demo_user_id := (
    SELECT user_id
    FROM users
    WHERE username = 'demo_user'
    LIMIT 1
);

-- =========================================================
-- 2. Fill pantry with up to 20 useful ingredients
--
-- We prefer common ingredients if they exist in the real
-- imported dataset. If fewer than 20 preferred names match,
-- the query falls back to the most-used ingredients in recipes.
-- =========================================================

INSERT INTO pantry (user_id, ingredient_id, quantity, unit)
SELECT
    @demo_user_id,
    ranked.ingredient_id,
    NULL,
    NULL
FROM (
    SELECT
        i.ingredient_id,
        i.name,
        COUNT(ri.recipe_id) AS usage_count,
        CASE
            WHEN LOWER(i.name) IN (
                'egg','eggs',
                'tomato','tomatoes',
                'onion','onions',
                'garlic',
                'rice',
                'chicken',
                'milk',
                'butter',
                'potato','potatoes',
                'cheese',
                'olive oil',
                'salt',
                'black pepper','pepper',
                'flour',
                'sugar',
                'carrot','carrots',
                'lemon',
                'parsley',
                'bread'
            ) THEN 0
            ELSE 1
        END AS priority_group
    FROM ingredients i
    LEFT JOIN recipe_ingredients ri
        ON ri.ingredient_id = i.ingredient_id
    GROUP BY i.ingredient_id, i.name
    ORDER BY priority_group ASC, usage_count DESC, i.name ASC
    LIMIT 20
) AS ranked
ON DUPLICATE KEY UPDATE
    updated_at = CURRENT_TIMESTAMP;

-- =========================================================
-- 3. Add 8 favorites
--
-- We pick recipes that actually have ingredient data.
-- This gives us useful records for later analytics queries.
-- =========================================================

INSERT IGNORE INTO favorites (user_id, recipe_id)
SELECT
    @demo_user_id,
    r.recipe_id
FROM recipes r
JOIN recipe_ingredients ri
    ON ri.recipe_id = r.recipe_id
GROUP BY r.recipe_id, r.name
ORDER BY COUNT(ri.recipe_ingredient_id) DESC, r.recipe_id ASC
LIMIT 8;

-- =========================================================
-- 4. Validation
-- =========================================================

SELECT
    u.username,
    i.ingredient_id,
    i.name AS ingredient_name,
    p.quantity,
    p.unit
FROM pantry p
JOIN users u
    ON u.user_id = p.user_id
JOIN ingredients i
    ON i.ingredient_id = p.ingredient_id
WHERE u.username = 'demo_user'
ORDER BY i.name;

SELECT
    COUNT(*) AS demo_pantry_count
FROM pantry
WHERE user_id = @demo_user_id;

SELECT
    u.username,
    r.recipe_id,
    r.name AS recipe_name,
    r.country_code,
    rc.name AS category
FROM favorites f
JOIN users u
    ON u.user_id = f.user_id
JOIN recipes r
    ON r.recipe_id = f.recipe_id
LEFT JOIN recipe_categories rc
    ON rc.category_id = r.category_id
WHERE u.username = 'demo_user'
ORDER BY r.name;

SELECT
    COUNT(*) AS demo_favorites_count
FROM favorites
WHERE user_id = @demo_user_id;

-- =========================================================
-- 5. Quick preview: pantry match candidate recipes
-- =========================================================

SELECT
    r.recipe_id,
    r.name,
    COUNT(DISTINCT ri.ingredient_id) AS total_ingredients,
    COUNT(DISTINCT p.ingredient_id) AS ingredients_in_pantry,
    ROUND(
        100 * COUNT(DISTINCT p.ingredient_id)
        / NULLIF(COUNT(DISTINCT ri.ingredient_id), 0),
        1
    ) AS pantry_match_percent
FROM recipes r
JOIN recipe_ingredients ri
    ON ri.recipe_id = r.recipe_id
LEFT JOIN pantry p
    ON p.user_id = @demo_user_id
   AND p.ingredient_id = ri.ingredient_id
GROUP BY r.recipe_id, r.name
HAVING total_ingredients > 0
ORDER BY pantry_match_percent DESC, total_ingredients ASC, r.name ASC
LIMIT 15;
