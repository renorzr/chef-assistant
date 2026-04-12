import { apiFetch } from "./client";

export function listMenus() {
  return apiFetch("/menus");
}

export function getMenu(menuId) {
  return apiFetch(`/menus/${menuId}`);
}

export function createMenuFromText(payload) {
  return apiFetch("/menus/generate-from-text", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateMenu(menuId, payload) {
  return apiFetch(`/menus/${menuId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function addMenuItem(menuId, recipeId) {
  return apiFetch(`/menus/${menuId}/items`, {
    method: "POST",
    body: JSON.stringify({
      recipe_id: recipeId,
      sort_order: 0
    })
  });
}

export function removeMenuItem(menuId, itemId) {
  return apiFetch(`/menus/${menuId}/items/${itemId}`, {
    method: "DELETE"
  });
}

export function updateMenuItem(menuId, itemId, payload) {
  return apiFetch(`/menus/${menuId}/items/${itemId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function createMenuCategory(menuId, payload) {
  return apiFetch(`/menus/${menuId}/categories`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
