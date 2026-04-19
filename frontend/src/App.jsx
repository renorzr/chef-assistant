import React, { useEffect, useMemo, useRef, useState } from "react";
import { Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { getChatMessages, sendChatMessage } from "./api/chat";
import { isNativeApp, openXiachufangImport, subscribeImportResult } from "./appBridge";
import { addMenuItem, createMenuCategory, createMenuFromText, getMenu, listMenus, removeMenuItem, updateMenu, updateMenuItem } from "./api/menus";
import { addMealPlanItem, cancelMealPlan, completeMealPlan, copyMealPlan, deleteMealPlan, getCurrentMealPlan, getMealPlan, listMealPlans, removeMealPlanItem, resumeMealPlan, updateMealPlan } from "./api/mealPlans";
import { getRecipe, importRecipeFromText, listRecipes, searchRecipes, updateRecipe } from "./api/recipes";

function isUsableImage(url) {
  if (!url || typeof url !== "string") return false;
  if (url.includes("example.com")) return false;
  return true;
}

function needsProxy(url) {
  if (!url || typeof url !== "string") return false;
  return url.includes("xiachufang.com") || url.includes("chuimg.com");
}

function toDisplayImageUrl(url) {
  if (!isUsableImage(url)) return null;
  if (!needsProxy(url)) return url;
  return `/api/media/proxy?url=${encodeURIComponent(url)}`;
}

function normalizeXiachufangRecipeUrl(url) {
  const match = url.trim().match(/^https?:\/\/(?:www\.)?xiachufang\.com\/recipe\/(\d+)(?:\/|[?#].*)*$/i);
  if (!match) {
    return null;
  }
  return `https://www.xiachufang.com/recipe/${match[1]}/`;
}

function Spinner() {
  return <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-black" />;
}

function LoadingBlock() {
  return (
    <div className="flex items-center justify-center py-12">
      <Spinner />
    </div>
  );
}

function IconButton({ onClick, children, title, active = false, disabled = false, tone = "default" }) {
  const toneClass =
    tone === "danger"
      ? "bg-red-50 text-red-600"
      : active
        ? "bg-black text-white"
        : "bg-gray-100 text-gray-700";

  return (
    <button
      onClick={onClick}
      title={title}
      disabled={disabled}
      className={`flex h-9 w-9 items-center justify-center rounded-full text-lg shadow-sm transition ${toneClass} disabled:opacity-40`}
    >
      {children}
    </button>
  );
}

function BottomSheet({ open, title, onClose, children }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <button className="absolute inset-0 bg-black/30" onClick={onClose} aria-label="关闭弹窗" />
      <div className="relative w-full max-w-sm rounded-t-3xl bg-white p-4 shadow-2xl">
        <div className="mx-auto mb-3 h-1.5 w-12 rounded-full bg-gray-200" />
        <div className="mb-3 flex items-center justify-between">
          <div className="font-semibold">{title}</div>
          <button onClick={onClose} className="rounded-full bg-gray-100 px-2 py-1 text-sm">
            关闭
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function ErrorBlock({ onRetry }) {
  return (
    <div className="py-10 text-center">
      <div className="mb-3 text-sm text-gray-500">加载失败</div>
      <button onClick={onRetry} className="rounded-xl bg-black px-4 py-2 text-sm text-white">
        重试
      </button>
    </div>
  );
}

function ImageOrPlaceholder({ src, alt, className, placeholderClassName }) {
  const [broken, setBroken] = useState(false);
  const displayUrl = toDisplayImageUrl(src);

  if (!displayUrl || broken) {
    return <div className={placeholderClassName} />;
  }

  return <img src={displayUrl} alt={alt} className={className} onError={() => setBroken(true)} />;
}

function TabButton({ label, active, onClick }) {
  return (
    <button onClick={onClick} className={`flex-1 py-2 text-sm ${active ? "border-t-2 border-black font-bold" : "text-gray-500"}`}>
      {label}
    </button>
  );
}

function RecipeCard({ recipe, subtitle, onClick, footer, overlayActions }) {
  return (
    <div className="relative mb-2 rounded-2xl bg-white p-3 shadow">
      <div onClick={onClick} className="cursor-pointer">
        <ImageOrPlaceholder
          src={recipe.cover_image_url}
          alt={recipe.name}
          className="mb-2 h-32 w-full rounded-xl object-cover"
          placeholderClassName="mb-2 h-32 rounded-xl bg-gray-200"
        />
        <div className="font-semibold">{recipe.name}</div>
        <div className="text-xs text-gray-500">{subtitle || `⏱${recipe.cook_time_minutes}min ⭐${recipe.difficulty}`}</div>
      </div>

      {overlayActions ? <div className="absolute bottom-3 right-3 flex gap-2">{overlayActions}</div> : null}

      {footer ? <div className="mt-2">{footer}</div> : null}
    </div>
  );
}

function LinkCard({ title, type, subtitle, onClick }) {
  return (
    <div onClick={onClick} className="mb-2 cursor-pointer rounded-xl bg-gray-100 p-3">
      <div className="text-xs text-gray-500">{type}</div>
      <div className="font-semibold">{title}</div>
      {subtitle ? <div className="mt-1 text-xs text-gray-500">{subtitle}</div> : null}
    </div>
  );
}

function ChatMessage({ role, children }) {
  return (
    <div className={`mb-3 flex ${role === "user" ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[80%] rounded-2xl p-3 ${role === "user" ? "bg-black text-white" : "bg-white"}`}>{children}</div>
    </div>
  );
}

function MenuPickerSheet({ open, menus, loading, error, onRetry, onClose, onPick, savingMenuId }) {
  return (
    <BottomSheet open={open} title="加入菜单" onClose={onClose}>
      {loading ? <LoadingBlock /> : null}
      {error ? <ErrorBlock onRetry={onRetry} /> : null}
      {!loading && !error ? (
        <div className="space-y-2 pb-2">
          {menus.map((menu) => (
            <button
              key={menu.id}
              onClick={() => onPick(menu.id)}
              disabled={savingMenuId === menu.id}
              className="flex w-full items-center justify-between rounded-2xl bg-gray-50 p-3 text-left disabled:opacity-40"
            >
              <div>
                <div className="font-medium">{menu.name}</div>
                <div className="text-xs text-gray-500">{menu.item_count} 道菜</div>
              </div>
              <div className="text-sm text-gray-500">{savingMenuId === menu.id ? "加入中" : "加入"}</div>
            </button>
          ))}
        </div>
      ) : null}
    </BottomSheet>
  );
}

function MenuItemActionSheet({ open, onClose, onEditCategory, onRemove, removing }) {
  return (
    <BottomSheet open={open} title="更多操作" onClose={onClose}>
      <div className="space-y-2 pb-2">
        <button onClick={onEditCategory} className="w-full rounded-2xl bg-gray-50 p-3 text-left">
          修改分类
        </button>
        <button onClick={onRemove} disabled={removing} className="w-full rounded-2xl bg-red-50 p-3 text-left text-red-600 disabled:opacity-40">
          {removing ? "移出中" : "移出菜单"}
        </button>
      </div>
    </BottomSheet>
  );
}

function CategoryPickerSheet({
  open,
  categories,
  currentCategoryId,
  currentCategoryName,
  creating,
  error,
  newCategoryName,
  setNewCategoryName,
  selectedCategoryId,
  setSelectedCategoryId,
  onClose,
  onSubmit
}) {
  return (
    <BottomSheet open={open} title="修改分类" onClose={onClose}>
      <div className="space-y-3 pb-2">
        <div className="text-xs text-gray-500">当前分类：{currentCategoryName || "未分类"}</div>

        <div className="space-y-2">
          <button
            onClick={() => {
              setSelectedCategoryId("");
              setNewCategoryName("");
            }}
            className={`w-full rounded-2xl p-3 text-left ${selectedCategoryId === "" && !newCategoryName.trim() ? "bg-black text-white" : "bg-gray-50"}`}
          >
            不分类
          </button>
          {categories.map((category) => (
            <button
              key={category.id}
              onClick={() => {
                setSelectedCategoryId(String(category.id));
                setNewCategoryName("");
              }}
              className={`w-full rounded-2xl p-3 text-left ${String(category.id) === selectedCategoryId ? "bg-black text-white" : "bg-gray-50"}`}
            >
              {category.name}
            </button>
          ))}
        </div>

        <div>
          <div className="mb-1 text-xs text-gray-500">或者输入新分类名称</div>
          <input
            value={newCategoryName}
            onChange={(e) => {
              setNewCategoryName(e.target.value);
              if (e.target.value.trim()) {
                setSelectedCategoryId("");
              }
            }}
            placeholder="例如：热菜 / 主食 / 甜点"
            className="w-full rounded-xl bg-gray-100 p-2"
          />
        </div>

        {error ? <div className="text-xs text-red-500">{error}</div> : null}

        <button onClick={onSubmit} disabled={creating} className="w-full rounded-xl bg-black p-3 text-white disabled:opacity-40">
          {creating ? "保存中" : "确认"}
        </button>
      </div>
    </BottomSheet>
  );
}

function RecipeActionSheet({ open, title = "操作", options, onClose }) {
  return (
    <BottomSheet open={open} title={title} onClose={onClose}>
      <div className="space-y-2 pb-2">
        {options.map((option) => (
          <button
            key={option.label}
            onClick={option.onClick}
            disabled={option.disabled}
            className={`w-full rounded-2xl p-3 text-left ${option.tone === "danger" ? "bg-red-50 text-red-600" : "bg-gray-50"} disabled:opacity-40`}
          >
            {option.loading ? option.loadingLabel || option.label : option.label}
          </button>
        ))}
      </div>
    </BottomSheet>
  );
}

function ExpiredMealPlanSheet({ open, onClose, onContinue, onComplete, onCancelPlan, loadingAction }) {
  return (
    <BottomSheet open={open} title="当前餐单已过期" onClose={onClose}>
      <div className="space-y-2 pb-2">
        <div className="mb-2 text-sm text-gray-500">这个编辑中的餐单已经超过预计完成时间，请选择如何处理。</div>
        <button onClick={onContinue} disabled={!!loadingAction} className="w-full rounded-2xl bg-gray-50 p-3 text-left disabled:opacity-40">
          {loadingAction === "continue" ? "处理中" : "继续使用这个餐单"}
        </button>
        <button onClick={onComplete} disabled={!!loadingAction} className="w-full rounded-2xl bg-gray-50 p-3 text-left disabled:opacity-40">
          {loadingAction === "complete" ? "处理中" : "完成这个餐单"}
        </button>
        <button onClick={onCancelPlan} disabled={!!loadingAction} className="w-full rounded-2xl bg-red-50 p-3 text-left text-red-600 disabled:opacity-40">
          {loadingAction === "cancel" ? "处理中" : "取消这个餐单"}
        </button>
      </div>
    </BottomSheet>
  );
}

function RecipeCreateSheet({
  open,
  title,
  placeholder,
  value,
  onChange,
  onClose,
  onSubmit,
  submitting,
  submitLabel,
  error,
  inputProps = {}
}) {
  const { multiline, ...restInputProps } = inputProps;

  return (
    <BottomSheet open={open} title={title} onClose={onClose}>
      <div className="space-y-3 pb-2">
        {multiline ? (
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            className="min-h-40 w-full rounded-2xl bg-gray-100 p-3 outline-none"
            {...restInputProps}
          />
        ) : (
          <input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            className="w-full rounded-2xl bg-gray-100 p-3 outline-none"
            {...restInputProps}
          />
        )}

        {error ? <div className="text-sm text-red-500">{error}</div> : null}

        <button onClick={onSubmit} disabled={submitting} className="w-full rounded-2xl bg-black p-3 text-white disabled:opacity-40">
          {submitting ? "处理中" : submitLabel}
        </button>
      </div>
    </BottomSheet>
  );
}

function Home() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(() => window.localStorage.getItem("chef_chat_session_id") || null);
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState("loading");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [menus, setMenus] = useState([]);
  const [menusStatus, setMenusStatus] = useState("idle");
  const [menuError, setMenuError] = useState("");
  const [actionRecipe, setActionRecipe] = useState(null);
  const [menuPickerOpen, setMenuPickerOpen] = useState(false);
  const [savingMenuId, setSavingMenuId] = useState(null);
  const [mealPlanSaving, setMealPlanSaving] = useState(false);
  const [addedMealPlanId, setAddedMealPlanId] = useState(null);
  const [expiredMealPlanOpen, setExpiredMealPlanOpen] = useState(false);
  const [expiredMealPlanAction, setExpiredMealPlanAction] = useState("");
  const navigate = useNavigate();
  const bottomRef = useRef(null);

  const loadMenusForPicker = () => {
    setMenusStatus("loading");
    setMenuError("");
    listMenus()
      .then((rows) => {
        setMenus(rows);
        setMenusStatus("success");
      })
      .catch((err) => {
        setMenusStatus("error");
        setMenuError(err.message);
      });
  };

  const loadRecentMessages = () => {
    setStatus("loading");
    if (!sessionId) {
      listMenus()
        .then((menus) => {
          setMessages([
            {
              role: "assistant",
              content: "这是你常用的菜单，可以直接选择👇",
              cards: menus.slice(0, 3).map((m) => ({ type: "menu", id: String(m.id), title: m.name, subtitle: m.description || "可复用菜单" }))
            }
          ]);
          setStatus("success");
        })
        .catch(() => setStatus("error"));
      return;
    }

    getChatMessages(sessionId, 20)
      .then((data) => {
        if (data.messages.length === 0) {
          return listMenus().then((menus) => {
            setMessages([
              {
                role: "assistant",
                content: "这是你常用的菜单，可以直接选择👇",
                cards: menus.slice(0, 3).map((m) => ({ type: "menu", id: String(m.id), title: m.name, subtitle: m.description || "可复用菜单" }))
              }
            ]);
          });
        }

        setMessages(
          data.messages.map((msg) => ({
            role: msg.role,
            content: msg.content,
            cards: msg.cards || []
          }))
        );
      })
      .then(() => setStatus("success"))
      .catch(() => setStatus("error"));
  };

  useEffect(() => {
    loadRecentMessages();
  }, [sessionId]);

  useEffect(() => {
    const unsubscribe = subscribeImportResult((payload) => {
      if (payload?.status === "success") {
        const imported = payload.results || [];
        const cards = imported
          .filter((item) => item.status === "imported" && item.recipe_id)
          .slice(0, 3)
          .map((item) => ({
            type: "recipe",
            id: String(item.recipe_id),
            title: item.recipe_name,
            subtitle: item.message,
            image_url: item.image_url || null
          }));

        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              imported.length > 1
                ? `已完成批量导入，成功 ${imported.filter((item) => item.status === "imported").length} 条。`
                : imported[0]?.message || "导入完成。",
            cards
          }
        ]);
      } else if (payload?.status === "failed") {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: payload.message || "导入失败。",
            cards: []
          }
        ]);
      }
    });

    return unsubscribe;
  }, []);

  useEffect(() => {
    if (status === "success") {
      bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages, status]);

  const sendMessage = async () => {
    if (!input.trim() || sending) return;
    const text = input.trim();
    setInput("");
    setSending(true);
    setMessages((prev) => [...prev, { role: "user", content: text }]);

    try {
      const reply = await sendChatMessage({
        session_id: sessionId,
        message: text,
        context: { current_page: "/" }
      });
      console.log("[chat-ui] reply received", reply);
      setSessionId(reply.session_id);
      window.localStorage.setItem("chef_chat_session_id", reply.session_id);
      setMessages((prev) => [...prev, { role: "assistant", content: reply.reply_text, cards: reply.cards || [] }]);

      if (reply.action?.type === "import_xiachufang_recipe") {
        console.log("[chat-ui] import recipe action detected", reply.action);
        const launched = openXiachufangImport({ mode: "recipe", url: reply.action.url });
        console.log("[chat-ui] import recipe bridge result", { launched });
        if (!launched) {
          setMessages((prev) => [...prev, { role: "assistant", content: "当前不在 App 环境中，无法直接打开导入 WebView。", cards: [] }]);
        }
      }
      if (reply.action?.type === "import_xiachufang_homepage") {
        console.log("[chat-ui] import homepage action detected", reply.action);
        const launched = openXiachufangImport({ mode: "homepage", url: "https://www.xiachufang.com/" });
        console.log("[chat-ui] import homepage bridge result", { launched });
        if (!launched) {
          setMessages((prev) => [...prev, { role: "assistant", content: "当前不在 App 环境中，无法直接打开导入 WebView。", cards: [] }]);
        }
      }
    } catch (error) {
      setMessages((prev) => [...prev, { role: "assistant", content: `对话请求失败：${error.message}` }]);
    } finally {
      setSending(false);
    }
  };

  const openRecipeActions = (card) => {
    setActionRecipe(card);
    setSheetOpen(true);
  };

  const addCurrentRecipeToMealPlan = async () => {
    if (!actionRecipe || mealPlanSaving) return;
    setMealPlanSaving(true);
    try {
      const result = await addMealPlanItem(Number(actionRecipe.id), "ask");
      if (result.status === "expired_confirmation_required") {
        setSheetOpen(false);
        setExpiredMealPlanOpen(true);
        return;
      }
      setSheetOpen(false);
      setAddedMealPlanId(actionRecipe.id);
      setTimeout(() => setAddedMealPlanId(null), 900);
    } finally {
      setMealPlanSaving(false);
    }
  };

  const resolveExpiredMealPlan = async (mode) => {
    if (!actionRecipe) return;
    setExpiredMealPlanAction(mode);
    try {
      await addMealPlanItem(Number(actionRecipe.id), mode);
      setExpiredMealPlanOpen(false);
      setAddedMealPlanId(actionRecipe.id);
      setTimeout(() => setAddedMealPlanId(null), 900);
    } finally {
      setExpiredMealPlanAction("");
    }
  };

  const openMenuPickerForCurrentRecipe = () => {
    setSheetOpen(false);
    setMenuPickerOpen(true);
    if (menusStatus === "idle") {
      loadMenusForPicker();
    }
  };

  const handlePickMenu = async (menuId) => {
    if (!actionRecipe) return;
    setSavingMenuId(menuId);
    try {
      await addMenuItem(menuId, Number(actionRecipe.id));
      setMenuPickerOpen(false);
    } catch (err) {
      setMenuError(err.message);
      setMenusStatus("error");
    } finally {
      setSavingMenuId(null);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-auto p-4">
        {status === "loading" ? <LoadingBlock /> : null}
        {status === "error" ? <ErrorBlock onRetry={loadRecentMessages} /> : null}
        {status === "success"
          ? messages.map((msg, i) => (
              <ChatMessage key={i} role={msg.role}>
                <div>
                  <div className="mb-2 whitespace-pre-wrap">{msg.content}</div>
                  {msg.cards?.length
                    ? msg.cards.map((card, idx) => {
                        if (card.type === "menu") {
                          return <LinkCard key={idx} title={card.title} subtitle={card.subtitle} type="菜单" onClick={() => navigate(`/menus/${card.id}`)} />;
                        }
                        if (card.type === "recipe") {
                          return (
                            <RecipeCard
                              key={idx}
                              recipe={{
                                name: card.title,
                                cook_time_minutes: 0,
                                difficulty: card.subtitle || "",
                                cover_image_url: card.image_url || null
                              }}
                              subtitle={card.subtitle}
                              onClick={() => navigate(`/recipes/${card.id}`)}
                              overlayActions={
                                <IconButton onClick={() => openRecipeActions(card)} active={addedMealPlanId === card.id} title="更多操作">
                                  {addedMealPlanId === card.id ? "✓" : "⋮"}
                                </IconButton>
                              }
                            />
                          );
                        }
                        if (card.type === "external_link") {
                          return (
                            <LinkCard
                              key={idx}
                              title={card.title}
                              subtitle={card.subtitle}
                              type="验证"
                              onClick={() => window.open(card.id, "_blank")}
                            />
                          );
                        }
                        return <LinkCard key={idx} title={card.title} subtitle={card.subtitle} type="计划" onClick={() => navigate("/plan")} />;
                      })
                    : null}
                </div>
              </ChatMessage>
            ))
          : null}
        <div ref={bottomRef} />
      </div>

      <div className="border-t bg-white p-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入你的需求..."
          className="w-full rounded-xl bg-gray-100 p-2"
          enterKeyHint="send"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.nativeEvent.isComposing) sendMessage();
          }}
        />
      </div>

      <RecipeActionSheet
        open={sheetOpen}
        title="菜谱操作"
        onClose={() => setSheetOpen(false)}
        options={[
          { label: "加入餐单", loading: mealPlanSaving, loadingLabel: "加入中", onClick: addCurrentRecipeToMealPlan },
          { label: "加入菜单", onClick: openMenuPickerForCurrentRecipe }
        ]}
      />

      <MenuPickerSheet
        open={menuPickerOpen}
        menus={menus}
        loading={menusStatus === "loading"}
        error={menusStatus === "error" ? menuError || "加载失败" : ""}
        onRetry={loadMenusForPicker}
        onClose={() => setMenuPickerOpen(false)}
        onPick={handlePickMenu}
        savingMenuId={savingMenuId}
      />

      <ExpiredMealPlanSheet
        open={expiredMealPlanOpen}
        onClose={() => setExpiredMealPlanOpen(false)}
        onContinue={() => resolveExpiredMealPlan("continue")}
        onComplete={() => resolveExpiredMealPlan("complete")}
        onCancelPlan={() => resolveExpiredMealPlan("cancel")}
        loadingAction={expiredMealPlanAction}
      />
    </div>
  );
}

