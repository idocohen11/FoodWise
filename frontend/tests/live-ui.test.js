/**
 * Real-API component checks in a DOM runtime (not a visual browser test).
 * Read checks are default. FOODWISE_TEST_WRITES=1 enables reversible test writes.
 * Added pantry/favorite records are removed in finally blocks; existing records
 * and all recipe/USDA data remain unchanged.
 */
import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { setTimeout as pause } from "node:timers/promises";
import { JSDOM, VirtualConsole } from "jsdom";
import * as api from "../js/api.js";
import { renderHome } from "../js/home.js";
import { renderRecipes, renderRecommendations, renderDetails } from "../js/recipes.js";
import { renderPantry } from "../js/pantry.js";
import { renderFavorites } from "../js/favorites.js";
import { renderAnalytics } from "../js/analytics.js";
import { escapeHTML } from "../js/ui.js";

const base = process.env.FOODWISE_TEST_URL || "http://127.0.0.1:5000";
const realFetch = globalThis.fetch;
const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
let dom, root, controller, errors;
const ctx = params => ({ signal: controller.signal, params: new URLSearchParams(params) });
async function until(check, label) {
  const start = Date.now();
  while (!check()) {
    if (Date.now() - start > 22000) throw new Error(`Timed out: ${label}`);
    await pause(30);
  }
}
function click(node) {
  assert.ok(node, "Expected the control to exist");
  node.click();
}

beforeEach(() => {
  errors = [];
  const console = new VirtualConsole();
  console.on("jsdomError", error => errors.push(error.message));
  console.on("error", error => errors.push(String(error)));
  dom = new JSDOM(html, { url: `${base}/#/home`, virtualConsole: console });
  for (const name of ["window", "document", "location", "FormData", "Event", "DOMException"]) {
    globalThis[name] = dom.window[name];
  }
  globalThis.fetch = (path, options) => realFetch(new URL(path, base), options);
  root = document.querySelector("#main");
  controller = new AbortController();
});
afterEach(() => {
  controller.abort();
  dom.window.close();
  globalThis.fetch = realFetch;
  assert.deepEqual(errors, [], "No DOM-runtime console errors");
});

test("Flask serves the frontend and every imported module", async () => {
  const response = await realFetch(base);
  assert.equal(response.status, 200);
  assert.match(await response.text(), /FoodWise/);
  for (const file of ["api", "app", "ui", "home", "recipes", "pantry", "favorites", "analytics"]) {
    const asset = await realFetch(`${base}/assets/js/${file}.js`);
    assert.equal(asset.status, 200, file);
    assert.match(asset.headers.get("content-type"), /javascript/);
  }
});

test("home reflects real pantry/favorite counts and top match", async () => {
  await renderHome(root, ctx());
  const [pantry, favorites, top] = await Promise.all([
    api.all("/pantry", "pantry"), api.all("/favorites", "favorites"),
    api.list("/recommendations/pantry", "recipes", { limit: 1 }),
  ]);
  assert.equal(root.querySelector("#pantry-count").textContent, String(pantry.length));
  assert.equal(root.querySelector("#favorite-count").textContent, String(favorites.length));
  assert.match(root.querySelector("#connection-status").textContent, /Connected/);
  assert.equal(root.querySelector("#hero-pick h2").textContent, top.rows[0].recipe_name);
});

test("recipe search uses all six filters and maintains backend result order", async () => {
  const source = await api.list("/recipes", "recipes", { max_minutes: 60, max_calories: 700, min_protein: 10, limit: 1 });
  assert.ok(source.rows.length, "Expected a real recipe fitting the demo filters");
  const sample = source.rows[0];
  const filters = {
    name: sample.recipe_name, country: sample.country_code, category: sample.category,
    max_minutes: 60, max_calories: 700, min_protein: 10,
  };
  const expected = await api.list("/recipes", "recipes", { ...filters, limit: 13 });
  await renderRecipes(root, ctx(filters));
  assert.deepEqual([...root.querySelectorAll(".recipe-card h2")].map(el => el.textContent),
    expected.rows.slice(0, 12).map(row => row.recipe_name));
  assert.ok(root.querySelectorAll(".recipe-card").length);
});

test("recipe search has empty state and pagination controls", async () => {
  await renderRecipes(root, ctx({ name: "foodwise-no-such-recipe-56e1950d" }));
  assert.match(root.textContent, /No recipes found/);
  await renderRecipes(root, ctx());
  assert.equal(root.querySelectorAll(".recipe-card").length, 12);
  assert.equal(root.querySelector("[data-prev]").disabled, true);
  assert.equal(root.querySelector("[data-next]").disabled, false);
  click(root.querySelector("[data-next]"));
  assert.match(location.hash, /offset=12/);
  await renderRecipes(root, ctx({ offset: 12 }));
  assert.equal(root.querySelector("[data-prev]").disabled, false);
  const expected = await api.list("/recipes", "recipes", { offset: 12, limit: 1 });
  assert.equal(root.querySelector(".recipe-card h2").textContent, expected.rows[0].recipe_name);
});

