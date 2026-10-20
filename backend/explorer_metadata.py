"""Presentation metadata from schema.sql. It cannot supply executable SQL."""


def table(name, pk, fk=(), fields=()):
    return {"name": name, "primary_key": list(pk), "foreign_keys": list(fk),
            "fields": list(dict.fromkeys([*pk, *fk, *fields]))}


TABLES = [
    table("countries", ["country_code"], fields=["name"]),
    table("recipe_categories", ["category_id"], fields=["name"]),
    table("recipes", ["recipe_id"], ["country_code", "category_id"], ["name"]),
    table("recipe_steps", ["recipe_id", "step_no"], ["recipe_id"], ["instruction"]),
    table("users", ["user_id"], fields=["username"]),
    table("favorites", ["user_id", "recipe_id"], ["user_id", "recipe_id"]),
    table("recipe_ingredients", ["recipe_ingredient_id"], ["recipe_id", "ingredient_id"], ["quantity"]),
    table("ingredients", ["ingredient_id"], fields=["source_ingredient_id", "name"]),
    table("pantry", ["user_id", "ingredient_id"], ["user_id", "ingredient_id"], ["quantity"]),
    table("ingredient_food_map", ["ingredient_id", "fdc_id"], ["ingredient_id", "fdc_id"], ["is_primary"]),
    table("food_categories", ["food_category_id"], fields=["name"]),
    table("food_items", ["fdc_id"], ["food_category_id"], ["description"]),
    table("food_nutrients", ["food_nutrient_id"], ["fdc_id", "nutrient_id"], ["amount"]),
    table("nutrients", ["nutrient_id"], fields=["name", "unit_name"]),
]


def edge(key, source, target, kind="foreign_key"):
    return {"id": key, "source": source, "target": target, "kind": kind}


RELATIONSHIPS = [
    edge("recipe_country", "recipes.country_code", "countries.country_code"),
    edge("recipe_category", "recipes.category_id", "recipe_categories.category_id"),
    edge("line_recipe", "recipe_ingredients.recipe_id", "recipes.recipe_id"),
    edge("line_ingredient", "recipe_ingredients.ingredient_id", "ingredients.ingredient_id"),
    edge("step_recipe", "recipe_steps.recipe_id", "recipes.recipe_id"),
    edge("pantry_user", "pantry.user_id", "users.user_id"),
    edge("pantry_ingredient", "pantry.ingredient_id", "ingredients.ingredient_id"),
    edge("favorite_user", "favorites.user_id", "users.user_id"),
    edge("favorite_recipe", "favorites.recipe_id", "recipes.recipe_id"),
    edge("food_category", "food_items.food_category_id", "food_categories.food_category_id"),
    edge("nutrient_food", "food_nutrients.fdc_id", "food_items.fdc_id"),
    edge("nutrient_kind", "food_nutrients.nutrient_id", "nutrients.nutrient_id"),
    edge("map_ingredient", "ingredient_food_map.ingredient_id", "ingredients.ingredient_id"),
    edge("map_food", "ingredient_food_map.fdc_id", "food_items.fdc_id"),
]

# Actual equijoins that are NOT direct FK constraints, distinguished in the UI.
QUERY_JOINS = [
    edge("line_pantry", "recipe_ingredients.ingredient_id", "pantry.ingredient_id", "query_join"),
    edge("ingredient_pantry", "ingredients.ingredient_id", "pantry.ingredient_id", "query_join"),
]


def step(title, description, tables, joins=(), clauses=()):
    return {"title": title, "description": description, "tables": tables,
            "relationships": list(joins), "clauses": list(clauses)}


