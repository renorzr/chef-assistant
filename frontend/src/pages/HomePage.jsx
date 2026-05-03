import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getChatMessages, sendChatMessage } from "../api/chat";
import { addMenuItem, listMenus } from "../api/menus";
import { addMealPlanItem } from "../api/mealPlans";
import { openXiachufangImport, subscribeImportResult } from "../appBridge";
import { ChatMessage, LinkCard, RecipeCard } from "../components/cards";
import { ErrorBlock, IconButton, LoadingBlock } from "../components/common";
import { ExpiredMealPlanSheet, MenuPickerSheet, RecipeActionSheet } from "../components/sheets";

export default function HomePage() {
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
        .then((menusRows) => {
          setMessages([
            {
              role: "assistant",
              content: "这是你常用的菜单，可以直接选择👇",
              cards: menusRows.slice(0, 3).map((m) => ({ type: "menu", id: String(m.id), title: m.name, subtitle: m.description || "可复用菜单" }))
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
          return listMenus().then((menusRows) => {
            setMessages([
              {
                role: "assistant",
                content: "这是你常用的菜单，可以直接选择👇",
                cards: menusRows.slice(0, 3).map((m) => ({ type: "menu", id: String(m.id), title: m.name, subtitle: m.description || "可复用菜单" }))
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
                          return <LinkCard key={idx} title={card.title} subtitle={card.subtitle} type="验证" onClick={() => window.open(card.id, "_blank")} />;
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
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="输入你的需求..." className="w-full rounded-xl bg-gray-100 p-2" enterKeyHint="send" onKeyDown={(e) => {
          if (e.key === "Enter" && !e.nativeEvent.isComposing) sendMessage();
        }} />
      </div>

      <RecipeActionSheet open={sheetOpen} title="菜谱操作" onClose={() => setSheetOpen(false)} options={[
        { label: "加入餐单", loading: mealPlanSaving, loadingLabel: "加入中", onClick: addCurrentRecipeToMealPlan },
        { label: "加入菜单", onClick: openMenuPickerForCurrentRecipe }
      ]} />

      <MenuPickerSheet open={menuPickerOpen} menus={menus} loading={menusStatus === "loading"} error={menusStatus === "error" ? menuError || "加载失败" : ""} onRetry={loadMenusForPicker} onClose={() => setMenuPickerOpen(false)} onPick={handlePickMenu} savingMenuId={savingMenuId} />

      <ExpiredMealPlanSheet open={expiredMealPlanOpen} onClose={() => setExpiredMealPlanOpen(false)} onContinue={() => resolveExpiredMealPlan("continue")} onComplete={() => resolveExpiredMealPlan("complete")} onCancelPlan={() => resolveExpiredMealPlan("cancel")} loadingAction={expiredMealPlanAction} />
    </div>
  );
}