test("recommendations show live matches without reordering them", async () => {
  const expected = await api.list("/recommendations/pantry", "recipes", { limit: 13 });
  await renderRecommendations(root, ctx());
  assert.deepEqual([...root.querySelectorAll(".match-card h2")].map(el => el.textContent),
    expected.rows.slice(0, 12).map(row => row.recipe_name));
  assert.equal(root.querySelector("[role=meter]").getAttribute("aria-valuenow"),
    String(expected.rows[0].pantry_match_percent));
  assert.equal(root.querySelectorAll(".match-card").length, 12);
});

test("details show actual ingredients, steps, missing items, and favorite state", async () => {
  const top = (await api.list("/recommendations/pantry", "recipes", { limit: 1 })).rows[0];
  const expected = await api.recipe(top.recipe_id);
  await renderDetails(root, { ...ctx(), recipeId: top.recipe_id });
  assert.equal(root.querySelector("h1").textContent, expected.recipe_name);
  assert.equal(root.querySelectorAll(".ingredient-panel li").length, expected.ingredients.length);
  assert.equal(root.querySelectorAll(".steps-list li").length, expected.steps.length);
  const missing = api.expectRows(await api.request(`/recipes/${top.recipe_id}/missing-ingredients`), "missing_ingredients");
  if (!missing.length) assert.match(root.querySelector("#missing-section").textContent, /You already have everything you need/);
  else assert.equal(root.querySelectorAll("#missing-section li").length, missing.length);
  assert.ok(root.querySelector("#toggle-favorite"));
});

test("pantry loads every page and ingredient lookup uses real IDs", async () => {
  const expected = await api.all("/pantry", "pantry");
  await renderPantry(root, ctx());
  assert.equal(root.querySelectorAll(".pantry-items li").length, expected.length);
  root.querySelector("#ingredient-name").value = "tomato";
  root.querySelector("#ingredient-search").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  await until(() => root.querySelector("#ingredient-choice"), "ingredient search");
  const real = await api.list("/ingredients", "ingredients", { name: "tomato", limit: 21 });
  const select = root.querySelector("#ingredient-choice");
  assert.equal(select.options[1].value, String(real.rows[0].ingredient_id));
  select.value = select.options[1].value;
  select.dispatchEvent(new Event("change"));
  assert.equal(root.querySelector("#save-ingredient").disabled, false);
  root.querySelector("#ingredient-name").dispatchEvent(new Event("input"));
  assert.equal(root.querySelector("#save-ingredient").disabled, true, "Typing invalidates the old selection");
});

test("favorites and analytics show current database values", async () => {
  const favorites = await api.all("/favorites", "favorites");
  await renderFavorites(root, ctx());
  assert.equal(root.querySelectorAll(".recipe-card").length, favorites.length);
  await renderAnalytics(root, ctx());
  const expected = api.expectRows(await api.request("/analytics/preferences"), "preferences");
  assert.equal(root.querySelectorAll("tbody tr").length, expected.length);
  if (expected.length) assert.equal(root.querySelector("tbody th").textContent, expected[0].category || "Uncategorized");
  for (const [index, row] of expected.entries()) {
    assert.equal(root.querySelectorAll(".chart-row strong")[index].firstChild.textContent, String(row.favorite_count));
  }
});

test("bad recipe ID displays an API error with retry", async () => {
  await renderDetails(root, { ...ctx(), recipeId: 9223372036854775000 });
  assert.match(root.textContent, /Recipe not found/);
  assert.ok(root.querySelector("[data-retry]"));
});

test("API helper rejects malformed responses and renders a usable network error", async () => {
  globalThis.fetch = async () => new Response('{"recipes":"invalid","limit":12,"offset":0}', {
    headers: { "Content-Type": "application/json" },
  });
  await assert.rejects(api.list("/recipes", "recipes"), /incomplete data/);
  globalThis.fetch = async () => { throw new TypeError("connection refused"); };
  await renderRecipes(root, ctx());
  assert.match(root.textContent, /Unable to reach FoodWise/);
  assert.ok(root.querySelector("[data-retry]"));
});

test("HTML from database text is escaped", () => {
  assert.equal(escapeHTML('<img onerror="alert(1)">'), "&lt;img onerror=&quot;alert(1)&quot;&gt;");
});

