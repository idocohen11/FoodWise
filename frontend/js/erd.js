import { escapeHTML } from "./ui.js";

// Fixed layout, real tables/keys/relationships supplied by backend metadata.
const positions = {
  countries: [20, 20], recipe_categories: [280, 20], recipes: [540, 20], recipe_steps: [800, 20],
  users: [20, 220], favorites: [280, 220], recipe_ingredients: [540, 220], ingredients: [800, 220],
  pantry: [20, 420], ingredient_food_map: [800, 420],
  food_categories: [20, 620], food_items: [280, 620], food_nutrients: [540, 620], nutrients: [800, 620],
};
const W = 230, H = 156;

function curve(source, target) {
  const [sx, sy] = positions[source.split(".")[0]];
  const [tx, ty] = positions[target.split(".")[0]];
  if (sx === tx) {
    const direction = ty > sy ? 1 : -1;
    const x = sx + W / 2, y1 = sy + (direction > 0 ? H : 0), y2 = ty + (direction > 0 ? 0 : H);
    return `M${x},${y1} C${x + 35},${(y1 + y2) / 2} ${x + 35},${(y1 + y2) / 2} ${x},${y2}`;
  }
  const right = tx > sx;
  const x1 = sx + (right ? W : 0), y1 = sy + H / 2;
  const x2 = tx + (right ? 0 : W), y2 = ty + H / 2;
  return `M${x1},${y1} C${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${y2} ${x2},${y2}`;
}

export function renderERD(target, schema, query, activeStep) {
  const allEdges = [...schema.relationships, ...schema.query_joins];
  const used = new Set(query.tables);
  const active = new Set(activeStep.tables);
  const usedEdges = new Set(query.relationships);
  const activeEdges = new Set(activeStep.relationships);
  target.innerHTML = `<div class="erd-scroll" tabindex="0" role="region" aria-label="Interactive FoodWise schema; scroll horizontally on small screens">
    <svg class="erd-svg" viewBox="0 0 1050 800" aria-label="FoodWise ERD, 14 tables" role="group">
      <defs><marker id="erd-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 10 5 0 10" fill="currentColor"/></marker></defs>
      ${allEdges.map(edge => `<path class="erd-edge ${usedEdges.has(edge.id) ? "used" : "unused"} ${activeEdges.has(edge.id) ? "current" : ""} ${edge.kind === "query_join" ? "query-join" : ""}"
        data-edge="${escapeHTML(edge.id)}" d="${curve(edge.source, edge.target)}" marker-end="url(#erd-arrow)"><title>${escapeHTML(edge.source)} → ${escapeHTML(edge.target)} (${edge.kind === "query_join" ? "query equality, not a foreign key" : "foreign key → referenced key"})</title></path>`).join("")}
      ${schema.tables.map(table => {
        const [x, y] = positions[table.name];
        return `<g class="erd-table ${used.has(table.name) ? "used" : "unrelated"} ${active.has(table.name) ? "current" : ""}" data-table="${escapeHTML(table.name)}" transform="translate(${x} ${y})" tabindex="0" role="button" aria-label="Inspect ${escapeHTML(table.name)}">
          <rect width="${W}" height="${H}" rx="10"/><text class="erd-title" x="12" y="27">${escapeHTML(table.name)}</text>
          <line x1="0" y1="42" x2="${W}" y2="42"/>
          ${table.fields.map((field, index) => {
            const pk = table.primary_key.includes(field), fk = table.foreign_keys.includes(field);
            return `<text class="erd-key" x="12" y="${64 + index * 23}">${pk && fk ? "PK/FK" : pk ? "PK" : fk ? "FK" : ""}</text><text class="erd-field" x="58" y="${64 + index * 23}">${escapeHTML(field)}</text>`;
          }).join("")}
        </g>`;
      }).join("")}
    </svg></div>
    <p class="erd-legend"><span>Green: used by query</span><span>Amber: current step</span><span>Solid: FK → referenced key</span><span>Dashed: query join only</span></p>
    <div class="erd-inspector" aria-live="polite">Select a table to inspect its keys and relationships. Non-key fields are a representative subset.</div>`;
  target.querySelectorAll("[data-table]").forEach(node => {
    const inspect = () => {
      const table = schema.tables.find(t => t.name === node.dataset.table);
      const edges = schema.relationships.filter(edge => edge.source.startsWith(`${table.name}.`) || edge.target.startsWith(`${table.name}.`));
      target.querySelector(".erd-inspector").innerHTML = `<strong>${escapeHTML(table.name)}</strong><p>Primary key: ${escapeHTML(table.primary_key.join(" + "))}</p>
        <ul>${edges.map(edge => `<li>${escapeHTML(edge.source)} → ${escapeHTML(edge.target)}</li>`).join("")}</ul>`;
    };
    node.addEventListener("click", inspect);
    node.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); inspect(); }
    });
  });
}
