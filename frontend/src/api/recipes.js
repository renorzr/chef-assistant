import { apiFetch } from "./client";

export function listRecipes({ page = 1, pageSize = 20 } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return apiFetch(`/recipes?${params.toString()}`);
}

export function getRecipe(id) {
  return apiFetch(`/recipes/${id}`);
}

export async function searchRecipes(query) {
  const payload = await apiFetch("/recipes/search/hybrid", {
    method: "POST",
    body: JSON.stringify({
      query,
      top_k: 20,
      semantic_weight: 0.7
    })
  });

  return (payload.results || []).map((item) => item.recipe);
}

export function updateRecipe(id, payload) {
  return apiFetch(`/recipes/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function deleteRecipe(id) {
  return apiFetch(`/recipes/${id}`, {
    method: "DELETE"
  });
}

export function importRecipeFromText(text) {
  return apiFetch("/recipes/import/from-text", {
    method: "POST",
    body: JSON.stringify({ text })
  });
}

export async function uploadRecipeStepImage(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/media/upload", {
    method: "POST",
    body: formData
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      // ignore parse failure
    }
    throw new Error(detail);
  }

  return response.json();
}
