import * as api from "./api.js";
import { heading, loading, empty, failure, link, format, escapeHTML, icon } from "./ui.js";

export async function renderAnalytics(root, { signal }) {
  root.innerHTML = heading("A TASTE OF YOU", "Your preferences.", "The story your saved recipes tell. Updated every time you change your favorites.", link("#/favorites", "View favorites", "secondary"))
    + '<div id="preferences-results" aria-live="polite"></div>';
  const load = async () => {
    const target = root.querySelector("#preferences-results");
    loading(target, "Finding the patterns in your favorites…");
    try {
      const response = await api.request("/analytics/preferences", { signal });
      const rows = api.expectRows(response, "preferences");
      if (signal.aborted) return;
      if (!rows.length) {
        target.innerHTML = empty("Your taste, still taking shape.", "Save a few recipes to see your favorite categories and their average nutrition.", link("#/recipes", "Discover recipes"));
        return;
      }
      const total = rows.reduce((sum, row) => sum + row.favorite_count, 0);
      const max = Math.max(...rows.map(row => row.favorite_count), 1);
      target.innerHTML = `<div class="analytics-intro"><div><span class="eyebrow">YOUR FAVORITE CATEGORY</span><h2>${escapeHTML(rows[0].category || "Uncategorized")}</h2><p>${rows[0].favorite_count} of your ${total} saved recipes</p></div><span class="analytics-symbol">${icon("chart")}</span><div class="analytics-caption">Every favorite adds<br>a little more flavor<br>to your story.</div></div>
        <section class="surface"><div class="section-heading"><h2>Your recipe repertoire</h2><span class="badge neutral">${rows.length} ${rows.length === 1 ? "category" : "categories"}</span></div>
        <div class="category-chart">${rows.map(row => `<div class="chart-row"><span>${escapeHTML(row.category || "Uncategorized")}</span><div class="bar-track"><span style="width:${100 * row.favorite_count / max}%"></span></div><strong>${row.favorite_count}<small> favorites</small></strong></div>`).join("")}</div></section>
        <section class="section-block"><div class="section-heading"><div><p class="eyebrow">A CLOSER LOOK</p><h2>What's in your favorites?</h2></div><p>Average nutrition per serving.<br>Preparation time includes cooking.</p></div>
          <div class="table-wrap surface"><table><caption class="sr-only">Favorite recipe averages by category</caption><thead><tr><th scope="col">Category</th><th scope="col">Favorites</th><th scope="col">Avg. calories</th><th scope="col">Avg. protein</th><th scope="col">Avg. total time</th></tr></thead><tbody>${rows.map(row => `<tr><th scope="row">${escapeHTML(row.category || "Uncategorized")}</th><td>${row.favorite_count}</td><td>${format(row.avg_calories, " kcal")}</td><td>${format(row.avg_protein_g, " g")}</td><td>${format(row.avg_total_minutes, " min")}</td></tr>`).join("")}</tbody></table></div>
          <p class="nutrition-note">Unknown nutrition is excluded from averages. Unlisted prep or cook times count as zero in the current calculations.</p>
        </section>`;
    } catch (error) { if (!signal.aborted) failure(target, error, load); }
  };
  await load();
}
