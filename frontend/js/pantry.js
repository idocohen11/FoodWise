import * as api from "./api.js";
import { heading, loading, empty, failure, link, icon, escapeHTML, quantity, action, toast, pagination } from "./ui.js";

export async function renderPantry(root, { signal }) {
  root.innerHTML = heading("START WITH WHAT YOU HAVE", "Your pantry.", "A well-kept pantry is the beginning of a good meal.", link("#/recommendations", "What can I cook?"))
    + `<div class="pantry-layout"><section class="surface pantry-content"><div class="section-heading"><h2>On your shelf</h2><span class="badge neutral" id="pantry-total">Loading…</span></div><div id="pantry-list" aria-live="polite"></div></section>
      <aside class="surface add-panel"><span class="shortcut-icon">${icon("plus")}</span><h2>A little restock.</h2><p class="muted">Find an ingredient, then add it to your pantry.</p>
        <form id="ingredient-search"><label for="ingredient-name">Find an ingredient</label><div class="input-button"><input id="ingredient-name" name="name" placeholder="e.g. tomatoes" maxlength="150" required autocomplete="off"><button class="button" aria-label="Search ingredients">${icon("search")}</button></div></form>
        <div id="ingredient-results" aria-live="polite"><p class="input-hint">Search by name to select an ingredient from the collection.</p></div>
        <form id="pantry-add">
          <div id="selected-ingredient" class="selected-ingredient">No ingredient selected</div>
          <div class="form-pair"><label>Quantity <span class="optional">(optional)</span><input name="quantity" type="number" min="0" max="9999999.999" step="0.001" placeholder="e.g. 2"></label><label>Unit <span class="optional">(optional)</span><input name="unit" maxlength="50" placeholder="e.g. pcs, g"></label></div>
          <button class="button full-width" id="save-ingredient" disabled>${icon("plus")} Add to pantry</button>
          <p class="input-hint">Already on your shelf? Saving replaces its quantity and unit. Leave them blank if unknown.</p>
        </form>
      </aside></div>`;
  let pantry = [];
  let selected = null;
  let searchSequence = 0;
  let searching = false;
  const loadPantry = async () => {
    const target = root.querySelector("#pantry-list");
    loading(target, "Checking your shelves…");
    try {
      pantry = await api.all("/pantry", "pantry", signal);
      if (signal.aborted) return;
      root.querySelector("#pantry-total").textContent = `${pantry.length} ingredients`;
      target.innerHTML = pantry.length ? `<ul class="pantry-items">${pantry.map(row =>
        `<li><span class="pantry-item-icon">${icon("leaf")}</span><div class="pantry-item-name"><strong>${escapeHTML(row.ingredient_name)}</strong><small>${row.quantity == null && !row.unit ? "Quantity not specified" : escapeHTML(quantity(row))}</small></div>
          <button class="icon-button remove-pantry" data-id="${row.ingredient_id}" aria-label="Remove ${escapeHTML(row.ingredient_name)} from pantry" title="Remove ingredient">${icon("trash")}</button></li>`).join("")}</ul>`
        : empty("A fresh shelf. A fresh start.", "Search for ingredients using the add form. Your recipe matches will update as you go.");
      target.querySelectorAll(".remove-pantry").forEach(button => {
        button.onclick = () => action(button, async () => {
          const removed = pantry.find(row => row.ingredient_id === Number(button.dataset.id));
          await api.deletePantry(removed.ingredient_id);
          toast(`${removed.ingredient_name} removed from your pantry.`);
          if (!signal.aborted) {
            await loadPantry();
            updateSelection();
          }
        });
      });
    } catch (error) {
      if (!signal.aborted) {
        root.querySelector("#pantry-total").textContent = "Unavailable";
        failure(target, error, loadPantry);
      }
    }
  };
  function updateSelection() {
    const inPantry = selected && pantry.some(row => row.ingredient_id === selected.ingredient_id);
    root.querySelector("#selected-ingredient").textContent = selected
      ? `${selected.ingredient_name} · ID ${selected.ingredient_id}` : "No ingredient selected";
    const save = root.querySelector("#save-ingredient");
    save.disabled = !selected;
    save.innerHTML = `${icon("plus")} ${inPantry ? "Update pantry ingredient" : "Add to pantry"}`;
  }
  const searchIngredients = async (name, offset = 0) => {
    const sequence = ++searchSequence;
    selected = null;
    updateSelection();
    const target = root.querySelector("#ingredient-results");
    loading(target, "Finding ingredients…");
    searching = true;
    try {
      const data = await api.list("/ingredients", "ingredients", { name, limit: 21, offset }, signal);
      if (signal.aborted || sequence !== searchSequence) return;
      const rows = data.rows.slice(0, 20);
      target.innerHTML = rows.length
        ? `<label for="ingredient-choice" class="result-label">Choose an ingredient</label><select id="ingredient-choice" size="5" aria-describedby="ingredient-help"><option value="" disabled selected>Select a result below</option>${rows.map(row => `<option value="${row.ingredient_id}">${escapeHTML(row.ingredient_name)} · #${row.ingredient_id}</option>`).join("")}</select><p id="ingredient-help" class="input-hint">Select a result to enable adding it.</p><div id="ingredient-pages"></div>`
        : '<p class="inline-empty">No matching ingredients. Try a shorter or different name.</p>';
      if (rows.length) {
        target.querySelector("select").onchange = event => {
          selected = rows.find(row => String(row.ingredient_id) === event.target.value) || null;
          updateSelection();
        };
      }
      if (rows.length || offset) {
        if (!target.querySelector("#ingredient-pages")) target.insertAdjacentHTML("beforeend", '<div id="ingredient-pages"></div>');
        pagination(target.querySelector("#ingredient-pages"), { offset, limit: 20, hasNext: data.rows.length > 20 }, next => searchIngredients(name, next));
      }
    } catch (error) { if (!signal.aborted && sequence === searchSequence) failure(target, error, () => searchIngredients(name, offset)); }
    finally { if (sequence === searchSequence) searching = false; }
  };
  root.querySelector("#ingredient-search").onsubmit = event => {
    event.preventDefault();
    const name = root.querySelector("#ingredient-name").value.trim();
    if (name) searchIngredients(name);
  };
  root.querySelector("#ingredient-name").oninput = () => {
    // A new search phrase must not retain a stale selection or an in-flight result.
    ++searchSequence;
    searching = false;
    selected = null;
    updateSelection();
    root.querySelector("#ingredient-results").innerHTML = '<p class="input-hint">Press Search to find matching ingredients.</p>';
  };
  root.querySelector("#pantry-add").onsubmit = event => {
    event.preventDefault();
    if (!selected || searching) return;
    const form = event.currentTarget;
    const item = selected;
    const values = new FormData(form);
    const body = {
      ingredient_id: item.ingredient_id,
      quantity: values.get("quantity") === "" ? null : Number(values.get("quantity")),
      unit: String(values.get("unit")).trim() || null,
    };
    const button = root.querySelector("#save-ingredient");
    action(button, async () => {
      await api.savePantry(body);
      toast(`${item.ingredient_name} saved to your pantry.`);
      if (!signal.aborted) {
        form.reset();
        selected = null;
        await loadPantry();
        updateSelection();
        const choice = root.querySelector("#ingredient-choice");
        if (choice) choice.selectedIndex = 0;
      }
    }).then(() => { if (!signal.aborted) updateSelection(); });
  };
  await loadPantry();
}
