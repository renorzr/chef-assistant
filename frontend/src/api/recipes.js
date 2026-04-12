import { apiFetch } from "./client";

export function listRecipes() {
  return apiFetch("/recipes");
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
