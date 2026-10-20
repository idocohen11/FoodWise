import * as api from "./api.js";
import { icon, link, matchCard, failure, empty, escapeHTML } from "./ui.js";

export async function renderHome(root, { signal }) {
  root.innerHTML = `
    <section class="hero">
      <div class="hero-copy"><p class="eyebrow"><span class="tiny-dot"></span> GOOD FOOD STARTS WITH WHAT YOU HAVE</p>
        <h1>Your pantry.<br>Your next <em>great meal.</em></h1>
        <p>A little inspiration for the ingredients you already have. Discover recipes, find your favorites, and make more of your kitchen.</p>
        ${link("#/recommendations", "What can I cook with what I have?")}
        <a class="hero-secondary" href="#/recipes">Or explore the recipe collection ${icon("arrow")}</a>
      </div>
      <div class="hero-feature"><div class="feature-label">${icon("leaf")} YOUR KITCHEN, TODAY</div><div id="hero-pick"><div class="loading-state" role="status">Finding your best match…</div></div><p class="hero-footnote">A meal closer to home, with fewer things to buy.</p></div>
    </section>
    <section class="kitchen-stats" aria-label="Your kitchen at a glance">
      <a href="#/pantry"><span class="stat-icon">${icon("pantry")}</span><span><strong id="pantry-count">…</strong><small>ingredients in your pantry</small></span>${icon("arrow")}</a>
      <a href="#/favorites"><span class="stat-icon">${icon("heart")}</span><span><strong id="favorite-count">…</strong><small>recipes saved for later</small></span>${icon("arrow")}</a>
      <div><span class="stat-icon">${icon("check")}</span><span><strong id="connection-status">Checking…</strong><small id="connection-label">Your FoodWise connection</small></span></div>
    </section>
    <section class="section-block"><div class="section-heading"><div><p class="eyebrow">MAKE YOURSELF AT HOME</p><h2>A thoughtful little kitchen companion.</h2></div><p>From “what's in the cupboard?”<br>to “what's for dinner?”</p></div>
      <div class="shortcut-grid">
        ${[
          ["recipes", "search", "Find Recipes", "A world of flavors, filtered to fit your day."],
          ["recommendations", "leaf", "What Can I Cook?", "Your ingredients. Your best recipe matches."],
          ["pantry", "pantry", "My Pantry", "Keep track of what you have on hand."],
          ["favorites", "heart", "Favorites", "Keep the recipes you'll come back to."],
          ["analytics", "chart", "My Preferences", "See the patterns in the food you love."],
        ].map(([path, glyph, title, text]) => `<a href="#/${path}" class="shortcut"><span class="shortcut-icon">${icon(glyph)}</span><h3>${title}</h3><p>${text}</p><span class="shortcut-arrow">${icon("arrow")}</span></a>`).join("")}
      </div>
    </section>`;
  const results = await Promise.allSettled([
    api.list("/recommendations/pantry", "recipes", { limit: 1 }, signal),
    api.all("/pantry", "pantry", signal),
    api.all("/favorites", "favorites", signal),
    api.request("/health", { signal }),
  ]);
  if (signal.aborted) return;
  const [matches, pantry, favorites, health] = results;
  const hero = root.querySelector("#hero-pick");
  if (matches.status === "fulfilled") {
    try {
      hero.innerHTML = matches.value.rows.length ? matchCard(matches.value.rows[0], true)
        : empty("A fresh start", "Add ingredients to your pantry and explore what's possible.", link("#/pantry", "Open pantry"));
    } catch (error) { failure(hero, error, () => renderHome(root, { signal })); }
  } else failure(hero, matches.reason, () => renderHome(root, { signal }));
  for (const [result, selector] of [[pantry, "#pantry-count"], [favorites, "#favorite-count"]]) {
    const target = root.querySelector(selector);
    target.textContent = result.status === "fulfilled" ? result.value.length : "Unavailable";
    if (result.status === "rejected") target.title = result.reason.message;
  }
  const connected = health.status === "fulfilled" && health.value.database === "connected";
  root.querySelector("#connection-status").textContent = connected ? "Connected" : "Unavailable";
  root.querySelector("#connection-label").textContent = connected ? "Fresh from your FoodWise database" : "Open a page to retry your connection";
}
