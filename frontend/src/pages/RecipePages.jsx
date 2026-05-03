import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { addMenuItem, listMenus } from "../api/menus";
import { addMealPlanItem } from "../api/mealPlans";
import { deleteRecipe, getRecipe, importRecipeFromText, listRecipes, searchRecipes, updateRecipe, uploadRecipeStepImage } from "../api/recipes";
import { isNativeApp, openXiachufangImport, subscribeImportResult } from "../appBridge";
import { RecipeCard } from "../components/cards";
import { ErrorBlock, IconButton, ImageOrPlaceholder, LoadingBlock } from "../components/common";
import { ConfirmActionSheet, ExpiredMealPlanSheet, MenuPickerSheet, RecipeActionSheet, RecipeBasicInfoSheet, RecipeCreateSheet, RecipeIngredientsSheet, RecipeStepEditSheet } from "../components/sheets";
import { formatDifficulty, nearestCookTimeOption } from "../utils/recipeDisplay";
import { normalizeXiachufangRecipeUrl } from "../utils/xiachufang";

export function RecipesListPage() {
  const [recipes, setRecipes] = useState([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("loading");
  const [searching, setSearching] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [searchMode, setSearchMode] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [createSheetOpen, setCreateSheetOpen] = useState(false);
  const [importLinkOpen, setImportLinkOpen] = useState(false);
  const [textCreateOpen, setTextCreateOpen] = useState(false);
  const [importUrl, setImportUrl] = useState("");
  const [recipeText, setRecipeText] = useState("");
  const [importError, setImportError] = useState("");
  const [createError, setCreateError] = useState("");
  const [importSubmitting, setImportSubmitting] = useState(false);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [menus, setMenus] = useState([]);
  const [menusStatus, setMenusStatus] = useState("idle");
  const [menuError, setMenuError] = useState("");
  const [activeRecipeId, setActiveRecipeId] = useState(null);
  const [actionSheetOpen, setActionSheetOpen] = useState(false);
  const [savingMenuId, setSavingMenuId] = useState(null);
  const [successRecipeId, setSuccessRecipeId] = useState(null);
  const [mealPlanSaving, setMealPlanSaving] = useState(false);
  const [expiredMealPlanOpen, setExpiredMealPlanOpen] = useState(false);
  const [expiredMealPlanAction, setExpiredMealPlanAction] = useState("");
  const navigate = useNavigate();
  const loadMoreRef = useRef(null);

  const loadRecipesPage = async (targetPage = 1, { append = false } = {}) => {
    if (append) {
      setLoadingMore(true);
    } else {
      setStatus("loading");
      setSearchMode(false);
    }
    try {
      const payload = await listRecipes({ page: targetPage, pageSize: 20 });
      const items = payload.items || [];
      setRecipes((prev) => (append ? [...prev, ...items] : items));
      setPage(payload.page || targetPage);
      setTotalPages(payload.total_pages || 0);
      setStatus("success");
    } catch {
      if (!append) setStatus("error");
    } finally {
      if (append) setLoadingMore(false);
    }
  };

  const loadMenus = () => {
    setMenusStatus("loading");
    setMenuError("");
    listMenus().then((rows) => {
      setMenus(rows);
      setMenusStatus("success");
    }).catch((err) => {
      setMenusStatus("error");
      setMenuError(err.message);
    });
  };

  useEffect(() => { loadRecipesPage(1); }, []);

  useEffect(() => {
    if (searchMode || status !== "success" || loadingMore || page >= totalPages) return undefined;
    const node = loadMoreRef.current;
    if (!node) return undefined;
    const observer = new IntersectionObserver((entries) => {
      const [entry] = entries;
      if (!entry?.isIntersecting) return;
      if (loadingMore || searchMode || page >= totalPages) return;
      loadRecipesPage(page + 1, { append: true });
    }, { rootMargin: "200px 0px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, [loadingMore, page, searchMode, status, totalPages]);

  useEffect(() => {
    const unsubscribe = subscribeImportResult((payload) => {
      if (payload?.status !== "success") {
        if (payload?.status === "failed") {
          setImportSubmitting(false);
          setImportError(payload.message || "导入失败。");
        }
        return;
      }
      const imported = (payload.results || []).filter((item) => item.status === "imported" && item.recipe_id);
      setImportSubmitting(false);
      setImportError("");
      setImportLinkOpen(false);
      setImportUrl("");
      loadRecipesPage(1);
      if (imported[0]?.recipe_id) navigate(`/recipes/${imported[0].recipe_id}`);
    });
    return unsubscribe;
  }, [navigate]);

  const openMenuPicker = (recipeId) => {
    setActiveRecipeId(recipeId);
    setActionSheetOpen(false);
    setSheetOpen(true);
    if (menusStatus === "idle") loadMenus();
  };
  const openActionSheet = (recipeId) => { setActiveRecipeId(recipeId); setActionSheetOpen(true); };
  const addCurrentRecipeToMealPlan = async () => {
    if (!activeRecipeId || mealPlanSaving) return;
    setMealPlanSaving(true);
    try {
      const result = await addMealPlanItem(activeRecipeId, "ask");
      if (result.status === "expired_confirmation_required") {
        setActionSheetOpen(false);
        setExpiredMealPlanOpen(true);
        return;
      }
      setActionSheetOpen(false);
      setSuccessRecipeId(activeRecipeId);
      setTimeout(() => setSuccessRecipeId(null), 900);
    } finally { setMealPlanSaving(false); }
  };
  const resolveExpiredMealPlan = async (mode) => {
    if (!activeRecipeId) return;
    setExpiredMealPlanAction(mode);
    try {
      await addMealPlanItem(activeRecipeId, mode);
      setExpiredMealPlanOpen(false);
      setSuccessRecipeId(activeRecipeId);
      setTimeout(() => setSuccessRecipeId(null), 900);
    } finally { setExpiredMealPlanAction(""); }
  };
  const handlePickMenu = async (menuId) => {
    if (!activeRecipeId) return;
    setSavingMenuId(menuId);
    try {
      await addMenuItem(menuId, activeRecipeId);
      setSheetOpen(false);
      setSuccessRecipeId(activeRecipeId);
      setTimeout(() => setSuccessRecipeId(null), 900);
      if (menusStatus === "success") {
        setMenus((prev) => prev.map((m) => (String(m.id) === String(menuId) ? { ...m, item_count: (m.item_count || 0) + 1 } : m)));
      }
    } catch (err) {
      setMenuError(err.message);
      setMenusStatus("error");
    } finally { setSavingMenuId(null); }
  };
  const runSearch = async () => {
    setSearching(true);
    try {
      if (!query.trim()) {
        await loadRecipesPage(1);
      } else {
        const rows = await searchRecipes(query.trim());
        setRecipes(rows);
        setPage(1);
        setTotalPages(rows.length > 0 ? 1 : 0);
        setSearchMode(true);
      }
    } catch { setStatus("error"); } finally { setSearching(false); }
  };
  const openCreateActions = () => { setCreateError(""); setImportError(""); setCreateSheetOpen(true); };
  const openImportLinkSheet = () => { setCreateSheetOpen(false); setCreateError(""); setImportError(""); setImportLinkOpen(true); };
  const openTextCreateSheet = () => { setCreateSheetOpen(false); setImportError(""); setCreateError(""); setTextCreateOpen(true); };
  const submitImportUrl = async () => {
    const url = importUrl.trim();
    if (!url) return setImportError("请输入下厨房菜谱链接。");
    const normalizedUrl = normalizeXiachufangRecipeUrl(url);
    if (!normalizedUrl) return setImportError("只支持下厨房菜谱详情链接。");
    if (!isNativeApp()) return setImportError("当前不在 App 环境中，无法直接打开导入 WebView。");
    setImportSubmitting(true); setImportError("");
    const launched = openXiachufangImport({ mode: "recipe", url: normalizedUrl });
    if (!launched) { setImportSubmitting(false); setImportError("当前不在 App 环境中，无法直接打开导入 WebView。"); }
  };
  const submitRecipeText = async () => {
    const text = recipeText.trim();
    if (!text) return setCreateError("请输入菜谱文本。");
    setCreateSubmitting(true); setCreateError("");
    try {
      const result = await importRecipeFromText(text);
      setTextCreateOpen(false);
      setRecipeText("");
      await loadRecipesPage(1);
      navigate(`/recipes/${result.recipe.id}`);
    } catch (error) { setCreateError(error.message || "新建失败。"); } finally { setCreateSubmitting(false); }
  };

  if (status === "loading") return <LoadingBlock />;
  if (status === "error") return <ErrorBlock onRetry={() => loadRecipesPage(1)} />;

  return (
    <div className="p-4">
      <div className="mb-3 flex gap-2">
        <input className="flex-1 rounded-xl bg-gray-100 p-2" placeholder="搜索菜谱" value={query} onChange={(e) => setQuery(e.target.value)} enterKeyHint="search" onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) runSearch(); }} />
        <IconButton onClick={openCreateActions} title="新增菜谱">+</IconButton>
      </div>

      {recipes.map((recipe) => <RecipeCard key={recipe.id} recipe={recipe} onClick={() => navigate(`/recipes/${recipe.id}`)} overlayActions={<IconButton onClick={() => openActionSheet(recipe.id)} active={successRecipeId === recipe.id} title="更多操作">{successRecipeId === recipe.id ? "✓" : "⋮"}</IconButton>} />)}
      {searchMode ? null : <div ref={loadMoreRef} className="py-4 text-center text-sm text-gray-500">{loadingMore ? "加载中..." : totalPages === 0 ? "暂无数据" : page >= totalPages ? "已经到底了" : "继续上划加载更多"}</div>}

      <RecipeActionSheet open={actionSheetOpen} title="菜谱操作" onClose={() => setActionSheetOpen(false)} options={[{ label: "加入餐单", loading: mealPlanSaving, loadingLabel: "加入中", onClick: addCurrentRecipeToMealPlan }, { label: "加入菜单", onClick: () => openMenuPicker(activeRecipeId) }]} />
      <RecipeActionSheet open={createSheetOpen} title="新增菜谱" onClose={() => setCreateSheetOpen(false)} options={[{ label: "导入菜谱", onClick: openImportLinkSheet }, { label: "新建菜谱", onClick: openTextCreateSheet }]} />
      <RecipeCreateSheet open={importLinkOpen} title="导入菜谱" placeholder="粘贴下厨房菜谱链接" value={importUrl} onChange={setImportUrl} onClose={() => { setImportLinkOpen(false); setImportSubmitting(false); setImportError(""); }} onSubmit={submitImportUrl} submitting={importSubmitting} submitLabel="开始导入" error={importError} inputProps={{ autoCapitalize: "none", autoCorrect: false }} />
      <RecipeCreateSheet open={textCreateOpen} title="新建菜谱" placeholder="粘贴完整菜谱文本，例如标题、食材、步骤" value={recipeText} onChange={setRecipeText} onClose={() => { setTextCreateOpen(false); setCreateError(""); }} onSubmit={submitRecipeText} submitting={createSubmitting} submitLabel="解析并保存" error={createError} inputProps={{ multiline: true }} />
      <MenuPickerSheet open={sheetOpen} menus={menus} loading={menusStatus === "loading"} error={menusStatus === "error" ? menuError || "加载失败" : ""} onRetry={loadMenus} onClose={() => setSheetOpen(false)} onPick={handlePickMenu} savingMenuId={savingMenuId} />
      <ExpiredMealPlanSheet open={expiredMealPlanOpen} onClose={() => setExpiredMealPlanOpen(false)} onContinue={() => resolveExpiredMealPlan("continue")} onComplete={() => resolveExpiredMealPlan("complete")} onCancelPlan={() => resolveExpiredMealPlan("cancel")} loadingAction={expiredMealPlanAction} />
    </div>
  );
}

export function RecipeDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [recipe, setRecipe] = useState(null);
  const [status, setStatus] = useState("loading");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [menus, setMenus] = useState([]);
  const [menusStatus, setMenusStatus] = useState("idle");
  const [menuError, setMenuError] = useState("");
  const [savingMenuId, setSavingMenuId] = useState(null);
  const [actionSheetOpen, setActionSheetOpen] = useState(false);
  const [mealPlanSaving, setMealPlanSaving] = useState(false);
  const [addedSuccess, setAddedSuccess] = useState(false);
  const [expiredMealPlanOpen, setExpiredMealPlanOpen] = useState(false);
  const [expiredMealPlanAction, setExpiredMealPlanAction] = useState("");
  const [basicInfoOpen, setBasicInfoOpen] = useState(false);
  const [basicInfoValues, setBasicInfoValues] = useState({ name: "", cook_time_minutes: "30", difficulty: "medium" });
  const [coverImageFile, setCoverImageFile] = useState(null);
  const [coverImagePreview, setCoverImagePreview] = useState("");
  const [ingredientsOpen, setIngredientsOpen] = useState(false);
  const [ingredientsExpanded, setIngredientsExpanded] = useState(false);
  const [ingredientDraft, setIngredientDraft] = useState([]);
  const [stepEditorOpen, setStepEditorOpen] = useState(false);
  const [editingStepId, setEditingStepId] = useState(null);
  const [stepInstructionDraft, setStepInstructionDraft] = useState("");
  const [stepImageFile, setStepImageFile] = useState(null);
  const [stepImagePreview, setStepImagePreview] = useState("");
  const [savingRecipe, setSavingRecipe] = useState(false);
  const [editError, setEditError] = useState("");
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deletingRecipe, setDeletingRecipe] = useState(false);

  const reload = () => { setStatus("loading"); getRecipe(id).then((data) => { setRecipe(data); setStatus("success"); }).catch(() => setStatus("error")); };
  useEffect(() => { reload(); }, [id]);
  useEffect(() => {
    if (!recipe) return;
    setBasicInfoValues({ name: recipe.name || "", cook_time_minutes: String(nearestCookTimeOption(recipe.cook_time_minutes || 30)), difficulty: recipe.difficulty || "medium" });
    setIngredientDraft(recipe.ingredients.map((item) => ({ name: item.name || "", amount: item.amount || "", unit: item.unit || "", note: item.note || null, optional: !!item.optional, is_main: !!item.is_main })));
  }, [recipe]);
  useEffect(() => {
    if (!stepImageFile) { setStepImagePreview(""); return undefined; }
    const objectUrl = URL.createObjectURL(stepImageFile); setStepImagePreview(objectUrl); return () => URL.revokeObjectURL(objectUrl);
  }, [stepImageFile]);
  useEffect(() => {
    if (!coverImageFile) { setCoverImagePreview(""); return undefined; }
    const objectUrl = URL.createObjectURL(coverImageFile); setCoverImagePreview(objectUrl); return () => URL.revokeObjectURL(objectUrl);
  }, [coverImageFile]);

  const buildRecipePayload = (overrides = {}) => recipe ? ({ name: recipe.name, description: recipe.description, cook_time_minutes: recipe.cook_time_minutes, difficulty: recipe.difficulty, tags: recipe.tags, source_type: recipe.source_type, source_url: recipe.source_url, cover_image_url: recipe.cover_image_url, main_ingredient: recipe.main_ingredient, dish_type: recipe.dish_type, cooking_method: recipe.cooking_method, ingredients: recipe.ingredients.map((item) => ({ name: item.name, amount: item.amount, unit: item.unit, note: item.note, optional: !!item.optional, is_main: !!item.is_main })), steps: recipe.steps.map((step) => ({ step_order: step.step_order, instruction: step.instruction, image_url: step.image_url })), media: recipe.media.map((media) => ({ media_type: media.media_type, url: media.url })), ...overrides }) : null;
  const saveRecipePayload = async (payload) => { const updated = await updateRecipe(id, payload); setRecipe(updated); return updated; };
  const loadMenus = () => { setMenusStatus("loading"); setMenuError(""); listMenus().then((rows) => { setMenus(rows); setMenusStatus("success"); }).catch((err) => { setMenusStatus("error"); setMenuError(err.message); }); };
  const openMenuPicker = () => { setActionSheetOpen(false); setSheetOpen(true); if (menusStatus === "idle") loadMenus(); };
  const addCurrentRecipeToMealPlan = async () => { if (!recipe || mealPlanSaving) return; setMealPlanSaving(true); try { const result = await addMealPlanItem(recipe.id, "ask"); if (result.status === "expired_confirmation_required") { setActionSheetOpen(false); setExpiredMealPlanOpen(true); return; } setActionSheetOpen(false); setAddedSuccess(true); setTimeout(() => setAddedSuccess(false), 900); } finally { setMealPlanSaving(false); } };
  const resolveExpiredMealPlan = async (mode) => { if (!recipe) return; setExpiredMealPlanAction(mode); try { await addMealPlanItem(recipe.id, mode); setExpiredMealPlanOpen(false); setAddedSuccess(true); setTimeout(() => setAddedSuccess(false), 900); } finally { setExpiredMealPlanAction(""); } };
  const openBasicInfoEditor = () => { if (!recipe) return; setActionSheetOpen(false); setBasicInfoValues({ name: recipe.name || "", cook_time_minutes: String(nearestCookTimeOption(recipe.cook_time_minutes || 30)), difficulty: recipe.difficulty || "medium" }); setCoverImageFile(null); setCoverImagePreview(""); setEditError(""); setBasicInfoOpen(true); };
  const saveBasicInfo = async () => {
    if (!recipe || savingRecipe) return;
    const trimmedName = String(basicInfoValues.name || "").trim();
    const cookTime = Number.parseInt(String(basicInfoValues.cook_time_minutes), 10);
    if (!trimmedName) return setEditError("标题不能为空。");
    if (!Number.isFinite(cookTime) || cookTime <= 0) return setEditError("耗时必须是大于 0 的数字。");
    setSavingRecipe(true); setEditError("");
    try {
      let uploadedCoverImageUrl = recipe.cover_image_url || null;
      if (coverImageFile) uploadedCoverImageUrl = (await uploadRecipeStepImage(coverImageFile)).url;
      await saveRecipePayload(buildRecipePayload({ name: trimmedName, cook_time_minutes: cookTime, difficulty: basicInfoValues.difficulty || "medium", cover_image_url: uploadedCoverImageUrl }));
      setBasicInfoOpen(false);
    } catch (error) { setEditError(error.message || "保存失败。"); } finally { setSavingRecipe(false); }
  };
  const openIngredientsEditor = () => { if (!recipe) return; setActionSheetOpen(false); setIngredientDraft(recipe.ingredients.map((item) => ({ name: item.name || "", amount: item.amount || "", unit: item.unit || "", note: item.note || null, optional: !!item.optional, is_main: !!item.is_main }))); setEditError(""); setIngredientsOpen(true); };
  const saveIngredients = async () => {
    if (!recipe || savingRecipe) return;
    const cleaned = ingredientDraft.map((item) => ({ ...item, name: (item.name || "").trim(), amount: (item.amount || "").trim() || null, unit: (item.unit || "").trim() || null })).filter((item) => item.name);
    if (cleaned.length === 0) return setEditError("至少保留一个食材。");
    setSavingRecipe(true); setEditError("");
    try { await saveRecipePayload(buildRecipePayload({ ingredients: cleaned })); setIngredientsOpen(false); } catch (error) { setEditError(error.message || "保存失败。"); } finally { setSavingRecipe(false); }
  };
  const openStepEditor = (step) => { setEditingStepId(step.id); setStepInstructionDraft(step.instruction || ""); setStepImageFile(null); setStepImagePreview(""); setEditError(""); setStepEditorOpen(true); };
  const closeStepEditor = () => { setStepEditorOpen(false); setEditingStepId(null); setStepInstructionDraft(""); setStepImageFile(null); setStepImagePreview(""); setEditError(""); };
  const saveStepEdit = async () => {
    if (!recipe || !editingStepId || savingRecipe) return;
    const trimmedInstruction = stepInstructionDraft.trim();
    if (!trimmedInstruction) return setEditError("步骤文字不能为空。");
    setSavingRecipe(true); setEditError("");
    try {
      let uploadedImageUrl = null;
      if (stepImageFile) uploadedImageUrl = (await uploadRecipeStepImage(stepImageFile)).url;
      const nextSteps = recipe.steps.map((step) => step.id === editingStepId ? { step_order: step.step_order, instruction: trimmedInstruction, image_url: uploadedImageUrl || step.image_url || null } : { step_order: step.step_order, instruction: step.instruction, image_url: step.image_url });
      await saveRecipePayload(buildRecipePayload({ steps: nextSteps }));
      closeStepEditor();
    } catch (error) { setEditError(error.message || "保存失败。"); } finally { setSavingRecipe(false); }
  };
  const editingStep = recipe?.steps.find((step) => step.id === editingStepId) || null;
  const stepPreviewUrl = stepImagePreview || editingStep?.image_url || "";
  const handlePickMenu = async (menuId) => { setSavingMenuId(menuId); try { await addMenuItem(menuId, recipe.id); setSheetOpen(false); setAddedSuccess(true); setTimeout(() => setAddedSuccess(false), 900); if (menusStatus === "success") setMenus((prev) => prev.map((m) => (String(m.id) === String(menuId) ? { ...m, item_count: (m.item_count || 0) + 1 } : m))); } catch (err) { setMenuError(err.message); setMenusStatus("error"); } finally { setSavingMenuId(null); } };
  const confirmDeleteRecipe = async () => {
    if (!recipe || deletingRecipe) return;
    setDeletingRecipe(true);
    try {
      await deleteRecipe(id);
      navigate("/recipes");
    } finally {
      setDeletingRecipe(false);
    }
  };

  if (status === "loading") return <LoadingBlock />;
  if (status === "error") return <ErrorBlock onRetry={reload} />;

  return (
    <div className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <button onClick={() => navigate(-1)} className="rounded-xl bg-gray-100 px-3 py-2 text-sm">返回</button>
        <div className="flex gap-2"><IconButton onClick={() => setActionSheetOpen(true)} active={addedSuccess} title="更多操作">{addedSuccess ? "✓" : "⋮"}</IconButton></div>
      </div>
      <ImageOrPlaceholder src={recipe.cover_image_url} alt={recipe.name} className="mb-3 h-48 w-full rounded-xl object-cover" placeholderClassName="mb-3 h-48 rounded-xl bg-gray-200" />
      <div className="mb-2 flex items-center justify-between gap-3">
        <h1 className="text-lg font-bold">{recipe.name}</h1>
        <IconButton onClick={openBasicInfoEditor} title="编辑基础信息">✎</IconButton>
      </div>
      <div className="mb-3 text-sm text-gray-500">⏱{recipe.cook_time_minutes}min ⭐{formatDifficulty(recipe.difficulty)}</div>
      <div className="mb-3"><div className="mb-1 font-semibold">食材</div><button onClick={() => setIngredientsExpanded((prev) => !prev)} className="w-full rounded-xl bg-white p-2 text-left"><div className="mb-2 flex items-center justify-between text-xs text-gray-500"><div>共 {recipe.ingredients.length} 项</div><div className="flex items-center gap-2"><div>{ingredientsExpanded ? "收起" : "展开"}</div><div onClick={(e) => { e.stopPropagation(); }}><IconButton onClick={openIngredientsEditor} title="编辑食材">✎</IconButton></div></div></div>{ingredientsExpanded ? <div className="space-y-2">{recipe.ingredients.map((ingredient, index) => { const quantity = [ingredient.amount, ingredient.unit].filter(Boolean).join(""); return <div key={ingredient.id || `${ingredient.name}-${index}`} className="flex items-start justify-between gap-3 border-b border-gray-100 pb-2 last:border-b-0 last:pb-0"><div className="font-medium">{ingredient.name}</div><div className="text-right text-sm text-gray-500">{quantity || "未填写用量"}</div></div>; })}</div> : <div className="text-sm text-gray-700">{recipe.ingredients.map((ingredient) => ingredient.name).join("、")}</div>}</button></div>
      <div><div className="mb-1 font-semibold">步骤</div><div className="space-y-2">{recipe.steps.slice().sort((a, b) => a.step_order - b.step_order).map((step) => <div key={step.id} className="rounded-xl bg-white p-2"><div className="mb-1 flex items-center justify-between text-xs text-gray-500"><div>步骤 {step.step_order}</div><IconButton onClick={() => openStepEditor(step)} title="编辑步骤">✎</IconButton></div><div className="text-sm">{step.instruction}</div>{step.image_url ? <ImageOrPlaceholder src={step.image_url} alt="step" className="mt-2 w-full rounded-lg" placeholderClassName="mt-2 h-32 w-full rounded-lg bg-gray-100" /> : null}</div>)}</div></div>
      <RecipeActionSheet open={actionSheetOpen} title="菜谱操作" onClose={() => setActionSheetOpen(false)} options={[{ label: "加入餐单", icon: "＋", loading: mealPlanSaving, loadingLabel: "加入中", onClick: addCurrentRecipeToMealPlan }, { label: "加入菜单", icon: "≣", onClick: openMenuPicker }, { label: "删除菜谱", icon: "⌫", tone: "danger", onClick: () => { setActionSheetOpen(false); setDeleteConfirmOpen(true); } }]} />
      <MenuPickerSheet open={sheetOpen} menus={menus} loading={menusStatus === "loading"} error={menusStatus === "error" ? menuError || "加载失败" : ""} onRetry={loadMenus} onClose={() => setSheetOpen(false)} onPick={handlePickMenu} savingMenuId={savingMenuId} />
      <ExpiredMealPlanSheet open={expiredMealPlanOpen} onClose={() => setExpiredMealPlanOpen(false)} onContinue={() => resolveExpiredMealPlan("continue")} onComplete={() => resolveExpiredMealPlan("complete")} onCancelPlan={() => resolveExpiredMealPlan("cancel")} loadingAction={expiredMealPlanAction} />
      <RecipeBasicInfoSheet open={basicInfoOpen} values={basicInfoValues} onChange={setBasicInfoValues} onFileChange={setCoverImageFile} previewUrl={coverImagePreview || recipe.cover_image_url || ""} onClose={() => { setBasicInfoOpen(false); setCoverImageFile(null); setCoverImagePreview(""); setEditError(""); }} onSubmit={saveBasicInfo} saving={savingRecipe} error={editError} />
      <RecipeIngredientsSheet open={ingredientsOpen} ingredients={ingredientDraft} onChange={setIngredientDraft} onClose={() => { setIngredientsOpen(false); setEditError(""); }} onSubmit={saveIngredients} saving={savingRecipe} error={editError} />
      <RecipeStepEditSheet open={stepEditorOpen} step={editingStep} instruction={stepInstructionDraft} onInstructionChange={setStepInstructionDraft} onFileChange={setStepImageFile} previewUrl={stepPreviewUrl} onClose={closeStepEditor} onSubmit={saveStepEdit} saving={savingRecipe} error={editError} />

      <ConfirmActionSheet
        open={deleteConfirmOpen}
        title="删除菜谱"
        message="删除后不可恢复，确定删除这道菜谱吗？"
        confirmLabel="删除菜谱"
        loading={deletingRecipe}
        onClose={() => setDeleteConfirmOpen(false)}
        onConfirm={confirmDeleteRecipe}
      />
    </div>
  );
}
