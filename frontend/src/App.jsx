import React from "react";
import { Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { TabButton } from "./components/common";
import HomePage from "./pages/HomePage";
import { MenusListPage, MenuDetailPage } from "./pages/MenuPages";
import PlanPage from "./pages/PlanPage";
import { RecipesListPage, RecipeDetailPage } from "./pages/RecipePages";

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <div className="mx-auto flex h-screen max-w-sm flex-col bg-gray-50">
      <div className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/recipes" element={<RecipesListPage />} />
          <Route path="/recipes/:id" element={<RecipeDetailPage />} />
          <Route path="/menus" element={<MenusListPage />} />
          <Route path="/menus/:id" element={<MenuDetailPage />} />
          <Route path="/plan" element={<PlanPage />} />
        </Routes>
      </div>

      <div className="flex border-t bg-white">
        <TabButton label="对话" active={location.pathname === "/"} onClick={() => navigate("/")} />
        <TabButton label="菜谱" active={location.pathname.startsWith("/recipes")} onClick={() => navigate("/recipes")} />
        <TabButton label="菜单" active={location.pathname.startsWith("/menus")} onClick={() => navigate("/menus")} />
        <TabButton label="餐单" active={location.pathname === "/plan"} onClick={() => navigate("/plan")} />
      </div>
    </div>
  );
}