test("favorite interaction updates analytics and restores the original collection", {
  skip: process.env.FOODWISE_TEST_WRITES !== "1",
}, async () => {
  const original = await api.all("/favorites", "favorites");
  const originalIds = original.map(row => row.recipe_id).sort((a, b) => a - b);
  const candidates = await api.list("/recommendations/pantry", "recipes", { limit: 100 });
  const selected = candidates.rows.find(row => !originalIds.includes(row.recipe_id));
  assert.ok(selected);
  try {
    await renderDetails(root, { ...ctx(), recipeId: selected.recipe_id });
    click(root.querySelector("#toggle-favorite"));
    await until(() => root.querySelector("#toggle-favorite")?.getAttribute("aria-pressed") === "true", "favorite saved");
    await renderFavorites(root, ctx());
    assert.equal(root.querySelectorAll(".recipe-card").length, original.length + 1);
    await renderAnalytics(root, ctx());
    const prefs = api.expectRows(await api.request("/analytics/preferences"), "preferences");
    assert.equal(prefs.reduce((sum, row) => sum + row.favorite_count, 0), original.length + 1);
    await renderFavorites(root, ctx());
    click(root.querySelector(`[data-id="${selected.recipe_id}"]`));
    await until(() => root.querySelectorAll(".recipe-card").length === original.length, "favorite removed");
  } finally {
    if ((await api.all("/favorites", "favorites")).some(row => row.recipe_id === selected.recipe_id)) {
      await api.deleteFavorite(selected.recipe_id);
    }
  }
  assert.deepEqual((await api.all("/favorites", "favorites")).map(row => row.recipe_id).sort((a, b) => a - b), originalIds);
});

test("pantry add/remove interaction uses a looked-up ingredient and restores the pantry", {
  skip: process.env.FOODWISE_TEST_WRITES !== "1",
}, async () => {
  const original = await api.all("/pantry", "pantry");
  const originalIds = original.map(row => row.ingredient_id).sort((a, b) => a - b);
  const candidates = await api.list("/ingredients", "ingredients", { name: "tomato", limit: 20 });
  const selected = candidates.rows.find(row => !originalIds.includes(row.ingredient_id));
  assert.ok(selected);
  try {
    await renderPantry(root, ctx());
    root.querySelector("#ingredient-name").value = selected.ingredient_name;
    root.querySelector("#ingredient-search").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await until(() => root.querySelector("#ingredient-choice"), "ingredient lookup");
    const select = root.querySelector("#ingredient-choice");
    select.value = String(selected.ingredient_id);
    select.dispatchEvent(new Event("change"));
    root.querySelector('[name="quantity"]').value = "2";
    root.querySelector('[name="unit"]').value = "pcs";
    root.querySelector("#pantry-add").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await until(() => root.querySelector(`.remove-pantry[data-id="${selected.ingredient_id}"]`), "pantry saved");
    const row = (await api.all("/pantry", "pantry")).find(row => row.ingredient_id === selected.ingredient_id);
    assert.equal(row.quantity, 2);
    assert.equal(row.unit, "pcs");
    click(root.querySelector(`.remove-pantry[data-id="${selected.ingredient_id}"]`));
    await until(() => root.querySelectorAll(".pantry-items li").length === original.length, "pantry removal");
  } finally {
    if ((await api.all("/pantry", "pantry")).some(row => row.ingredient_id === selected.ingredient_id)) {
      await api.deletePantry(selected.ingredient_id);
    }
  }
  assert.deepEqual((await api.all("/pantry", "pantry")).map(row => row.ingredient_id).sort((a, b) => a - b), originalIds);
});

test("router, keyboard-friendly menu, and browser hash navigation", async () => {
  // jsdom has no viewport; visual/responsive layout still requires a browser.
  dom.window.scrollTo = () => {};
  await import("../js/app.js");
  await until(() => root.querySelector("#connection-status")?.textContent === "Connected", "home route");
  click(document.querySelector("#menu-toggle"));
  assert.equal(document.querySelector("#menu-toggle").getAttribute("aria-expanded"), "true");
  document.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Escape" }));
  assert.equal(document.querySelector("#menu-toggle").getAttribute("aria-expanded"), "false");
  location.hash = "/recommendations";
  await until(() => root.querySelectorAll(".match-card").length === 12, "recommendation route");
  assert.equal(document.querySelector('[data-nav="recommendations"]').getAttribute("aria-current"), "page");
  location.hash = "/unknown";
  await until(() => /isn't on the menu/.test(root.textContent), "not-found route");
});