function MenusList() {
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

function MenuDetail() {
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
      setMenu((prev) => ({
        ...prev,
        items: prev.items.filter((item) => item.id !== itemId)
      }));
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
        setMenu((prev) => ({
          ...prev,
          categories: [...prev.categories, created]
        }));
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
        items: prev.items.map((item) =>
          item.id === categoryItem.id
            ? {
                ...item,
                category_id: categoryId,
                category_name: categoryName
              }
            : item
        )
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
      const updated = await updateMenu(id, {
        name: trimmed,
        description: menu.description,
        preference_text: menu.preference_text
      });
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
        <IconButton onClick={renameMenu} disabled={renaming} title="修改标题">
          ✎
        </IconButton>
      </div>

      {groupedItems.map((group) => (
        <div key={group.title} className="mb-4">
          {showCategoryHeaders ? <div className="mb-2 px-1 text-sm font-semibold text-gray-600">{group.title}</div> : null}
          {group.items.map((item) => (
            <RecipeCard
              key={item.id}
              recipe={{
                name: item.item_name_override || item.recipe_name,
                cook_time_minutes: item.recipe_cook_time_minutes || 0,
                difficulty: item.recipe_difficulty || "unknown",
                cover_image_url: item.recipe_cover_image_url
              }}
              onClick={() => navigate(`/recipes/${item.recipe_id}`)}
              overlayActions={
                <IconButton onClick={() => setActionItem(item)} active={addedMealPlanItemId === item.id} disabled={removingId === item.id} title="更多操作">
                  {addedMealPlanItemId === item.id ? "✓" : "⋮"}
                </IconButton>
              }
            />
          ))}
        </div>
      ))}

      <RecipeActionSheet
        open={!!actionItem}
        title="菜谱操作"
        onClose={() => setActionItem(null)}
        options={[
          { label: "加入餐单", loading: mealPlanSaving, loadingLabel: "加入中", onClick: () => addItemToMealPlan(actionItem) },
          { label: "修改分类", onClick: () => openCategoryEditor(actionItem) },
          { label: "移出菜单", tone: "danger", loading: removingId === actionItem?.id, loadingLabel: "移出中", onClick: () => removeItemFromMenu(actionItem.id) }
        ]}
      />

      <CategoryPickerSheet
        open={!!categoryItem}
        categories={menu.categories}
        currentCategoryId={categoryItem?.category_id}
        currentCategoryName={categoryItem?.category_name}
        creating={categorySaving}
        error={categoryError}
        newCategoryName={newCategoryName}
        setNewCategoryName={setNewCategoryName}
        selectedCategoryId={selectedCategoryId}
        setSelectedCategoryId={setSelectedCategoryId}
        onClose={() => setCategoryItem(null)}
        onSubmit={saveCategoryChange}
      />

      <ExpiredMealPlanSheet
        open={expiredMealPlanOpen}
        onClose={() => setExpiredMealPlanOpen(false)}
        onContinue={() => resolveExpiredMealPlan("continue")}
        onComplete={() => resolveExpiredMealPlan("complete")}
        onCancelPlan={() => resolveExpiredMealPlan("cancel")}
        loadingAction={expiredMealPlanAction}
      />
    </div>
  );
}