DEFINITIONS = {
    "pantry_match": {
        "name": "Pantry Match",
        "description": "Rank recipes by distinct ingredient IDs already present in demo_user's pantry.",
        "source": "backend/sql/queries.py · PANTRY_MATCH (Day 5 query 1)",
        "concepts": ["JOIN", "LEFT JOIN", "GROUP BY", "HAVING", "COUNT(DISTINCT)", "NULLIF", "ROUND"],
        "tables": ["recipes", "recipe_ingredients", "pantry"],
        "relationships": ["line_recipe", "line_pantry"],
        "parameters": {},
        "user_lookup": True,
        "steps": [
            step("Start with recipes", "The main SELECT starts with recipe records. demo_user's ID is resolved by a separate lookup.", ["recipes"], clauses=["FROM recipes"]),
            step("Join recipe ingredients", "An inner join keeps recipes with ingredient lines. Repeated lines can reference the same ingredient ID.", ["recipes", "recipe_ingredients"], ["line_recipe"], ["JOIN recipe_ingredients"]),
            step("Compare with the pantry", "A LEFT JOIN keeps every required ingredient, even when no row matches this user's pantry.", ["recipe_ingredients", "pantry"], ["line_pantry"], ["LEFT JOIN pantry"]),
            step("Group by recipe", "Each recipe's joined rows become a group.", ["recipes", "recipe_ingredients", "pantry"], clauses=["GROUP BY"]),
            step("Count distinct ingredients", "Count distinct IDs on both sides. Identical names with different IDs stay distinct. NULL pantry IDs are not counted.", ["recipe_ingredients", "pantry"], clauses=["COUNT(DISTINCT"]),
            step("Calculate the percentage", "Divide available by required ingredients, guard division with NULLIF, and round to one decimal place.", ["recipe_ingredients", "pantry"], clauses=["ROUND(", "NULLIF("]),
            step("Rank the results", "Highest match first, then fewer missing ingredients, fewer total ingredients, name, and recipe ID.", ["recipes"], clauses=["ORDER BY", "pantry_match_percent DESC", "LIMIT"]),
            step("Inspect the real plan", "The diagram is a logical explanation. MySQL may choose a different physical order; inspect EXPLAIN ANALYZE below.", ["recipes", "recipe_ingredients", "pantry"]),
        ],
    },
    "missing_ingredients": {
        "name": "Missing Ingredients",
        "description": "Find recipe ingredient lines with no matching pantry record for demo_user.",
        "source": "backend/sql/queries.py · MISSING_INGREDIENTS (Day 5 query 2)",
        "concepts": ["JOIN", "LEFT JOIN", "Anti-join", "IS NULL"],
        "tables": ["recipes", "recipe_ingredients", "ingredients", "pantry"],
        "relationships": ["line_recipe", "line_ingredient", "ingredient_pantry"],
        "parameters": {"recipe_id": {"label": "Recipe ID (blank: best partially matched recipe)", "type": "integer", "default": None, "min": 1}},
        "user_lookup": True,
        "steps": [
            step("Select a recipe", "Use a bound recipe ID. The default is selected from real pantry recommendations.", ["recipes"], clauses=["WHERE r.recipe_id"]),
            step("Read ingredient lines", "Join ingredient IDs to their names, preserving quantities, units, and notes.", ["recipes", "recipe_ingredients", "ingredients"], ["line_recipe", "line_ingredient"], ["JOIN recipe_ingredients", "JOIN ingredients"]),
            step("Compare with this pantry", "Keep recipe lines whether or not their ingredient ID is in the pantry.", ["ingredients", "pantry"], ["ingredient_pantry"], ["LEFT JOIN pantry"]),
            step("Keep only missing lines", "The unmatched side of the LEFT JOIN is NULL. Filter on that NULL and preserve line order.", ["recipe_ingredients", "pantry"], clauses=["p.ingredient_id IS NULL", "ORDER BY"]),
        ],
    },
    "smart_filter": {
        "name": "Smart Recipe Filter",
        "description": "Combine time, nutrition, country, category, and name filters inside MySQL.",
        "source": "backend/sql/queries.py · RECIPE_SEARCH (Day 5 query 3)",
        "concepts": ["LEFT JOIN", "Parameterized filters", "COALESCE", "ORDER BY"],
        "tables": ["recipes", "countries", "recipe_categories"],
        "relationships": ["recipe_country", "recipe_category"],
        "parameters": {
            "name": {"label": "Recipe name", "type": "text", "default": None, "max_length": 200},
            "country": {"label": "Country name or code", "type": "text", "default": None, "max_length": 100},
            "category": {"label": "Category", "type": "text", "default": None, "max_length": 100},
            "max_minutes": {"label": "Maximum total minutes", "type": "number", "default": 60, "min": 0},
            "max_calories": {"label": "Maximum calories", "type": "number", "default": 700, "min": 0},
            "min_protein": {"label": "Minimum protein (g)", "type": "number", "default": 10, "min": 0},
        },
        "steps": [
            step("Read recipes", "Start with the existing recipe and nutrition columns.", ["recipes"], clauses=["SELECT", "FROM recipes"]),
            step("Attach country and category", "LEFT JOIN keeps recipes even if optional country/category metadata is absent.", ["recipes", "countries", "recipe_categories"], ["recipe_country", "recipe_category"], ["LEFT JOIN"]),
            step("Apply optional filters", "NULL disables a filter. Known filters use bound values; missing prep/cook time contributes zero, matching the app.", ["recipes", "countries", "recipe_categories"], clauses=["WHERE", "AND (", "COALESCE"]),
            step("Order and limit", "Rank by protein descending, time ascending, calories ascending, then recipe ID. Return a bounded result.", ["recipes"], clauses=["ORDER BY", "LIMIT"]),
        ],
    },
    "top_ingredients_country": {
        "name": "Top Ingredients by Country",
        "description": "Aggregate ingredient usage, then rank within each country using a window function.",
        "source": "Day 5 query 4 · unchanged CTE/ranking logic, outer demo LIMIT 20",
        "concepts": ["CTE", "JOIN", "GROUP BY", "COUNT(DISTINCT)", "DENSE_RANK", "PARTITION BY"],
        "tables": ["countries", "recipes", "recipe_ingredients", "ingredients"],
        "relationships": ["recipe_country", "line_recipe", "line_ingredient"],
        "parameters": {},
        "steps": [
            step("Follow country to ingredients", "Join each country to recipes, ingredient lines, and ingredient names.", ["countries", "recipes", "recipe_ingredients", "ingredients"], ["recipe_country", "line_recipe", "line_ingredient"], ["FROM countries", "JOIN"]),
            step("Aggregate usage in a CTE", "Count distinct recipes using each ingredient ID within each country.", ["countries", "recipes", "ingredients"], clauses=["WITH ingredient_usage", "COUNT(DISTINCT", "GROUP BY"]),
            step("Rank within country", "DENSE_RANK partitions by country. Day 5's ordering also includes ingredient name, so different names break equal-usage ties.", ["countries", "ingredients"], clauses=["ranked AS", "DENSE_RANK", "PARTITION BY", "ORDER BY recipes_using"]),
            step("Keep the top five ranks", "Filter to rank 5 or less per country, then sort. The preview's outer LIMIT applies after ranking.", ["countries", "ingredients"], clauses=["WHERE ingredient_rank", "ORDER BY country", "LIMIT"]),
        ],
    },
    "favorite_preferences": {
        "name": "Favorites Preferences",
        "description": "Group demo_user's favorites by category and calculate average nutrition and total time.",
        "source": "backend/sql/queries.py · PREFERENCES (Day 5 query 5)",
        "concepts": ["JOIN", "LEFT JOIN", "GROUP BY", "COUNT", "AVG", "COALESCE"],
        "tables": ["users", "favorites", "recipes", "recipe_categories"],
        "relationships": ["favorite_user", "favorite_recipe", "recipe_category"],
        "parameters": {},
        "user_lookup": True,
        "steps": [
            step("Select this user's favorites", "Use demo_user's resolved ID. Join users to saved recipe IDs.", ["users", "favorites"], ["favorite_user"], ["FROM users", "JOIN favorites", "WHERE u.user_id"]),
            step("Read recipes and categories", "Join nutrition/time data; keep uncategorized recipes with a LEFT JOIN.", ["favorites", "recipes", "recipe_categories"], ["favorite_recipe", "recipe_category"], ["JOIN recipes", "LEFT JOIN recipe_categories"]),
            step("Group and calculate averages", "COUNT counts favorites. AVG ignores NULL nutrition; missing time is COALESCE'd to zero.", ["recipes", "recipe_categories"], clauses=["COUNT(", "AVG(", "COALESCE", "GROUP BY"]),
            step("Order category preferences", "Highest favorite count first; protein and category break ties.", ["recipe_categories"], clauses=["ORDER BY"]),
        ],
    },
    "usda_comparison": {
        "name": "USDA Nutrition Comparison",
        "description": "Pivot USDA nutrient rows into macro columns and compare high-protein food items.",
        "source": "Day 5 query 6 · bound protein/LIMIT; equivalent nutrient-name filter before aggregation",
        "concepts": ["CTE", "JOIN", "LEFT JOIN", "GROUP BY", "MAX(CASE WHEN)", "Conditional aggregation"],
        "tables": ["food_items", "food_categories", "food_nutrients", "nutrients"],
        "relationships": ["food_category", "nutrient_food", "nutrient_kind"],
        "parameters": {"min_protein": {"label": "Minimum USDA protein (g)", "type": "number", "default": 20, "min": 0}},
        "steps": [
            step("Read food items and categories", "LEFT JOIN retains food items without a category.", ["food_items", "food_categories"], ["food_category"], ["FROM food_items", "LEFT JOIN food_categories"]),
            step("Join nutrient measurements", "Follow food_nutrients to nutrient names and units. Skip unrelated nutrient names: they contribute NULL to every displayed macro and cannot satisfy the final protein filter.", ["food_items", "food_nutrients", "nutrients"], ["nutrient_food", "nutrient_kind"], ["JOIN food_nutrients", "JOIN nutrients", "WHERE n.name"]),
            step("Pivot with conditional aggregation", "MAX(CASE WHEN...) extracts each macro. Energy uses the KCAL unit; group one row per food in the CTE.", ["food_items", "food_nutrients", "nutrients"], clauses=["WITH food_macros", "MAX(CASE", "THEN fn.amount", "GROUP BY"]),
            step("Filter and compare", "Filter the aggregated protein column, then rank protein descending and calories ascending. These are USDA food values, not recipe-serving nutrition.", ["food_items", "food_nutrients"], clauses=["WHERE protein_g", "ORDER BY protein_g", "LIMIT"]),
        ],
    },
}
