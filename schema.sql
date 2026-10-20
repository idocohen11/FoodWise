-- FoodWise - MySQL 8.x schema
-- Generated from ERD V1
-- Project: Workshop in Data Management
-- Notes:
--   * No ORM assumptions.
--   * Uses InnoDB + utf8mb4.
--   * Safe to run on a fresh MySQL 8.x instance.

CREATE DATABASE IF NOT EXISTS foodwise
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE foodwise;

-- =========================================================
-- 1. RECIPE DOMAIN
-- =========================================================

CREATE TABLE countries (
    country_code CHAR(2) NOT NULL,
    name VARCHAR(100) NOT NULL,

    CONSTRAINT pk_countries PRIMARY KEY (country_code),
    CONSTRAINT uq_countries_name UNIQUE (name)
) ENGINE=InnoDB;

CREATE TABLE recipe_categories (
    category_id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,

    CONSTRAINT pk_recipe_categories PRIMARY KEY (category_id),
    CONSTRAINT uq_recipe_categories_name UNIQUE (name)
) ENGINE=InnoDB;

CREATE TABLE recipes (
    recipe_id BIGINT NOT NULL AUTO_INCREMENT,
    source_slug VARCHAR(150) NOT NULL,

    country_code CHAR(2) NULL,
    category_id INT NULL,

    name VARCHAR(200) NOT NULL,
    native_name VARCHAR(200) NULL,
    summary TEXT NULL,
    difficulty VARCHAR(20) NULL,

    base_servings SMALLINT NULL,
    prep_minutes SMALLINT NULL,
    cook_minutes SMALLINT NULL,

    calories_per_serving DECIMAL(10,2) NULL,
    protein_g_per_serving DECIMAL(10,2) NULL,
    fat_g_per_serving DECIMAL(10,2) NULL,
    carbs_g_per_serving DECIMAL(10,2) NULL,

    CONSTRAINT pk_recipes PRIMARY KEY (recipe_id),
    CONSTRAINT uq_recipes_source_slug UNIQUE (source_slug),

    CONSTRAINT chk_recipes_base_servings
        CHECK (base_servings IS NULL OR base_servings > 0),

    CONSTRAINT chk_recipes_prep_minutes
        CHECK (prep_minutes IS NULL OR prep_minutes >= 0),

    CONSTRAINT chk_recipes_cook_minutes
        CHECK (cook_minutes IS NULL OR cook_minutes >= 0),

    CONSTRAINT chk_recipes_calories
        CHECK (calories_per_serving IS NULL OR calories_per_serving >= 0),

    CONSTRAINT chk_recipes_protein
        CHECK (protein_g_per_serving IS NULL OR protein_g_per_serving >= 0),

    CONSTRAINT chk_recipes_fat
        CHECK (fat_g_per_serving IS NULL OR fat_g_per_serving >= 0),

    CONSTRAINT chk_recipes_carbs
        CHECK (carbs_g_per_serving IS NULL OR carbs_g_per_serving >= 0),

    CONSTRAINT fk_recipes_country
        FOREIGN KEY (country_code)
        REFERENCES countries(country_code)
        ON UPDATE CASCADE
        ON DELETE SET NULL,

    CONSTRAINT fk_recipes_category
        FOREIGN KEY (category_id)
        REFERENCES recipe_categories(category_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX idx_recipes_country
    ON recipes(country_code);

CREATE INDEX idx_recipes_category
    ON recipes(category_id);

CREATE INDEX idx_recipes_name
    ON recipes(name);

CREATE TABLE ingredients (
    ingredient_id BIGINT NOT NULL AUTO_INCREMENT,
    source_ingredient_id VARCHAR(100) NULL,
    name VARCHAR(150) NOT NULL,

    CONSTRAINT pk_ingredients PRIMARY KEY (ingredient_id),
    CONSTRAINT uq_ingredients_source_id UNIQUE (source_ingredient_id)
) ENGINE=InnoDB;

CREATE INDEX idx_ingredients_name
    ON ingredients(name);

CREATE TABLE recipe_ingredients (
    recipe_ingredient_id BIGINT NOT NULL AUTO_INCREMENT,

    recipe_id BIGINT NOT NULL,
    ingredient_id BIGINT NOT NULL,

    line_no INT NULL,
    quantity DECIMAL(10,3) NULL,
    unit VARCHAR(50) NULL,
    scaling VARCHAR(50) NULL,
    note VARCHAR(255) NULL,

    CONSTRAINT pk_recipe_ingredients
        PRIMARY KEY (recipe_ingredient_id),

    -- A recipe line number should be unique inside a recipe.
    CONSTRAINT uq_recipe_ingredients_line
        UNIQUE (recipe_id, line_no),

    CONSTRAINT chk_recipe_ingredients_line_no
        CHECK (line_no IS NULL OR line_no > 0),

    CONSTRAINT chk_recipe_ingredients_quantity
        CHECK (quantity IS NULL OR quantity >= 0),

    CONSTRAINT fk_recipe_ingredients_recipe
        FOREIGN KEY (recipe_id)
        REFERENCES recipes(recipe_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT fk_recipe_ingredients_ingredient
        FOREIGN KEY (ingredient_id)
        REFERENCES ingredients(ingredient_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE INDEX idx_recipe_ingredients_recipe_ingredient
    ON recipe_ingredients(recipe_id, ingredient_id);

CREATE INDEX idx_recipe_ingredients_ingredient
    ON recipe_ingredients(ingredient_id);

CREATE TABLE recipe_steps (
    recipe_id BIGINT NOT NULL,
    step_no INT NOT NULL,
    instruction TEXT NOT NULL,
    minutes INT NULL,

    CONSTRAINT pk_recipe_steps
        PRIMARY KEY (recipe_id, step_no),

    CONSTRAINT chk_recipe_steps_step_no
        CHECK (step_no > 0),

    CONSTRAINT chk_recipe_steps_minutes
        CHECK (minutes IS NULL OR minutes >= 0),

    CONSTRAINT fk_recipe_steps_recipe
        FOREIGN KEY (recipe_id)
        REFERENCES recipes(recipe_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
) ENGINE=InnoDB;


-- =========================================================
-- 2. USER DOMAIN
-- =========================================================

CREATE TABLE users (
    user_id BIGINT NOT NULL AUTO_INCREMENT,
    username VARCHAR(100) NOT NULL,

    CONSTRAINT pk_users PRIMARY KEY (user_id),
    CONSTRAINT uq_users_username UNIQUE (username)
) ENGINE=InnoDB;

CREATE TABLE pantry (
    user_id BIGINT NOT NULL,
    ingredient_id BIGINT NOT NULL,

    quantity DECIMAL(10,3) NULL,
    unit VARCHAR(50) NULL,
    updated_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT pk_pantry
        PRIMARY KEY (user_id, ingredient_id),

    CONSTRAINT chk_pantry_quantity
        CHECK (quantity IS NULL OR quantity >= 0),

    CONSTRAINT fk_pantry_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT fk_pantry_ingredient
        FOREIGN KEY (ingredient_id)
        REFERENCES ingredients(ingredient_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE INDEX idx_pantry_ingredient
    ON pantry(ingredient_id);

CREATE TABLE favorites (
    user_id BIGINT NOT NULL,
    recipe_id BIGINT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_favorites
        PRIMARY KEY (user_id, recipe_id),

    CONSTRAINT fk_favorites_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT fk_favorites_recipe
        FOREIGN KEY (recipe_id)
        REFERENCES recipes(recipe_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_favorites_recipe
    ON favorites(recipe_id);


-- =========================================================
-- 3. USDA / FOOD DATA DOMAIN
-- =========================================================

CREATE TABLE food_categories (
    food_category_id INT NOT NULL,
    name VARCHAR(200) NOT NULL,

    CONSTRAINT pk_food_categories
        PRIMARY KEY (food_category_id)
) ENGINE=InnoDB;

CREATE TABLE food_items (
    fdc_id BIGINT NOT NULL,
    description VARCHAR(500) NOT NULL,
    data_type VARCHAR(100) NULL,
    food_category_id INT NULL,

    CONSTRAINT pk_food_items
        PRIMARY KEY (fdc_id),

    CONSTRAINT fk_food_items_category
        FOREIGN KEY (food_category_id)
        REFERENCES food_categories(food_category_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX idx_food_items_category
    ON food_items(food_category_id);

CREATE INDEX idx_food_items_data_type
    ON food_items(data_type);

CREATE TABLE nutrients (
    nutrient_id INT NOT NULL,
    name VARCHAR(200) NOT NULL,
    unit_name VARCHAR(50) NULL,

    CONSTRAINT pk_nutrients
        PRIMARY KEY (nutrient_id)
) ENGINE=InnoDB;

CREATE INDEX idx_nutrients_name
    ON nutrients(name);

CREATE TABLE food_nutrients (
    food_nutrient_id BIGINT NOT NULL,

    fdc_id BIGINT NOT NULL,
    nutrient_id INT NOT NULL,
    amount DECIMAL(15,5) NULL,

    CONSTRAINT pk_food_nutrients
        PRIMARY KEY (food_nutrient_id),

    CONSTRAINT chk_food_nutrients_amount
        CHECK (amount IS NULL OR amount >= 0),

    CONSTRAINT fk_food_nutrients_food
        FOREIGN KEY (fdc_id)
        REFERENCES food_items(fdc_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT fk_food_nutrients_nutrient
        FOREIGN KEY (nutrient_id)
        REFERENCES nutrients(nutrient_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_food_nutrients_food_nutrient
    ON food_nutrients(fdc_id, nutrient_id);

CREATE INDEX idx_food_nutrients_nutrient_amount
    ON food_nutrients(nutrient_id, amount);


-- =========================================================
-- 4. DATA-INTEGRATION BRIDGE
-- =========================================================

CREATE TABLE ingredient_food_map (
    ingredient_id BIGINT NOT NULL,
    fdc_id BIGINT NOT NULL,

    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    match_method VARCHAR(50) NULL,
    confidence DECIMAL(4,3) NULL,

    CONSTRAINT pk_ingredient_food_map
        PRIMARY KEY (ingredient_id, fdc_id),

    CONSTRAINT chk_ingredient_food_map_confidence
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),

    CONSTRAINT fk_ingredient_food_map_ingredient
        FOREIGN KEY (ingredient_id)
        REFERENCES ingredients(ingredient_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT fk_ingredient_food_map_food
        FOREIGN KEY (fdc_id)
        REFERENCES food_items(fdc_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_ingredient_food_map_fdc
    ON ingredient_food_map(fdc_id);

CREATE INDEX idx_ingredient_food_map_primary
    ON ingredient_food_map(ingredient_id, is_primary);


-- =========================================================
-- 5. SMALL DEMO SEED
-- =========================================================
-- This is intentionally minimal.
-- Real recipe and USDA data will be loaded by import scripts.

INSERT INTO users (username)
VALUES ('demo_user')
ON DUPLICATE KEY UPDATE username = VALUES(username);


-- =========================================================
-- 6. QUICK VALIDATION QUERIES
-- =========================================================

-- Show all created tables:
SHOW TABLES;

-- Confirm table count (expected: 14):
SELECT COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema = DATABASE();

-- Show all foreign keys in this schema:
SELECT
    TABLE_NAME,
    COLUMN_NAME,
    CONSTRAINT_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
  AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY TABLE_NAME, COLUMN_NAME;