function RecipesList() {
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
      if (!append) {
        setStatus("error");
      }
    } finally {
      if (append) {
        setLoadingMore(false);
      }
    }
  };

  const loadMenus = () => {
    setMenusStatus("loading");
    setMenuError("");
    listMenus()
      .then((rows) => {
        setMenus(rows);
        setMenusStatus("success");
      })
      .catch((err) => {
        setMenusStatus("error");
        setMenuError(err.message);
      });
  };

  useEffect(() => {
    loadRecipesPage(1);
  }, []);

  useEffect(() => {
    if (searchMode || status !== "success" || loadingMore || page >= totalPages) {
      return undefined;
    }

    const node = loadMoreRef.current;
    if (!node) {
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (!entry?.isIntersecting) {
          return;
        }
        if (loadingMore || searchMode || page >= totalPages) {
          return;
        }
        loadRecipesPage(page + 1, { append: true });
      },
      { rootMargin: "200px 0px" }
    );

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
      if (imported[0]?.recipe_id) {
        navigate(`/recipes/${imported[0].recipe_id}`);
      }
    });

    return unsubscribe;
  }, [navigate]);

  const openMenuPicker = (recipeId) => {
    setActiveRecipeId(recipeId);
    setActionSheetOpen(false);
    setSheetOpen(true);
    if (menusStatus === "idle") {
      loadMenus();
    }
  };

  const openActionSheet = (recipeId) => {
    setActiveRecipeId(recipeId);
    setActionSheetOpen(true);
  };

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
    } finally {
      setMealPlanSaving(false);
    }
  };

  const resolveExpiredMealPlan = async (mode) => {
    if (!activeRecipeId) return;
    setExpiredMealPlanAction(mode);
    try {
      await addMealPlanItem(activeRecipeId, mode);
      setExpiredMealPlanOpen(false);
      setSuccessRecipeId(activeRecipeId);
      setTimeout(() => setSuccessRecipeId(null), 900);
    } finally {
      setExpiredMealPlanAction("");
    }
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
    } finally {
      setSavingMenuId(null);
    }
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
    } catch {
      setStatus("error");
    } finally {
      setSearching(false);
    }
  };

  const openCreateActions = () => {
    setCreateError("");
    setImportError("");
    setCreateSheetOpen(true);
  };

  const openImportLinkSheet = () => {
    setCreateSheetOpen(false);
    setCreateError("");
    setImportError("");
    setImportLinkOpen(true);
  };

  const openTextCreateSheet = () => {
    setCreateSheetOpen(false);
    setImportError("");
    setCreateError("");
    setTextCreateOpen(true);
  };

  const submitImportUrl = async () => {
    const url = importUrl.trim();
    if (!url) {
      setImportError("请输入下厨房菜谱链接。");
      return;
    }
    const normalizedUrl = normalizeXiachufangRecipeUrl(url);
    if (!normalizedUrl) {
      setImportError("只支持下厨房菜谱详情链接。");
      return;
    }
    if (!isNativeApp()) {
      setImportError("当前不在 App 环境中，无法直接打开导入 WebView。");
      return;
    }

    setImportSubmitting(true);
    setImportError("");
    const launched = openXiachufangImport({ mode: "recipe", url: normalizedUrl });
    if (!launched) {
      setImportSubmitting(false);
      setImportError("当前不在 App 环境中，无法直接打开导入 WebView。");
    }
  };

  const submitRecipeText = async () => {
    const text = recipeText.trim();
    if (!text) {
      setCreateError("请输入菜谱文本。");
      return;
    }

    setCreateSubmitting(true);
    setCreateError("");
    try {
      const result = await importRecipeFromText(text);
      setTextCreateOpen(false);
      setRecipeText("");
      await loadRecipesPage(1);
      navigate(`/recipes/${result.recipe.id}`);
    } catch (error) {
      setCreateError(error.message || "新建失败。");
    } finally {
      setCreateSubmitting(false);
    }
  };

  if (status === "loading") return <LoadingBlock />;
  if (status === "error") return <ErrorBlock onRetry={() => loadRecipesPage(1)} />;

  return (
    <div className="p-4">
      <div className="mb-3 flex gap-2">
        <input
          className="flex-1 rounded-xl bg-gray-100 p-2"
          placeholder="搜索菜谱"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          enterKeyHint="search"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.nativeEvent.isComposing) runSearch();
          }}
        />
        <IconButton onClick={openCreateActions} title="新增菜谱">
          +
        </IconButton>
      </div>

      {recipes.map((recipe) => (
        <RecipeCard
          key={recipe.id}
          recipe={recipe}
          onClick={() => navigate(`/recipes/${recipe.id}`)}
          overlayActions={
            <IconButton onClick={() => openActionSheet(recipe.id)} active={successRecipeId === recipe.id} title="更多操作">
              {successRecipeId === recipe.id ? "✓" : "⋮"}
            </IconButton>
          }
        />
      ))}

      {searchMode ? null : (
        <div ref={loadMoreRef} className="py-4 text-center text-sm text-gray-500">
          {loadingMore ? "加载中..." : totalPages === 0 ? "暂无数据" : page >= totalPages ? "已经到底了" : "继续上划加载更多"}
        </div>
      )}

      <RecipeActionSheet
        open={actionSheetOpen}
        title="菜谱操作"
        onClose={() => setActionSheetOpen(false)}
        options={[
          { label: "加入餐单", loading: mealPlanSaving, loadingLabel: "加入中", onClick: addCurrentRecipeToMealPlan },
          { label: "加入菜单", onClick: () => openMenuPicker(activeRecipeId) }
        ]}
      />

      <RecipeActionSheet
        open={createSheetOpen}
        title="新增菜谱"
        onClose={() => setCreateSheetOpen(false)}
        options={[
          { label: "导入菜谱", onClick: openImportLinkSheet },
          { label: "新建菜谱", onClick: openTextCreateSheet }
        ]}
      />

      <RecipeCreateSheet
        open={importLinkOpen}
        title="导入菜谱"
        placeholder="粘贴下厨房菜谱链接"
        value={importUrl}
        onChange={setImportUrl}
        onClose={() => {
          setImportLinkOpen(false);
          setImportSubmitting(false);
          setImportError("");
        }}
        onSubmit={submitImportUrl}
        submitting={importSubmitting}
        submitLabel="开始导入"
        error={importError}
        inputProps={{ autoCapitalize: "none", autoCorrect: false }}
      />

      <RecipeCreateSheet
        open={textCreateOpen}
        title="新建菜谱"
        placeholder="粘贴完整菜谱文本，例如标题、食材、步骤"
        value={recipeText}
        onChange={setRecipeText}
        onClose={() => {
          setTextCreateOpen(false);
          setCreateError("");
        }}
        onSubmit={submitRecipeText}
        submitting={createSubmitting}
        submitLabel="解析并保存"
        error={createError}
        inputProps={{ multiline: true }}
      />

      <MenuPickerSheet
        open={sheetOpen}
        menus={menus}
        loading={menusStatus === "loading"}
        error={menusStatus === "error" ? menuError || "加载失败" : ""}
        onRetry={loadMenus}
        onClose={() => setSheetOpen(false)}
        onPick={handlePickMenu}
        savingMenuId={savingMenuId}
      />

      <ExpiredMealPlanSheet
        open={expiredMealPlanOpen}
        onClose={() => setExpiredMealPlanOpen(false)}
        onContinue={() => resolveExpiredMealPlan("continue")}
        onComplete={() => resolveExpiredMealPlan("complete")}
        onCancelPlan={() => resolveExpiredMealPlan("cancel")}
        loadingAction={expiredMealPlanAction}
      />
    </div>
  );
}

