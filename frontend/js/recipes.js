import * as api from "./api.js";
import { heading, loading, empty, failure, link, icon, escapeHTML, recipeCard, matchCard,
  pagination, navigate, format, quantity, action, toast } from "./ui.js";

const PAGE_SIZE = 12;
const filterFields = [
  ["name", "Recipe name", "text", "What are you craving?"],
  ["country", "Country", "text", "Country name or code"],
  ["category", "Category", "text", "e.g. main, soup"],
  ["max_minutes", "Maximum time · min", "number", "Any time"],
  ["max_calories", "Maximum calories · kcal", "number", "Any calories"],
  ["min_protein", "Minimum protein · g", "number", "Any protein"],
];
function pageOffset(params) {
  const offset = Number(params.get("offset") || 0);
  return Number.isSafeInteger(offset) && offset >= 0 && offset <= 2147483647 ? offset : 0;
}

export async function renderRecipes(root, { signal, params }) {
  root.innerHTML = heading("THE RECIPE COLLECTION", "Find your next favorite.", "A little less searching. A little more cooking.")
    + `<form id="recipe-search" class="filter-panel">
      <div class="filter-grid">${filterFields.map(([name, label, type, placeholder]) =>
        `<label>${label}<input name="${name}" type="${type}" ${type === "number" ? 'min="0" max="99999999.99" step="any"' : `maxlength="${name === "name" ? 200 : 100}"`}
        placeholder="${placeholder}" value="${escapeHTML(params.get(name) || "")}"></label>`).join("")}</div>
      <div class="filter-actions"><span>Nutrition values are per serving.</span><button class="button quiet" type="button" id="clear-filters">Clear filters</button><button class="button" type="submit">${icon("search")} Search recipes</button></div>
    </form><div id="search-results" aria-live="polite"></div><div id="search-pagination"></div>`;
  root.querySelector("#recipe-search").addEventListener("submit", event => {
    event.preventDefault();
    const values = new URLSearchParams();
    for (const [key, value] of new FormData(event.currentTarget)) {
      if (String(value).trim()) values.set(key, String(value).trim());
    }
    navigate(`/recipes${values.size ? `?${values}` : ""}`);
  });
  root.querySelector("#clear-filters").onclick = () => navigate("/recipes");
  const load = async () => {
    const target = root.querySelector("#search-results");
    loading(target, "Searching the recipe collection…");
    try {
      const offset = pageOffset(params);
      const filters = Object.fromEntries(filterFields.map(([key]) => [key, params.get(key)]));
      const data = await api.list("/recipes", "recipes", { ...filters, limit: PAGE_SIZE + 1, offset }, signal);
      if (signal.aborted) return;
      const rows = data.rows.slice(0, PAGE_SIZE);
      target.innerHTML = rows.length
        ? `<div class="results-heading"><h2>Your recipe discoveries</h2><span>Showing ${offset + 1}–${offset + rows.length}</span></div><div class="recipe-grid">${rows.map(row => recipeCard(row)).join("")}</div>`
        : empty("No recipes found", "Try a broader name, a little more time, or fewer filters.", link("#/recipes", "Explore all recipes", "secondary"));
      pagination(root.querySelector("#search-pagination"), { offset, limit: PAGE_SIZE, hasNext: data.rows.length > PAGE_SIZE }, next => {
        const nextParams = new URLSearchParams(params);
        nextParams.set("offset", next);
        navigate(`/recipes?${nextParams}`);
      });
    } catch (error) { if (!signal.aborted) failure(target, error, load); }
  };
  await load();
}

export async function renderRecommendations(root, { signal, params }) {
  root.innerHTML = heading("A LITTLE LESS WASTE, A LOT MORE POSSIBILITY", "What can I cook?", "Good things are already in your kitchen. Here's where to start.", link("#/pantry", "View my pantry", "secondary"))
    + `<div class="info-strip">${icon("leaf")} <p><strong>Made for your pantry.</strong> Recipes are ranked by the ingredients you already have. Matches check ingredient presence, not quantities.</p></div>
       <div id="match-results" aria-live="polite"></div><div id="match-pagination"></div>`;
  const load = async () => {
    const target = root.querySelector("#match-results");
    loading(target, "Matching recipes to your pantry…");
    try {
      const offset = pageOffset(params);
      const data = await api.list("/recommendations/pantry", "recipes", { limit: PAGE_SIZE + 1, offset }, signal);
      if (signal.aborted) return;
      target.innerHTML = data.rows.length
        ? `<div class="results-heading"><h2>${offset ? "More possibilities" : "Your best matches"}</h2><span>Best match first</span></div><div class="match-grid">${data.rows.slice(0, PAGE_SIZE).map(row => matchCard(row)).join("")}</div>`
        : empty("No recipes to match yet", "Recipes with ingredients will appear here when available.", link("#/recipes", "Browse recipes"));
      pagination(root.querySelector("#match-pagination"), { offset, limit: PAGE_SIZE, hasNext: data.rows.length > PAGE_SIZE },
        next => navigate(`/recommendations?offset=${next}`));
    } catch (error) { if (!signal.aborted) failure(target, error, load); }
  };
  await load();
}

