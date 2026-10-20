/** All HTTP access lives here. No client-side database or fixture data. */
export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function request(path, { method = "GET", body, signal, timeoutMs = 20000 } = {}) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  const timeout = setTimeout(abort, timeoutMs);
  try {
    const response = await fetch(`/api${path}`, {
      method, signal: controller.signal, cache: "no-store",
      headers: body === undefined ? { Accept: "application/json" }
        : { Accept: "application/json", "Content-Type": "application/json" },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (response.status === 204 && response.ok) return null;
    let data;
    try { data = await response.json(); }
    catch { throw new ApiError("The server returned an unexpected response. Please try again.", response.status); }
    if (!response.ok) {
      throw new ApiError(typeof data?.error?.message === "string"
        ? data.error.message : "This request could not be completed.", response.status);
    }
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      throw new ApiError("The server returned an unexpected response.");
    }
    return data;
  } catch (error) {
    if (signal?.aborted) throw new DOMException("Page changed", "AbortError");
    if (error instanceof ApiError) throw error;
    throw new ApiError(error.name === "AbortError"
      ? "The request took too long. Please try again."
      : "Unable to reach FoodWise. Check that the Flask server is running, then try again.");
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", abort);
  }
}

const id = value => Number.isSafeInteger(value) && value > 0;
const numeric = value => value === null || (typeof value === "number" && Number.isFinite(value));
const named = row => row && id(row.recipe_id) && typeof row.recipe_name === "string";
const checks = {
  recipes: named,
  favorites: named,
  pantry: row => row && id(row.ingredient_id) && typeof row.ingredient_name === "string" && numeric(row.quantity),
  ingredients: row => row && id(row.ingredient_id) && typeof row.ingredient_name === "string",
  missing_ingredients: row => row && id(row.ingredient_id) && typeof row.missing_ingredient === "string",
  preferences: row => row && (row.category === null || typeof row.category === "string")
    && Number.isInteger(row.favorite_count) && row.favorite_count >= 0
    && ["avg_calories", "avg_protein_g", "avg_total_minutes"].every(key => numeric(row[key])),
};

export function expectRows(data, key) {
  if (!Array.isArray(data[key]) || !data[key].every(checks[key])) {
    throw new ApiError("The server returned incomplete data. Please try again.");
  }
  return data[key];
}

export async function list(path, key, params = {}, signal) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== "" && value != null));
  const data = await request(`${path}?${query}`, { signal });
  const rows = expectRows(data, key);
  if (!Number.isInteger(data.limit) || data.limit < 1 || !Number.isInteger(data.offset) || data.offset < 0) {
    throw new ApiError("The server returned invalid pagination.");
  }
  return { ...data, rows };
}

/** User-owned collections only. Recipe search and recommendations stay paginated. */
export async function all(path, key, signal) {
  const rows = [];
  for (let offset = 0; ; offset += 100) {
    const page = await list(path, key, { limit: 100, offset }, signal);
    rows.push(...page.rows);
    if (page.rows.length < 100) return rows;
    if (offset >= 99900) throw new ApiError("This collection is too large to load. Please try again later.");
  }
}

export async function recipe(recipeId, signal) {
  const data = await request(`/recipes/${encodeURIComponent(recipeId)}`, { signal });
  if (!named(data) || !Array.isArray(data.ingredients) || !Array.isArray(data.steps)
    || !data.ingredients.every(checks.ingredients)
    || !data.steps.every(row => Number.isInteger(row.step_no) && typeof row.instruction === "string")) {
    throw new ApiError("The recipe response is incomplete. Please try again.");
  }
  return data;
}

export const saveFavorite = recipeId => request(`/favorites/${recipeId}`, { method: "POST" });
export const deleteFavorite = recipeId => request(`/favorites/${recipeId}`, { method: "DELETE" });
export const savePantry = body => request("/pantry", { method: "POST", body });
export const deletePantry = ingredientId => request(`/pantry/${ingredientId}`, { method: "DELETE" });