function RecipeDetail() {
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
  const [renaming, setRenaming] = useState(false);
  const [expiredMealPlanOpen, setExpiredMealPlanOpen] = useState(false);
  const [expiredMealPlanAction, setExpiredMealPlanAction] = useState("");

  const reload = () => {
    setStatus("loading");
    getRecipe(id)
      .then((data) => {
        setRecipe(data);
        setStatus("success");
      })
      .catch(() => setStatus("error"));
  };

  useEffect(() => {
    reload();
  }, [id]);

  const loadMenus = () => {
    setMenusStatus("loading");
    setMenuError("");
    listMenus()
      .then((rows) => {
        setMenus(rows);
        setMenusStatus("success");
      })
      .catch((err) => {
        setMenusStatus("error");
        setMenuError(err.message);
      });
  };

  const openMenuPicker = () => {
    setActionSheetOpen(false);
    setSheetOpen(true);
    if (menusStatus === "idle") {
      loadMenus();
    }
  };

  const addCurrentRecipeToMealPlan = async () => {
    if (!recipe || mealPlanSaving) return;
    setMealPlanSaving(true);
    try {
      const result = await addMealPlanItem(recipe.id, "ask");
      if (result.status === "expired_confirmation_required") {
        setActionSheetOpen(false);
        setExpiredMealPlanOpen(true);
        return;
      }
      setActionSheetOpen(false);
      setAddedSuccess(true);
      setTimeout(() => setAddedSuccess(false), 900);
    } finally {
      setMealPlanSaving(false);
    }
  };

  const resolveExpiredMealPlan = async (mode) => {
    if (!recipe) return;
    setExpiredMealPlanAction(mode);
    try {
      await addMealPlanItem(recipe.id, mode);
      setExpiredMealPlanOpen(false);
      setAddedSuccess(true);
      setTimeout(() => setAddedSuccess(false), 900);
    } finally {
      setExpiredMealPlanAction("");
    }
  };

  const renameRecipe = async () => {
    if (!recipe || renaming) return;
    const nextName = window.prompt("修改菜谱标题", recipe.name);
    if (nextName === null) return;
    const trimmed = nextName.trim();
    if (!trimmed || trimmed === recipe.name) return;

    setRenaming(true);
    try {
      const updated = await updateRecipe(id, {
        name: trimmed,
        description: recipe.description,
        cook_time_minutes: recipe.cook_time_minutes,
        difficulty: recipe.difficulty,
        tags: recipe.tags,
        source_type: recipe.source_type,
        source_url: recipe.source_url,
        cover_image_url: recipe.cover_image_url,
        main_ingredient: recipe.main_ingredient,
        dish_type: recipe.dish_type,
        cooking_method: recipe.cooking_method,
        ingredients: recipe.ingredients.map((item) => ({
          name: item.name,
          amount: item.amount,
          unit: item.unit,
          is_main: item.is_main
        })),
        steps: recipe.steps.map((step) => ({
          step_order: step.step_order,
          instruction: step.instruction,
          image_url: step.image_url
        })),
        media: recipe.media.map((media) => ({
          media_type: media.media_type,
          url: media.url
        }))
      });
      setRecipe(updated);
    } finally {
      setRenaming(false);
    }
  };

  const handlePickMenu = async (menuId) => {
    setSavingMenuId(menuId);
    try {
      await addMenuItem(menuId, recipe.id);
      setSheetOpen(false);
      setAddedSuccess(true);
      setTimeout(() => setAddedSuccess(false), 900);
      if (menusStatus === "success") {
        setMenus((prev) => prev.map((m) => (String(m.id) === String(menuId) ? { ...m, item_count: (m.item_count || 0) + 1 } : m)));
      }
    } catch (err) {
      setMenuError(err.message);
      setMenusStatus("error");
    } finally {
      setSavingMenuId(null);
    }
  };

  if (status === "loading") return <LoadingBlock />;
  if (status === "error") return <ErrorBlock onRetry={reload} />;

  return (
    <div className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <button onClick={() => navigate(-1)} className="rounded-xl bg-gray-100 px-3 py-2 text-sm">
          返回
        </button>
        <div className="flex gap-2">
          <IconButton onClick={renameRecipe} disabled={renaming} title="修改标题">
            ✎
          </IconButton>
          <IconButton onClick={() => setActionSheetOpen(true)} active={addedSuccess} title="更多操作">
            {addedSuccess ? "✓" : "⋮"}
          </IconButton>
        </div>
      </div>

      <ImageOrPlaceholder src={recipe.cover_image_url} alt={recipe.name} className="mb-3 h-48 w-full rounded-xl object-cover" placeholderClassName="mb-3 h-48 rounded-xl bg-gray-200" />
      <h1 className="mb-2 text-lg font-bold">{recipe.name}</h1>
      <div className="mb-3 text-sm text-gray-500">⏱{recipe.cook_time_minutes}min ⭐{recipe.difficulty}</div>

      <div className="mb-3">
        <div className="mb-1 font-semibold">食材</div>
        <div className="text-sm text-gray-700">{recipe.ingredients.map((i) => i.name).join("、")}</div>
      </div>

      <div>
        <div className="mb-1 font-semibold">步骤</div>
        <div className="space-y-2">
          {recipe.steps
            .slice()
            .sort((a, b) => a.step_order - b.step_order)
            .map((step) => (
              <div key={step.id} className="rounded-xl bg-white p-2">
                <div className="mb-1 text-xs text-gray-500">步骤 {step.step_order}</div>
                <div className="text-sm">{step.instruction}</div>
                {isUsableImage(step.image_url) ? <ImageOrPlaceholder src={step.image_url} alt="step" className="mt-2 w-full rounded-lg" placeholderClassName="mt-2 h-32 w-full rounded-lg bg-gray-100" /> : null}
              </div>
            ))}
        </div>
      </div>

      <RecipeActionSheet
        open={actionSheetOpen}
        title="菜谱操作"
        onClose={() => setActionSheetOpen(false)}
        options={[
          { label: "加入餐单", loading: mealPlanSaving, loadingLabel: "加入中", onClick: addCurrentRecipeToMealPlan },
          { label: "加入菜单", onClick: openMenuPicker }
        ]}
      />

      <MenuPickerSheet
        open={sheetOpen}
        menus={menus}
        loading={menusStatus === "loading"}
        error={menusStatus === "error" ? menuError || "加载失败" : ""}
        onRetry={loadMenus}
        onClose={() => setSheetOpen(false)}
        onPick={handlePickMenu}
        savingMenuId={savingMenuId}
      />

      <ExpiredMealPlanSheet
        open={expiredMealPlanOpen}
        onClose={() => setExpiredMealPlanOpen(false)}
        onContinue={() => resolveExpiredMealPlan("continue")}
        onComplete={() => resolveExpiredMealPlan("complete")}
        onCancelPlan={() => resolveExpiredMealPlan("cancel")}
        loadingAction={expiredMealPlanAction}
      />
    </div>
  );
}

