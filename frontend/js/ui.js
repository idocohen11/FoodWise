export const escapeHTML = value => String(value ?? "").replace(/[&<>"']/g, char =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
export const format = (value, unit = "") => value == null ? "Not available"
  : `${new Intl.NumberFormat("en", { maximumFractionDigits: 3 }).format(value)}${unit}`;

const paths = {
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  pantry: '<rect x="4" y="6" width="16" height="15" rx="2"/><path d="M8 3h8M4 11h16M9 15h6"/>',
  heart: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',
  chart: '<path d="M5 20V10m7 10V4m7 16v-7M3 21h18"/>',
  leaf: '<path d="M20 3c1 12-4 17-11 14C2 14 5 5 20 3ZM4 21 15 10"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
};
export const icon = name => `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.leaf}</svg>`;
export const link = (href, label, extra = "") => `<a class="button ${extra}" href="${href}">${label}${icon("arrow")}</a>`;

export function heading(kicker, title, description, action = "") {
  return `<header class="page-heading"><div><p class="eyebrow">${escapeHTML(kicker)}</p><h1>${escapeHTML(title)}</h1><p class="lede">${escapeHTML(description)}</p></div>${action}</header>`;
}
export function loading(target, message = "Getting everything ready…") {
  target.innerHTML = `<div class="loading-state" role="status"><span class="loading-dot"></span>${escapeHTML(message)}</div>`;
}
export function empty(title, description, action = "") {
  return `<div class="empty-state"><span class="empty-icon">${icon("leaf")}</span><h2>${escapeHTML(title)}</h2><p>${escapeHTML(description)}</p>${action}</div>`;
}
export function failure(target, error, retry) {
  if (error.name === "AbortError") return;
  target.innerHTML = `<div class="error-state" role="alert"><h2>Something needs a second try</h2><p>${escapeHTML(error.message)}</p><button class="button secondary" data-retry>Try again ${icon("arrow")}</button></div>`;
  target.querySelector("[data-retry]").addEventListener("click", retry);
}
let toastTimer;
export function toast(message, error = false) {
  const target = document.querySelector("#toast");
  clearTimeout(toastTimer);
  target.textContent = message;
  target.classList.toggle("toast-error", error);
  target.hidden = false;
  toastTimer = setTimeout(() => { target.hidden = true; }, 6500);
}
export async function action(button, work) {
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  try { await work(); }
  catch (error) { toast(error.message, true); }
  finally {
    button.disabled = false;
    button.removeAttribute("aria-busy");
  }
}
export const quantity = row => [row.quantity == null ? "" : format(row.quantity), row.unit].filter(Boolean).join(" ") || "As needed";
export function navigate(path) {
  const hash = `#${path}`;
  if (location.hash === hash) document.dispatchEvent(new Event("foodwise:refresh"));
  else location.hash = hash;
}

export function recipeCard(recipe, extra = "") {
  return `<article class="recipe-card">
    <div class="card-top"><span class="badge">${escapeHTML(recipe.category || "Uncategorized")}</span><span class="country">${escapeHTML(recipe.country || "Country not listed")}</span></div>
    <h2><a href="#/recipe/${recipe.recipe_id}">${escapeHTML(recipe.recipe_name)}</a></h2>
    <p class="card-summary">${escapeHTML(recipe.summary || "Explore the ingredients and preparation steps for this recipe.")}</p>
    <div class="recipe-metrics"><span>${icon("clock")} ${recipe.prep_minutes == null && recipe.cook_minutes == null ? "Time not listed" : format(recipe.total_minutes, " min")}</span><span><strong>${format(recipe.calories_per_serving)}</strong> kcal</span><span><strong>${format(recipe.protein_g_per_serving, " g")}</strong> protein</span></div>
    <div class="card-bottom"><a class="text-link" href="#/recipe/${recipe.recipe_id}">View recipe ${icon("arrow")}</a>${extra}</div>
  </article>`;
}

export function matchCard(recipe, compact = false) {
  const percent = recipe.pantry_match_percent;
  if (typeof percent !== "number" || !Number.isFinite(percent) || percent < 0 || percent > 100
      || !["total_ingredients", "ingredients_in_pantry", "missing_ingredients"].every(key => Number.isInteger(recipe[key]) && recipe[key] >= 0)) {
    throw new Error("The server returned incomplete pantry match data.");
  }
  return `<article class="match-card ${compact ? "compact" : ""}">
    <div class="match-card-top"><span class="badge ${percent === 100 ? "ready" : ""}">${percent === 100 ? `${icon("check")} Ready to cook` : `${recipe.missing_ingredients} missing`}</span><span class="match-score">${format(percent)}<small>%</small></span></div>
    <p class="match-label">PANTRY MATCH</p>
    <h2><a href="#/recipe/${recipe.recipe_id}">${escapeHTML(recipe.recipe_name)}</a></h2>
    <div class="match-track" role="meter" aria-label="Pantry match" aria-valuenow="${percent}" aria-valuemin="0" aria-valuemax="100"><span style="width:${percent}%"></span></div>
    <div class="match-counts"><span><strong>${recipe.ingredients_in_pantry}<small> / ${recipe.total_ingredients}</small></strong>ingredients in pantry</span><span><strong>${recipe.missing_ingredients}</strong>to pick up</span></div>
    <a class="text-link" href="#/recipe/${recipe.recipe_id}">Let's make this ${icon("arrow")}</a>
  </article>`;
}

export function pagination(target, { offset, limit, hasNext }, navigate) {
  target.innerHTML = `<div class="pagination"><button class="button secondary" data-prev ${offset === 0 ? "disabled" : ""}>← Previous</button><span>Page ${Math.floor(offset / limit) + 1}</span><button class="button secondary" data-next ${!hasNext ? "disabled" : ""}>Next ${icon("arrow")}</button></div>`;
  target.querySelector("[data-prev]").onclick = () => navigate(Math.max(0, offset - limit));
  target.querySelector("[data-next]").onclick = () => navigate(offset + limit);
}
