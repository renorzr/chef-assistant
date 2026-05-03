import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { addMenuItem, createMenuCategory, createMenuFromText, getMenu, listMenus, removeMenuItem, updateMenu, updateMenuItem } from "../api/menus";
import { addMealPlanItem } from "../api/mealPlans";
import { LinkCard, RecipeCard } from "../components/cards";
import { ErrorBlock, IconButton, LoadingBlock } from "../components/common";
import { CategoryPickerSheet, ExpiredMealPlanSheet, RecipeActionSheet } from "../components/sheets";

export function MenusListPage() {
  const [menus, setMenus] = useState([]);
  const [name, setName] = useState("");
  const [pref, setPref] = useState("");
  const [status, setStatus] = useState("loading");
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  const reload = () => {
    setStatus("loading");
    listMenus()
      .then((rows) => {
        setMenus(rows);
        setStatus("success");
      })
      .catch(() => setStatus("error"));
  };

  useEffect(() => {
    reload();
  }, []);

  const createFromText = async () => {
    if (!name.trim() || !pref.trim()) return;
    setCreating(true);
    try {
      const result = await createMenuFromText({ name: name.trim(), preference_text: pref.trim() });
      navigate(`/menus/${result.menu.id}`);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="p-4">
      <div className="mb-4 rounded-2xl bg-white p-3 shadow">
        <div className="mb-2 font-semibold">自然语言创建菜单</div>
        <input className="mb-2 w-full rounded-xl bg-gray-100 p-2" placeholder="菜单名" value={name} onChange={(e) => setName(e.target.value)} />
        <textarea className="mb-2 w-full resize-none rounded-xl bg-gray-100 p-2" rows={3} placeholder="例如：清淡快手，最好有汤，来4道菜" value={pref} onChange={(e) => setPref(e.target.value)} />
        <button onClick={createFromText} disabled={creating} className="w-full rounded-xl bg-black p-2 text-white disabled:opacity-40">
          {creating ? "生成中..." : "生成菜单"}
        </button>
      </div>

      <div className="mb-2 font-semibold">已有菜单</div>
      {status === "loading" ? <LoadingBlock /> : null}
      {status === "error" ? <ErrorBlock onRetry={reload} /> : null}
      {status === "success" ? menus.map((m) => <LinkCard key={m.id} title={m.name} subtitle={`${m.item_count} 道菜`} type="菜单" onClick={() => navigate(`/menus/${m.id}`)} />) : null}
    </div>
  );
}

export function MenuDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [menu, setMenu] = useState(null);
  const [status, setStatus] = useState("loading");
  const [removingId, setRemovingId] = useState(null);
  const [actionItem, setActionItem] = useState(null);
  const [categoryItem, setCategoryItem] = useState(null);
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [newCategoryName, setNewCategoryName] = useState("");
  const [categorySaving, setCategorySaving] = useState(false);
  const [categoryError, setCategoryError] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [mealPlanSaving, setMealPlanSaving] = useState(false);
  const [addedMealPlanItemId, setAddedMealPlanItemId] = useState(null);
  const [expiredMealPlanOpen, setExpiredMealPlanOpen] = useState(false);
  const [expiredMealPlanAction, setExpiredMealPlanAction] = useState("");

  const reload = () => {
    setStatus("loading");
    getMenu(id)
      .then((data) => {
        setMenu(data);
        setStatus("success");
      })
      .catch(() => setStatus("error"));
  };

  useEffect(() => {
    reload();
  }, [id]);

  const removeItemFromMenu = async (itemId) => {
    setRemovingId(itemId);
    try {
      await removeMenuItem(id, itemId);
      setMenu((prev) => ({ ...prev, items: prev.items.filter((item) => item.id !== itemId) }));
      setActionItem(null);
    } finally {
      setRemovingId(null);
    }
  };

  const addItemToMealPlan = async (item) => {
    if (!item || mealPlanSaving) return;
    setMealPlanSaving(true);
    try {
      const result = await addMealPlanItem(item.recipe_id, "ask");
      if (result.status === "expired_confirmation_required") {
        setActionItem(item);
        setExpiredMealPlanOpen(true);
        return;
      }
      setActionItem(null);
      setAddedMealPlanItemId(item.id);
      setTimeout(() => setAddedMealPlanItemId(null), 900);
    } finally {
      setMealPlanSaving(false);
    }
  };

  const resolveExpiredMealPlan = async (mode) => {
    if (!actionItem) return;
    setExpiredMealPlanAction(mode);
    try {
      await addMealPlanItem(actionItem.recipe_id, mode);
      setExpiredMealPlanOpen(false);
      setActionItem(null);
      setAddedMealPlanItemId(actionItem.id);
      setTimeout(() => setAddedMealPlanItemId(null), 900);
    } finally {
      setExpiredMealPlanAction("");
    }
  };

  const openCategoryEditor = (item) => {
    setActionItem(null);
    setCategoryItem(item);
    setSelectedCategoryId(item.category_id ? String(item.category_id) : "");
    setNewCategoryName("");
    setCategoryError("");
  };

  const saveCategoryChange = async () => {
    if (!categoryItem) return;
    setCategorySaving(true);
    setCategoryError("");
    try {
      let categoryId = selectedCategoryId ? Number(selectedCategoryId) : null;
      let categoryName = categoryItem.category_name || null;

      const trimmedName = newCategoryName.trim();
      if (trimmedName) {
        const created = await createMenuCategory(id, { name: trimmedName, sort_order: menu.categories.length + 1 });
        categoryId = created.id;
        categoryName = created.name;
        setMenu((prev) => ({ ...prev, categories: [...prev.categories, created] }));
      } else if (categoryId) {
        const matched = menu.categories.find((category) => category.id === categoryId);
        categoryName = matched?.name || null;
      } else {
        categoryName = null;
      }

      await updateMenuItem(id, categoryItem.id, {
        recipe_id: categoryItem.recipe_id,
        category_id: categoryId,
        item_name_override: categoryItem.item_name_override,
        notes: categoryItem.notes,
        sort_order: categoryItem.sort_order
      });

      setMenu((prev) => ({
        ...prev,
        items: prev.items.map((item) => item.id === categoryItem.id ? { ...item, category_id: categoryId, category_name: categoryName } : item)
      }));
      setCategoryItem(null);
    } catch (err) {
      setCategoryError(err.message);
    } finally {
      setCategorySaving(false);
    }
  };

  const renameMenu = async () => {
    if (!menu || renaming) return;
    const nextName = window.prompt("修改菜单标题", menu.name);
    if (nextName === null) return;
    const trimmed = nextName.trim();
    if (!trimmed || trimmed === menu.name) return;

    setRenaming(true);
    try {
      const updated = await updateMenu(id, { name: trimmed, description: menu.description, preference_text: menu.preference_text });
      setMenu(updated);
    } finally {
      setRenaming(false);
    }
  };

  const groupedItems = useMemo(() => {
    if (!menu) return [];
    const categoryOrder = new Map(menu.categories.map((category, index) => [category.name, index]));
    const groups = new Map();
    for (const item of menu.items) {
      const groupName = item.category_name || "未分类";
      if (!groups.has(groupName)) {
        groups.set(groupName, []);
      }
      groups.get(groupName).push(item);
    }
    return Array.from(groups.entries())
      .sort((a, b) => {
        const aName = a[0];
        const bName = b[0];
        const aIsUncategorized = aName === "未分类";
        const bIsUncategorized = bName === "未分类";
        if (aIsUncategorized && !bIsUncategorized) return 1;
        if (!aIsUncategorized && bIsUncategorized) return -1;
        return (categoryOrder.get(aName) ?? 999) - (categoryOrder.get(bName) ?? 999);
      })
      .map(([title, items]) => ({ title, items }));
  }, [menu]);

  const showCategoryHeaders = useMemo(() => {
    if (groupedItems.length !== 1) return true;
    return groupedItems[0]?.title !== "未分类";
  }, [groupedItems]);

  if (status === "loading") return <LoadingBlock />;
  if (status === "error") return <ErrorBlock onRetry={reload} />;

  return (
    <div className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-lg font-bold">{menu.name}</h1>
        <IconButton onClick={renameMenu} disabled={renaming} title="修改标题">✎</IconButton>
      </div>

      {groupedItems.map((group) => (
        <div key={group.title} className="mb-4">
          {showCategoryHeaders ? <div className="mb-2 px-1 text-sm font-semibold text-gray-600">{group.title}</div> : null}
          {group.items.map((item) => (
            <RecipeCard
              key={item.id}
              recipe={{ name: item.item_name_override || item.recipe_name, cook_time_minutes: item.recipe_cook_time_minutes || 0, difficulty: item.recipe_difficulty || "unknown", cover_image_url: item.recipe_cover_image_url }}
              onClick={() => navigate(`/recipes/${item.recipe_id}`)}
              overlayActions={<IconButton onClick={() => setActionItem(item)} active={addedMealPlanItemId === item.id} disabled={removingId === item.id} title="更多操作">{addedMealPlanItemId === item.id ? "✓" : "⋮"}</IconButton>}
            />
          ))}
        </div>
      ))}

      <RecipeActionSheet open={!!actionItem} title="菜谱操作" onClose={() => setActionItem(null)} options={[
        { label: "加入餐单", loading: mealPlanSaving, loadingLabel: "加入中", onClick: () => addItemToMealPlan(actionItem) },
        { label: "修改分类", onClick: () => openCategoryEditor(actionItem) },
        { label: "移出菜单", tone: "danger", loading: removingId === actionItem?.id, loadingLabel: "移出中", onClick: () => removeItemFromMenu(actionItem.id) }
      ]} />

      <CategoryPickerSheet open={!!categoryItem} categories={menu.categories} currentCategoryId={categoryItem?.category_id} currentCategoryName={categoryItem?.category_name} creating={categorySaving} error={categoryError} newCategoryName={newCategoryName} setNewCategoryName={setNewCategoryName} selectedCategoryId={selectedCategoryId} setSelectedCategoryId={setSelectedCategoryId} onClose={() => setCategoryItem(null)} onSubmit={saveCategoryChange} />

      <ExpiredMealPlanSheet open={expiredMealPlanOpen} onClose={() => setExpiredMealPlanOpen(false)} onContinue={() => resolveExpiredMealPlan("continue")} onComplete={() => resolveExpiredMealPlan("complete")} onCancelPlan={() => resolveExpiredMealPlan("cancel")} loadingAction={expiredMealPlanAction} />
    </div>
  );
}
