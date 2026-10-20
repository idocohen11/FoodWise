import * as api from "./api.js";
import { heading, loading, empty, failure, link, icon, recipeCard, escapeHTML, action, toast } from "./ui.js";

export async function renderFavorites(root, { signal }) {
  root.innerHTML = heading("THE KEEPERS", "Your favorites.", "Good recipes deserve a place to come back to.", link("#/analytics", "See my preferences", "secondary"))
    + '<div id="favorites-list" aria-live="polite"></div>';
  const load = async () => {
    const target = root.querySelector("#favorites-list");
    loading(target, "Opening your saved recipes…");
    try {
      const rows = await api.all("/favorites", "favorites", signal);
      if (signal.aborted) return;
      target.innerHTML = rows.length
        ? `<div class="results-heading"><h2>Recipes worth remembering</h2><span>${rows.length} saved ${rows.length === 1 ? "recipe" : "recipes"}</span></div><div class="recipe-grid">${rows.map(row => recipeCard(row,
          `<button class="icon-button remove-favorite" data-id="${row.recipe_id}" aria-label="Remove ${escapeHTML(row.recipe_name)} from favorites" title="Remove favorite">${icon("heart")}</button>`)).join("")}</div>`
        : empty("Your next favorite is out there.", "Open any recipe and save it here. Your preferences will grow with your collection.", link("#/recipes", "Find a favorite"));
      target.querySelectorAll(".remove-favorite").forEach(button => {
        button.onclick = () => action(button, async () => {
          await api.deleteFavorite(Number(button.dataset.id));
          toast("Recipe removed from favorites.");
          if (!signal.aborted) await load();
        });
      });
    } catch (error) { if (!signal.aborted) failure(target, error, load); }
  };
  await load();
}
