import { apiFetch } from "./client";

export function getCurrentMealPlan() {
  return apiFetch("/meal-plans/current");
}

export function ensureCurrentMealPlan() {
  return apiFetch("/meal-plans/current/ensure", { method: "POST" });
}

export function addMealPlanItem(recipeId) {
  return apiFetch("/meal-plans/current/items", {
    method: "POST",
    body: JSON.stringify({ recipe_id: recipeId })
  });
}

export function listMealPlans(limit = 5) {
  return apiFetch(`/meal-plans?limit=${limit}`);
}

export function getMealPlan(id) {
  return apiFetch(`/meal-plans/${id}`);
}

export function updateMealPlan(id, payload) {
  return apiFetch(`/meal-plans/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function removeMealPlanItem(mealPlanId, itemId) {
  return apiFetch(`/meal-plans/${mealPlanId}/items/${itemId}`, { method: "DELETE" });
}

export function completeMealPlan(mealPlanId) {
  return apiFetch(`/meal-plans/${mealPlanId}/complete`, { method: "POST" });
}

export function resumeMealPlan(mealPlanId) {
  return apiFetch(`/meal-plans/${mealPlanId}/resume`, { method: "POST" });
}

export function deleteMealPlan(mealPlanId) {
  return apiFetch(`/meal-plans/${mealPlanId}`, { method: "DELETE" });
}