function Plan() {
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
  const listBottomRef = useRef(null);

  const loadMealPlans = async () => {
    setStatus("loading");
    try {
      const [current, recent] = await Promise.all([getCurrentMealPlan(), listMealPlans(5)]);
      setCurrentMealPlan(current);
      setMealPlans(recent);
      setView(current ? "detail" : "list");
      setStatus("success");
    } catch {
      setStatus("error");
    }
  };

  useEffect(() => {
    loadMealPlans();
  }, []);

  useEffect(() => {
    if (view === "list" && status === "success") {
      listBottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [mealPlans, view, status]);

  const removeFromMealPlan = async (itemId) => {
    if (!currentMealPlan) return;
    setRemovingItemId(itemId);
    try {
      await removeMealPlanItem(currentMealPlan.id, itemId);
      const refreshed = await getMealPlan(currentMealPlan.id);
      setCurrentMealPlan(refreshed);
      setActionItem(null);
    } finally {
      setRemovingItemId(null);
    }
  };

  const completeCurrent = async () => {
    if (!currentMealPlan || completing) return;
    setCompleting(true);
    try {
      await completeMealPlan(currentMealPlan.id);
      await loadMealPlans();
      setView("list");
    } finally {
      setCompleting(false);
    }
  };

  const deleteCurrent = async () => {
    if (!currentMealPlan || deleting) return;
    setDeleting(true);
    try {
      await deleteMealPlan(currentMealPlan.id);
      await loadMealPlans();
      setView("list");
    } finally {
      setDeleting(false);
    }
  };

  const cancelCurrent = async () => {
    if (!currentMealPlan || cancelling) return;
    setCancelling(true);
    try {
      await cancelMealPlan(currentMealPlan.id);
      await loadMealPlans();
      setView("list");
    } finally {
      setCancelling(false);
    }
  };

  const resumePlan = async (mealPlanId) => {
    setResumingId(mealPlanId);
    try {
      const resumed = await resumeMealPlan(mealPlanId);
      setCurrentMealPlan(resumed);
      await loadMealPlans();
      setView("detail");
    } finally {
      setResumingId(null);
    }
  };

  const copyPlan = async (mealPlanId) => {
    setCopyingId(mealPlanId);
    try {
      const copied = await copyMealPlan(mealPlanId);
      setCurrentMealPlan(copied);
      await loadMealPlans();
      setView("detail");
    } finally {
      setCopyingId(null);
    }
  };

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
    } finally {
      setRenaming(false);
    }
  };

  if (status === "loading") return <LoadingBlock />;
  if (status === "error") return <ErrorBlock onRetry={loadMealPlans} />;

  return (
    <div className="p-4">
      {view === "detail" && currentMealPlan ? (
        <div>
          <div className="mb-3 flex items-center justify-between">
            <button onClick={() => setView("list")} className="rounded-xl bg-gray-100 px-3 py-2 text-sm">
              返回列表
            </button>
            <div className="text-center">
              <div className="font-bold">{currentMealPlan.name}</div>
              <div className="text-xs text-gray-500">预计完成：{currentMealPlan.expected_finish_at ? new Date(currentMealPlan.expected_finish_at).toLocaleString() : "未设置"}</div>
            </div>
            <IconButton onClick={renameCurrent} disabled={renaming} title="修改标题">
              ✎
            </IconButton>
          </div>

          {currentMealPlan.items.length === 0 ? (
            <div className="pb-24 text-sm text-gray-500">当前餐单还没有菜，去菜谱页或菜单页添加。</div>
          ) : (
            <div className="pb-24">
              {currentMealPlan.items.map((item) => (
                <RecipeCard
                  key={item.id}
                  recipe={{
                    name: item.recipe_name,
                    cook_time_minutes: item.recipe_cook_time_minutes || 0,
                    difficulty: item.recipe_difficulty || "unknown",
                    cover_image_url: item.recipe_cover_image_url
                  }}
                  onClick={() => navigate(`/recipes/${item.recipe_id}`)}
                  overlayActions={
                    <IconButton onClick={() => setActionItem(item)} disabled={removingItemId === item.id} title="更多操作">
                      ⋮
                    </IconButton>
                  }
                />
              ))}
            </div>
          )}

          <div className="fixed bottom-16 left-1/2 z-10 w-full max-w-sm -translate-x-1/2 border-t bg-white p-4">
            <div className="flex gap-2">
              <button onClick={completeCurrent} disabled={completing} className="flex-1 rounded-xl bg-black p-3 text-white disabled:opacity-40">
                {completing ? "完成中" : "完成餐单"}
              </button>
              <button onClick={cancelCurrent} disabled={cancelling} className="flex-1 rounded-xl bg-yellow-50 p-3 text-yellow-700 disabled:opacity-40">
                {cancelling ? "取消中" : "取消餐单"}
              </button>
              <button onClick={deleteCurrent} disabled={deleting} className="flex-1 rounded-xl bg-red-50 p-3 text-red-600 disabled:opacity-40">
                {deleting ? "删除中" : "删除餐单"}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div>
          <div className="mb-3 font-bold">最近餐单</div>
          {mealPlans.length === 0 ? <div className="text-sm text-gray-500">还没有餐单。</div> : null}
          <div className="space-y-2">
            {mealPlans.map((plan) => (
              <div key={plan.id} className="rounded-2xl bg-white p-3 shadow">
                <div className="font-semibold">{plan.name}</div>
                <div className="mb-2 text-xs text-gray-500">{plan.item_count} 道菜 · {plan.status === "editing" ? "编辑中" : plan.status === "completed" ? "已完成" : "已取消"}</div>
                <div className="flex gap-2">
                  <button onClick={async () => { const detail = await getMealPlan(plan.id); setCurrentMealPlan(detail); setView("detail"); }} className="flex-1 rounded-xl bg-gray-100 p-2 text-sm">
                    查看
                  </button>
                  {plan.status !== "editing" ? (
                    <button onClick={() => resumePlan(plan.id)} disabled={resumingId === plan.id} className="flex-1 rounded-xl bg-black p-2 text-sm text-white disabled:opacity-40">
                      {resumingId === plan.id ? "恢复中" : "恢复编辑中"}
                    </button>
                  ) : null}
                  {plan.status !== "editing" ? (
                    <button onClick={() => copyPlan(plan.id)} disabled={copyingId === plan.id} className="flex-1 rounded-xl bg-gray-100 p-2 text-sm disabled:opacity-40">
                      {copyingId === plan.id ? "复制中" : "复制为新餐单"}
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
            <div ref={listBottomRef} />
          </div>
        </div>
      )}

      <RecipeActionSheet
        open={!!actionItem}
        title="菜谱操作"
        onClose={() => setActionItem(null)}
        options={[
          { label: "移出餐单", tone: "danger", loading: removingItemId === actionItem?.id, loadingLabel: "移出中", onClick: () => removeFromMealPlan(actionItem.id) }
        ]}
      />
    </div>
  );
}

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <div className="mx-auto flex h-screen max-w-sm flex-col bg-gray-50">
      <div className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/recipes" element={<RecipesList />} />
          <Route path="/recipes/:id" element={<RecipeDetail />} />
          <Route path="/menus" element={<MenusList />} />
          <Route path="/menus/:id" element={<MenuDetail />} />
          <Route path="/plan" element={<Plan />} />
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
