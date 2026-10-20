import { renderHome } from "./home.js";
import { renderRecipes, renderRecommendations, renderDetails } from "./recipes.js";
import { renderPantry } from "./pantry.js";
import { renderFavorites } from "./favorites.js";
import { renderAnalytics } from "./analytics.js";
import { empty, link, failure } from "./ui.js";

const root = document.querySelector("#main");
const menu = document.querySelector("#main-nav");
const menuButton = document.querySelector("#menu-toggle");
let activeController;
const pages = {
  home: ["Home", renderHome], recipes: ["Recipes", renderRecipes],
  recommendations: ["What Can I Cook?", renderRecommendations],
  pantry: ["My Pantry", renderPantry], favorites: ["Favorites", renderFavorites],
  analytics: ["My Preferences", renderAnalytics],
};

menuButton.addEventListener("click", () => {
  const expanded = menuButton.getAttribute("aria-expanded") !== "true";
  menuButton.setAttribute("aria-expanded", expanded);
  menu.classList.toggle("is-open", expanded);
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && menu.classList.contains("is-open")) {
    menu.classList.remove("is-open");
    menuButton.setAttribute("aria-expanded", "false");
    menuButton.focus();
  }
});

async function render() {
  activeController?.abort();
  activeController = new AbortController();
  const signal = activeController.signal;
  const route = new URL(location.hash.slice(1) || "/home", location.origin);
  const parts = route.pathname.split("/").filter(Boolean);
  const page = parts[0] || "home";
  const isDetail = page === "recipe" && /^[1-9][0-9]*$/.test(parts[1]) && parts.length === 2;
  document.querySelectorAll("[data-nav]").forEach(item => {
    const current = item.dataset.nav === (isDetail ? "recipes" : page);
    item.classList.toggle("active", current);
    if (current) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
  menu.classList.remove("is-open");
  menuButton.setAttribute("aria-expanded", "false");
  root.classList.toggle("home-page", page === "home");
  document.title = `${isDetail ? "Recipe" : pages[page]?.[0] || "Page not found"} · FoodWise`;
  window.scrollTo({ top: 0, behavior: "instant" });
  root.focus({ preventScroll: true });
  try {
    if (isDetail) await renderDetails(root, { signal, recipeId: parts[1] });
    else if (pages[page] && parts.length <= 1) await pages[page][1](root, { signal, params: route.searchParams });
    else root.innerHTML = empty("This page isn't on the menu.", "Let's get you back to your kitchen.", link("#/home", "Go home"));
  } catch (error) { if (!signal.aborted) failure(root, error, render); }
}

window.addEventListener("hashchange", render);
document.addEventListener("foodwise:refresh", render);
render();
