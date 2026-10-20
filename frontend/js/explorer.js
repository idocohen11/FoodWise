import { request } from "./api.js";
import { heading, loading, failure, escapeHTML as esc, icon, format, navigate } from "./ui.js";
import { renderERD } from "./erd.js";

function sqlLines(sql, clauses) {
  return sql.split("\n").map((line, index) => `<span class="sql-line ${clauses.some(clause => line.includes(clause)) ? "active-clause" : ""}"><span class="line-number" aria-hidden="true">${index + 1}</span><span>${esc(line) || " "}</span></span>`).join("");
}

function tableHTML(columns, rows, caption) {
  return `<div class="table-wrap explorer-table"><table><caption class="sr-only">${esc(caption)}</caption>
    <thead><tr>${columns.map(key => `<th scope="col">${esc(key)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(row => `<tr>${columns.map(key => `<td>${row[key] == null ? '<span class="muted">NULL</span>' : esc(typeof row[key] === "object" ? JSON.stringify(row[key]) : row[key])}</td>`).join("")}</tr>`).join("")}</tbody>
  </table></div>`;
}

function showExecution(target, data) {
  if (!data.plan || typeof data.plan.analyze_tree !== "string" || typeof data.plan.estimate_json !== "string"
    || !Array.isArray(data.plan.access_paths) || !data.results
    || !Array.isArray(data.results.rows) || !Array.isArray(data.results.columns)) {
    throw new Error("The server returned an incomplete execution plan.");
  }
  const { plan, results } = data;
  const metrics = plan.root_metrics || {};
  const labels = {
    last_row_ms: ["Root last-row time", " ms"], actual_rows_per_loop: ["Root rows / loop", ""],
    loops: ["Root loops", ""], estimated_rows: ["Root estimated rows", ""],
  };
  target.innerHTML = `<div class="section-heading"><div><p class="eyebrow">MEASURED BY MYSQL</p><h2>Inside the execution.</h2></div><span class="badge ready">${icon("check")} Read-only run complete</span></div>
    <div class="explorer-metrics">${Object.entries(labels).filter(([key]) => typeof metrics[key] === "number").map(([key, [label, unit]]) =>
      `<div><span>${label}</span><strong>${format(metrics[key], unit)}</strong></div>`).join("")}</div>
    <p class="input-hint">Root time is MySQL's reported iterator time, not page load time. Iterator timings include children and are averaged per loop. Do not add them together. Missing metrics are omitted.</p>
    <details open><summary>Actual execution · EXPLAIN ANALYZE</summary><pre class="plan-output">${esc(plan.analyze_tree)}</pre></details>
    ${plan.access_paths.length ? `<details open><summary>Access paths · optimizer estimates</summary>${tableHTML(
      ["table_name", "access_type", "key", "rows_examined_per_scan", "rows_produced_per_join", "filtered"], plan.access_paths, "Estimated access paths from MySQL JSON plan")}
      <p class="input-hint">key = chosen index; NULL means no reported index. filtered is an estimated percentage. Table names may be SQL aliases or materialized CTEs.</p></details>` : ""}
    <details><summary>Full optimizer estimate · EXPLAIN FORMAT=JSON</summary><pre class="plan-output">${esc(plan.estimate_json)}</pre></details>
    <details><summary>Exact SQL and bound values for this run</summary><pre class="plan-output">${esc(data.sql)}</pre>
      <p class="input-hint">Positional binding order: ${data.binding_order ? esc(data.binding_order.join(", ")) : "named placeholders"}.</p>
      <pre class="binding-output">${esc(JSON.stringify(data.parameters, null, 2))}</pre></details>
    <section class="preview-section"><div class="section-heading"><h3>Real result preview</h3><span class="badge neutral">${results.rows.length} rows shown${results.truncated ? ` of ${results.returned_row_count}` : ""}</span></div>
      ${results.rows.length ? tableHTML(results.columns, results.rows, "Actual query result preview")
        : '<p class="inline-empty">The query ran successfully and returned no rows for these parameters.</p>'}
      <p class="input-hint">The preview SELECT executes separately from EXPLAIN ANALYZE, with the same SQL, values, and read-only transaction. Preview cap: ${results.preview_limit} rows.</p>
    </section>`;
}

export async function renderExplorer(root, { signal, params = new URLSearchParams() }) {
  loading(root, "Opening the query explorer…");
  try {
    const catalog = await request("/query-explorer/queries", { signal });
    if (signal.aborted) return;
    if (!Array.isArray(catalog.queries) || catalog.schema?.tables?.length !== 14) {
      throw new Error("The server returned incomplete explorer metadata.");
    }
    const queryKey = params.get("query") || "pantry_match";
    const query = catalog.queries.find(item => item.key === queryKey);
    if (!query) throw new Error("This predefined query is not available. Open Query Explorer from the navigation to reset.");
    let currentStep = 0;
    let runController;
    let generation = 0;
    signal.addEventListener("abort", () => runController?.abort(), { once: true });
    root.innerHTML = heading("FROM INGREDIENTS TO INSIGHT", "Query Explorer.", "Follow the relationships. Read the SQL. See what MySQL actually does.")
      + `<div class="explorer-banner">${icon("chart")}<p><strong>Six questions. One connected database.</strong> Explore predefined SELECT queries. The diagram is a logical walkthrough; the execution plan shows MySQL's physical strategy.</p></div>
      <section class="surface explorer-selector"><label for="query-select">Explore a query</label><select id="query-select">${catalog.queries.map(item => `<option value="${esc(item.key)}" ${item.key === queryKey ? "selected" : ""}>${esc(item.name)}</option>`).join("")}</select>
        <div><h2>${esc(query.name)}</h2><p class="muted">${esc(query.description)}</p></div><span class="badge neutral">${query.tables.length} tables involved</span></section>
      <div class="explorer-workspace">
        <section class="surface explorer-sql-panel"><div class="section-heading"><h2>The SQL</h2><span class="badge ready">Fixed · read-only</span></div>
          <div class="concept-tags">${query.concepts.map(concept => `<span class="badge neutral">${esc(concept)}</span>`).join("")}</div>
          <p class="input-hint">${esc(query.source)}</p><pre class="sql-code" id="explorer-sql" tabindex="0" aria-label="Predefined SQL"></pre>
          ${query.lookup_sql ? `<details class="lookup-details"><summary>demo_user lookup · separate prerequisite</summary><pre class="plan-output">${esc(query.lookup_sql)}</pre><p class="input-hint">Bound username: demo_user. Its resolved ID is used in the main query. This separate lookup is not included in the displayed main-query plan.</p></details>` : ""}
          <form id="explorer-parameters"><h3>Demo parameters</h3><div class="explorer-inputs">${Object.entries(query.parameters).map(([key, field]) =>
            `<label>${esc(field.label)}<input name="${esc(key)}" type="${field.type === "text" ? "text" : "number"}" ${field.type === "integer" ? 'step="1" min="1"' : field.type === "number" ? 'min="0" max="99999999.99" step="any"' : `maxlength="${field.max_length}"`}
              value="${esc(field.default ?? "")}" placeholder="${key === "recipe_id" ? "Choose from real recommendations" : "No filter"}"></label>`).join("") || '<p class="input-hint">This query uses fixed demo parameters. No SQL input is accepted.</p>'}</div>
            <button class="button full-width" id="run-query">${icon("chart")} Run / Explain Query</button>
            <p class="input-hint">Runs on your real MySQL database in a read-only transaction. The USDA query may take longer. Each statement has an 8-second server time limit.</p>
          </form>
        </section>
        <section class="surface explorer-schema-panel"><div class="section-heading"><div><p class="eyebrow">THE RELATIONSHIPS BEHIND THE RESULT</p><h2>A map of FoodWise.</h2></div><span class="badge neutral">14 tables</span></div>
          <div id="explorer-erd"></div>
          <div class="step-panel"><div class="step-heading"><span id="step-counter" class="badge ready"></span><strong id="step-title"></strong></div><p id="step-description" aria-live="polite"></p>
            <div class="step-controls"><button class="button secondary" type="button" id="step-prev">← Previous step</button><button class="button secondary" type="button" id="step-next">Next step ${icon("arrow")}</button><button class="button quiet" type="button" id="step-reset">Reset</button></div>
          </div><ol class="step-outline">${query.steps.map((step, index) => `<li><button type="button" data-step="${index}">${index + 1}. ${esc(step.title)}</button></li>`).join("")}</ol>
        </section>
      </div>
      <section class="surface execution-panel" id="explorer-execution" aria-live="polite"><div class="empty-state"><h2>From the walkthrough to the real plan.</h2><p>Use Next step to explore the logic, then Run / Explain Query to see live results and MySQL's execution plan.</p></div></section>`;
    root.querySelector("#query-select").onchange = event => navigate(`/query-explorer?query=${encodeURIComponent(event.target.value)}`);
    const paintStep = () => {
      const step = query.steps[currentStep];
      root.querySelector("#step-counter").textContent = `Step ${currentStep + 1} / ${query.steps.length}`;
      root.querySelector("#step-title").textContent = step.title;
      root.querySelector("#step-description").textContent = step.description;
      root.querySelector("#explorer-sql").innerHTML = sqlLines(query.sql, step.clauses);
      renderERD(root.querySelector("#explorer-erd"), catalog.schema, query, step);
      root.querySelector("#step-prev").disabled = currentStep === 0;
      root.querySelector("#step-next").disabled = currentStep === query.steps.length - 1;
      root.querySelectorAll("[data-step]").forEach(button => {
        const active = Number(button.dataset.step) === currentStep;
        button.classList.toggle("selected", active);
        if (active) button.setAttribute("aria-current", "step");
        else button.removeAttribute("aria-current");
      });
    };
    root.querySelector("#step-prev").onclick = () => { currentStep = Math.max(0, currentStep - 1); paintStep(); };
    root.querySelector("#step-next").onclick = () => { currentStep = Math.min(query.steps.length - 1, currentStep + 1); paintStep(); };
    root.querySelectorAll("[data-step]").forEach(button => {
      button.onclick = () => { currentStep = Number(button.dataset.step); paintStep(); };
    });
    const execution = root.querySelector("#explorer-execution");
    const runButton = root.querySelector("#run-query");
    const clearExecution = () => {
      ++generation;
      runController?.abort();
      runButton.disabled = false;
      runButton.removeAttribute("aria-busy");
      execution.innerHTML = '<p class="muted">Run / Explain Query to inspect results for the current parameters.</p>';
    };
    root.querySelector("#step-reset").onclick = () => {
      clearExecution();
      root.querySelector("#explorer-parameters").reset();
      currentStep = 0;
      paintStep();
    };
    const run = async () => {
      runController?.abort();
      runController = new AbortController();
      const sequence = ++generation;
      const values = Object.fromEntries([...new FormData(root.querySelector("#explorer-parameters"))]
        .map(([key, value]) => [key, String(value).trim() || null]));
      runButton.disabled = true;
      runButton.setAttribute("aria-busy", "true");
      currentStep = 0;
      paintStep();
      loading(execution, "Executing the predefined SELECT and collecting MySQL's plans…");
      try {
        const data = await request(`/query-explorer/${queryKey}/explain`, {
          method: "POST", body: { parameters: values }, signal: runController.signal, timeoutMs: 45000,
        });
        if (signal.aborted || sequence !== generation) return;
        showExecution(execution, data);
      } catch (error) {
        if (!signal.aborted && sequence === generation) failure(execution, error, run);
      } finally {
        if (!signal.aborted && sequence === generation) {
          runButton.disabled = false;
          runButton.removeAttribute("aria-busy");
        }
      }
    };
    root.querySelector("#explorer-parameters").onsubmit = event => { event.preventDefault(); run(); };
    root.querySelector("#explorer-parameters").oninput = clearExecution;
    paintStep();
  } catch (error) { if (!signal.aborted) failure(root, error, () => renderExplorer(root, { signal, params })); }
}