export async function renderDetails(root, { signal, recipeId }) {
  loading(root, "Opening your recipe…");
  try {
    const data = await api.recipe(recipeId, signal);
    if (signal.aborted) return;
    document.title = `${data.recipe_name} · FoodWise`;
    root.innerHTML = `<a class="back-link" href="#/recommendations">← Back to pantry matches</a>
      <header class="detail-heading"><div><div class="tag-row"><span class="badge">${escapeHTML(data.category || "Uncategorized")}</span><span>${escapeHTML(data.country || "Country not listed")}</span>${data.difficulty ? `<span>· ${escapeHTML(data.difficulty)}</span>` : ""}</div>
      <h1>${escapeHTML(data.recipe_name)}</h1>${data.native_name && data.native_name !== data.recipe_name ? `<p class="native-name">${escapeHTML(data.native_name)}</p>` : ""}
      <p class="lede">${escapeHTML(data.summary || "")}</p></div><div id="favorite-control" class="favorite-control" aria-live="polite"></div></header>
      <div class="detail-stats">
        ${[["Prep time", data.prep_minutes, " min"], ["Cook time", data.cook_minutes, " min"], ["Calories", data.calories_per_serving, " kcal"], ["Protein", data.protein_g_per_serving, " g"], ["Fat", data.fat_g_per_serving, " g"], ["Carbs", data.carbs_g_per_serving, " g"]].map(([label, value, unit]) => `<div><span>${label}</span><strong>${format(value, unit)}</strong></div>`).join("")}
      </div><p class="nutrition-note">Nutrition per serving${data.base_servings ? ` · Recipe makes ${format(data.base_servings)} servings` : ""}</p>
      <div class="detail-grid"><aside><section class="surface ingredient-panel"><div class="section-heading"><h2>Ingredients</h2><span class="badge neutral">${data.ingredients.length} lines</span></div>
        ${data.ingredients.length ? `<ul class="ingredient-list">${data.ingredients.map(row => `<li><div><strong>${escapeHTML(row.ingredient_name)}</strong>${row.note ? `<small>${escapeHTML(row.note)}</small>` : ""}</div><span>${escapeHTML(quantity(row))}</span></li>`).join("")}</ul>` : `<p class="muted">No ingredients have been listed for this recipe.</p>`}
      </section><section id="missing-section" class="surface missing-panel" aria-live="polite"></section></aside>
      <section class="surface steps-panel"><p class="eyebrow">LET'S MAKE SOMETHING GOOD</p><h2>In the kitchen</h2>
        ${data.steps.length ? `<ol class="steps-list">${data.steps.map(step => `<li><span class="step-number">${step.step_no}</span><div><p>${escapeHTML(step.instruction)}</p>${step.minutes == null ? "" : `<small>${icon("clock")} ${format(step.minutes, " min")}</small>`}</div></li>`).join("")}</ol>` : `<p class="muted">Preparation steps aren't available for this recipe yet.</p>`}
      </section></div>`;
    const loadMissing = async () => {
      const target = root.querySelector("#missing-section");
      loading(target, "Checking your pantry…");
      try {
        const response = await api.request(`/recipes/${recipeId}/missing-ingredients`, { signal });
        const rows = api.expectRows(response, "missing_ingredients");
        if (signal.aborted) return;
        target.innerHTML = `<h2>Missing from your pantry</h2>${rows.length
          ? `<p class="muted">A short shopping list for this recipe.</p><ul class="ingredient-list">${rows.map(row => `<li><strong>${escapeHTML(row.missing_ingredient)}</strong><span>${escapeHTML(quantity(row))}</span></li>`).join("")}${link("#/pantry", "Update my pantry", "secondary")}`
          : `<div class="all-ready">${icon("check")}<p><strong>You already have everything you need.</strong><span>Based on the ingredients in your pantry.</span></p></div>`}`;
      } catch (error) { if (!signal.aborted) failure(target, error, loadMissing); }
    };
    const loadFavorite = async () => {
      const target = root.querySelector("#favorite-control");
      target.innerHTML = '<span class="muted" role="status">Checking favorites…</span>';
      try {
        const favorites = await api.all("/favorites", "favorites", signal);
        if (signal.aborted) return;
        let saved = favorites.some(row => row.recipe_id === data.recipe_id);
        const paint = () => {
          target.innerHTML = `<button class="button ${saved ? "secondary" : ""}" id="toggle-favorite" aria-pressed="${saved}">${icon("heart")} ${saved ? "Remove favorite" : "Add to favorites"}</button>`;
          target.querySelector("button").onclick = event => action(event.currentTarget, async () => {
            if (saved) await api.deleteFavorite(data.recipe_id);
            else await api.saveFavorite(data.recipe_id);
            saved = !saved;
            toast(saved ? "Saved to your favorites." : "Removed from your favorites.");
            if (!signal.aborted) paint();
          });
        };
        paint();
      } catch (error) { if (!signal.aborted) failure(target, error, loadFavorite); }
    };
    await Promise.all([loadMissing(), loadFavorite()]);
  } catch (error) { if (!signal.aborted) failure(root, error, () => renderDetails(root, { signal, recipeId })); }
}
