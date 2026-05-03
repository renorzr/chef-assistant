import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { cancelMealPlan, completeMealPlan, copyMealPlan, deleteMealPlan, getCurrentMealPlan, getMealPlan, getMealPlanIngredients, listMealPlans, removeMealPlanItem, resumeMealPlan, updateMealPlan } from "../api/mealPlans";
import { RecipeCard } from "../components/cards";
import { ErrorBlock, IconButton, LoadingBlock } from "../components/common";
import { ConfirmActionSheet, RecipeActionSheet } from "../components/sheets";

export default function PlanPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("loading");
  const [currentMealPlan, setCurrentMealPlan] = useState(null);
  const [mealPlans, setMealPlans] = useState([]);
  const [view, setView] = useState("detail");
  const [actionItem, setActionItem] = useState(null);
  const [removingItemId, setRemovingItemId] = useState(null);
  const [completing, setCompleting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [resumingId, setResumingId] = useState(null);
  const [copyingId, setCopyingId] = useState(null);
  const [renaming, setRenaming] = useState(false);
  const [ingredientSummaryOpen, setIngredientSummaryOpen] = useState(false);
  const [ingredientSummaryStatus, setIngredientSummaryStatus] = useState("idle");
  const [ingredientSummary, setIngredientSummary] = useState([]);
  const [ingredientSummaryError, setIngredientSummaryError] = useState("");
  const [expandedIngredients, setExpandedIngredients] = useState({});
  const [cancelConfirmOpen, setCancelConfirmOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const listBottomRef = useRef(null);

  const loadMealPlans = async () => {
    setStatus("loading");
    try {
      const [current, recent] = await Promise.all([getCurrentMealPlan(), listMealPlans(5)]);
      setCurrentMealPlan(current);
      setMealPlans(recent);
      setView(current ? "detail" : "list");
      setIngredientSummaryOpen(false);
      setIngredientSummaryStatus("idle");
      setIngredientSummary([]);
      setIngredientSummaryError("");
      setExpandedIngredients({});
      setStatus("success");
    } catch {
      setStatus("error");
    }
  };

  useEffect(() => { loadMealPlans(); }, []);
  useEffect(() => { if (view === "list" && status === "success") listBottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [mealPlans, view, status]);
  useEffect(() => { setIngredientSummaryOpen(false); setIngredientSummaryStatus("idle"); setIngredientSummary([]); setIngredientSummaryError(""); setExpandedIngredients({}); }, [currentMealPlan?.id]);

  const removeFromMealPlan = async (itemId) => {
    if (!currentMealPlan) return;
    setRemovingItemId(itemId);
    try {
      await removeMealPlanItem(currentMealPlan.id, itemId);
      const refreshed = await getMealPlan(currentMealPlan.id);
      setCurrentMealPlan(refreshed);
      setActionItem(null);
    } finally { setRemovingItemId(null); }
  };
  const completeCurrent = async () => { if (!currentMealPlan || completing) return; setCompleting(true); try { await completeMealPlan(currentMealPlan.id); await loadMealPlans(); setView("list"); } finally { setCompleting(false); } };
  const deleteCurrent = async () => { if (!currentMealPlan || deleting) return; setDeleting(true); try { await deleteMealPlan(currentMealPlan.id); await loadMealPlans(); setView("list"); } finally { setDeleting(false); } };
  const cancelCurrent = async () => { if (!currentMealPlan || cancelling) return; setCancelling(true); try { await cancelMealPlan(currentMealPlan.id); await loadMealPlans(); setView("list"); } finally { setCancelling(false); } };
  const resumePlan = async (mealPlanId) => { setResumingId(mealPlanId); try { const resumed = await resumeMealPlan(mealPlanId); setCurrentMealPlan(resumed); await loadMealPlans(); setView("detail"); } finally { setResumingId(null); } };
  const copyPlan = async (mealPlanId) => { setCopyingId(mealPlanId); try { const copied = await copyMealPlan(mealPlanId); setCurrentMealPlan(copied); await loadMealPlans(); setView("detail"); } finally { setCopyingId(null); } };
  const renameCurrent = async () => {
    if (!currentMealPlan || renaming) return;
    const nextName = window.prompt("修改餐单标题", currentMealPlan.name);
    if (nextName === null) return;
    const trimmed = nextName.trim();
    if (!trimmed || trimmed === currentMealPlan.name) return;
    setRenaming(true);
    try {
      const updated = await updateMealPlan(currentMealPlan.id, { name: trimmed });
      setCurrentMealPlan(updated);
      setMealPlans((prev) => prev.map((plan) => (plan.id === updated.id ? { ...plan, name: updated.name } : plan)));
    } finally { setRenaming(false); }
  };
  const loadIngredientSummary = async (mealPlanId) => {
    setIngredientSummaryStatus("loading"); setIngredientSummaryError("");
    try { const result = await getMealPlanIngredients(mealPlanId); setIngredientSummary(result.items || []); setIngredientSummaryStatus("success"); }
    catch (error) { setIngredientSummaryError(error.message || "加载失败"); setIngredientSummaryStatus("error"); }
  };
  const toggleIngredientSummary = async () => {
    if (!currentMealPlan) return;
    if (ingredientSummaryOpen) return setIngredientSummaryOpen(false);
    setIngredientSummaryOpen(true);
    if (ingredientSummaryStatus === "idle") await loadIngredientSummary(currentMealPlan.id);
  };
  const toggleIngredientDetail = (ingredientId) => setExpandedIngredients((prev) => ({ ...prev, [ingredientId]: !prev[ingredientId] }));

  if (status === "loading") return <LoadingBlock />;
  if (status === "error") return <ErrorBlock onRetry={loadMealPlans} />;

  return (
    <div className="p-4">
      {view === "detail" && currentMealPlan ? (
        <div>
          <div className="mb-3 flex items-center justify-between">
            <button onClick={() => setView("list")} className="rounded-xl bg-gray-100 px-3 py-2 text-sm">返回列表</button>
            <div className="text-center"><div className="font-bold">{currentMealPlan.name}</div><div className="text-xs text-gray-500">预计完成：{currentMealPlan.expected_finish_at ? new Date(currentMealPlan.expected_finish_at).toLocaleString() : "未设置"}</div></div>
            <IconButton onClick={renameCurrent} disabled={renaming} title="修改标题">✎</IconButton>
          </div>

          {currentMealPlan.items.length === 0 ? <div className="pb-24 text-sm text-gray-500">当前餐单还没有菜，去菜谱页或菜单页添加。</div> : (
            <div className="pb-24">
              {currentMealPlan.items.map((item) => <RecipeCard key={item.id} recipe={{ name: item.recipe_name, cook_time_minutes: item.recipe_cook_time_minutes || 0, difficulty: item.recipe_difficulty || "unknown", cover_image_url: item.recipe_cover_image_url }} onClick={() => navigate(`/recipes/${item.recipe_id}`)} overlayActions={<IconButton onClick={() => setActionItem(item)} disabled={removingItemId === item.id} title="更多操作">⋮</IconButton>} />)}
              <div className="mt-4 rounded-2xl bg-white p-3 shadow"><button onClick={toggleIngredientSummary} className="w-full rounded-xl bg-gray-100 p-3 text-sm font-medium">{ingredientSummaryOpen ? "收起食材汇总" : "食材汇总"}</button>{ingredientSummaryOpen ? <div className="mt-3 space-y-2">{ingredientSummaryStatus === "loading" ? <div className="text-sm text-gray-500">加载中...</div> : null}{ingredientSummaryStatus === "error" ? <div className="space-y-2"><div className="text-sm text-red-500">{ingredientSummaryError || "加载失败"}</div><button onClick={() => loadIngredientSummary(currentMealPlan.id)} className="rounded-xl bg-gray-100 px-3 py-2 text-sm">重试</button></div> : null}{ingredientSummaryStatus === "success" && ingredientSummary.length === 0 ? <div className="text-sm text-gray-500">当前餐单还没有可汇总的食材。</div> : null}{ingredientSummaryStatus === "success" ? ingredientSummary.map((ingredient) => { const expanded = !!expandedIngredients[ingredient.ingredient_id]; return <div key={ingredient.ingredient_id} className="rounded-xl bg-gray-50 p-3"><button onClick={() => toggleIngredientDetail(ingredient.ingredient_id)} className="flex w-full items-center justify-between gap-3 text-left"><div><div className="font-medium text-gray-900">{ingredient.name}{ingredient.optional ? <span className="ml-2 rounded-full bg-yellow-100 px-2 py-0.5 text-xs text-yellow-700">可选</span> : null}</div><div className="mt-1 text-sm text-gray-500">{ingredient.total_amount && ingredient.total_unit ? `合计 ${ingredient.total_amount}${ingredient.total_unit}` : "查看明细"}{` · ${ingredient.recipe_count}道菜`}</div></div><div className="text-sm text-gray-400">{expanded ? "收起" : "展开"}</div></button>{expanded ? <div className="mt-3 space-y-2 border-t border-gray-200 pt-3">{ingredient.usages.map((usage, index) => { const quantity = [usage.amount, usage.unit].filter(Boolean).join(usage.amount && usage.unit ? "" : ""); return <div key={`${usage.recipe_id}-${index}`} className="flex items-start justify-between gap-3 text-sm"><div className="font-medium text-gray-700">{usage.recipe_name}</div><div className="text-right text-gray-500"><div>{quantity || "未标注用量"}</div>{usage.note ? <div>{usage.note}</div> : null}</div></div>; })}</div> : null}</div>; }) : null}</div> : null}</div>
            </div>
          )}

          <div className="fixed bottom-16 left-1/2 z-10 w-full max-w-sm -translate-x-1/2 border-t bg-white p-4"><div className="flex gap-2"><button onClick={completeCurrent} disabled={completing} className="flex-1 rounded-xl bg-black p-3 text-white disabled:opacity-40">{completing ? "完成中" : "完成餐单"}</button><button onClick={() => setCancelConfirmOpen(true)} disabled={cancelling} className="flex-1 rounded-xl bg-yellow-50 p-3 text-yellow-700 disabled:opacity-40">{cancelling ? "取消中" : "取消餐单"}</button><button onClick={() => setDeleteConfirmOpen(true)} disabled={deleting} className="flex-1 rounded-xl bg-red-50 p-3 text-red-600 disabled:opacity-40">{deleting ? "删除中" : "删除餐单"}</button></div></div>
        </div>
      ) : (
        <div>
          <div className="mb-3 font-bold">最近餐单</div>
          {mealPlans.length === 0 ? <div className="text-sm text-gray-500">还没有餐单。</div> : null}
          <div className="space-y-2">{mealPlans.map((plan) => <div key={plan.id} className="rounded-2xl bg-white p-3 shadow"><div className="font-semibold">{plan.name}</div><div className="mb-2 text-xs text-gray-500">{plan.item_count} 道菜 · {plan.status === "editing" ? "编辑中" : plan.status === "completed" ? "已完成" : "已取消"}</div><div className="flex gap-2"><button onClick={async () => { const detail = await getMealPlan(plan.id); setCurrentMealPlan(detail); setView("detail"); }} className="flex-1 rounded-xl bg-gray-100 p-2 text-sm">查看</button>{plan.status !== "editing" ? <button onClick={() => resumePlan(plan.id)} disabled={resumingId === plan.id} className="flex-1 rounded-xl bg-black p-2 text-sm text-white disabled:opacity-40">{resumingId === plan.id ? "恢复中" : "恢复编辑中"}</button> : null}{plan.status !== "editing" ? <button onClick={() => copyPlan(plan.id)} disabled={copyingId === plan.id} className="flex-1 rounded-xl bg-gray-100 p-2 text-sm disabled:opacity-40">{copyingId === plan.id ? "复制中" : "复制为新餐单"}</button> : null}</div></div>)}<div ref={listBottomRef} /></div>
        </div>
      )}

      <RecipeActionSheet open={!!actionItem} title="菜谱操作" onClose={() => setActionItem(null)} options={[{ label: "移出餐单", tone: "danger", loading: removingItemId === actionItem?.id, loadingLabel: "移出中", onClick: () => removeFromMealPlan(actionItem.id) }]} />

      <ConfirmActionSheet
        open={cancelConfirmOpen}
        title="取消餐单"
        message="确定取消当前餐单吗？之后仍可从最近餐单中恢复。"
        confirmLabel="取消餐单"
        confirmTone="default"
        loading={cancelling}
        onClose={() => setCancelConfirmOpen(false)}
        onConfirm={async () => {
          await cancelCurrent();
          setCancelConfirmOpen(false);
        }}
      />

      <ConfirmActionSheet
        open={deleteConfirmOpen}
        title="删除餐单"
        message="删除后不可恢复，确定删除当前餐单吗？"
        confirmLabel="删除餐单"
        loading={deleting}
        onClose={() => setDeleteConfirmOpen(false)}
        onConfirm={async () => {
          await deleteCurrent();
          setDeleteConfirmOpen(false);
        }}
      />
    </div>
  );
}
