import json
import os
import re
import time
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from models import ChatSession, ChatMessage
from config import load_env_file
from schemas import (
    ChatAction,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatCard,
    ChatHistoryMessage,
    ChatHistoryResponse,
    HybridSearchRequest,
)
from services.menu_template_service import list_menus
from services.recipe_service import get_recipe_by_id, search_recipes_hybrid

load_env_file()


class ChatServiceError(Exception):
    pass


def _chat_base_url() -> str:
    return (
        os.getenv("CHAT_LLM_BASE_URL", "").strip()
        or os.getenv("RECIPE_PARSER_BASE_URL", "").strip()
        or os.getenv("EMBEDDING_BASE_URL", "").strip()
    )


def _chat_api_key() -> str:
    return (
        os.getenv("CHAT_LLM_API_KEY", "").strip()
        or os.getenv("RECIPE_PARSER_API_KEY", "").strip()
        or os.getenv("EMBEDDING_API_KEY", "").strip()
    )


def _chat_model() -> str:
    return (
        os.getenv("CHAT_LLM_MODEL", "").strip()
        or os.getenv("RECIPE_PARSER_MODEL", "").strip()
    )


def _build_llm_prompt(payload: ChatMessageRequest) -> str:
    return (
        "你是小厨，是一个中文厨师助理。"
        "请先理解用户意图，再输出一个严格 JSON 对象。"
        "不要输出 markdown，不要输出代码块，不要输出解释性前缀。"
        "JSON schema 如下：\n"
        '{"reply_text":"string","action":{"type":"list_menus|search_recipes|get_recipe|go_plan|import_xiachufang_recipe|import_xiachufang_homepage|none","query":"string|null","id":"string|null","url":"string|null","limit":3}}\n'
        "规则：\n"
        "1. 用户想看常用菜单、推荐菜单、菜单列表时，用 list_menus。\n"
        "2. 用户在找菜谱、按口味/食材/做法搜索时，用 search_recipes，并填写 query。\n"
        "3. 只有用户明确提到具体 recipe id 时，才用 get_recipe。\n"
        "4. 如果用户提供下厨房单个菜谱链接，使用 import_xiachufang_recipe，并填写 url。\n"
        "5. 如果用户要求导入下厨房首页/推荐菜谱，使用 import_xiachufang_homepage。\n"
        "6. 不要编造菜单或菜谱 id；除 get_recipe 外，不需要返回真实 id。\n"
        "7. 若只是普通闲聊、无法确定、或不需要卡片，使用 none。\n"
        "8. reply_text 使用自然中文，简洁友好。\n"
        f"当前页面上下文: {json.dumps(payload.context, ensure_ascii=False)}\n"
        f"用户消息: {payload.message}"
    )


def _ordinal_to_index(text: str) -> int | None:
    mapping = {
        "第一个": 0,
        "第二个": 1,
        "第三个": 2,
        "第四个": 3,
        "第五个": 4,
        "第1个": 0,
        "第2个": 1,
        "第3个": 2,
        "第4个": 3,
        "第5个": 4,
    }
    for key, value in mapping.items():
        if key in text:
            return value
    return None


def _latest_assistant_cards(db: Session, session_id: str) -> list[dict[str, Any]]:
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).one_or_none()
    if not session:
        return []

    row = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_ref_id == session.id, ChatMessage.role == "assistant")
        .order_by(ChatMessage.id.desc())
        .first()
    )
    if not row or not isinstance(row.cards_json, list):
        return []
    return [card for card in row.cards_json if isinstance(card, dict)]


def _reference_hint_from_latest_cards(db: Session, session_id: str, message: str) -> str:
    cards = _latest_assistant_cards(db, session_id)
    if not cards:
        return ""

    idx = _ordinal_to_index(message)
    if idx is None or idx >= len(cards):
        return ""

    card = cards[idx]
    card_type = str(card.get("type") or "").strip()
    card_id = str(card.get("id") or "").strip()
    title = str(card.get("title") or "").strip()
    if not card_type or not card_id or not title:
        return ""

    return (
        "补充上下文：用户这次提到的顺序指代，指向上一条 assistant 回复中的卡片。"
        f"当前消息里的对象 = 第{idx + 1}个卡片，type={card_type}, id={card_id}, title={title}。"
    )


def _recent_history_messages(db: Session, session_id: str, limit: int = 10) -> list[dict[str, str]]:
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).one_or_none()
    if not session:
        return []

    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_ref_id == session.id)
        .order_by(ChatMessage.id.desc())
        .limit(max(1, min(limit, 50)))
        .all()
    )
    rows.reverse()

    history = []
    for row in rows:
        role = row.role if row.role in {"user", "assistant", "system"} else "user"
        content = row.content or ""

        # Expose prior clickable cards to the model so it can resolve follow-ups
        # like "第一个菜单" or "刚才第二个菜谱" against real ids/titles.
        if role == "assistant" and isinstance(row.cards_json, list) and row.cards_json:
            card_lines = []
            for idx, card in enumerate(row.cards_json, start=1):
                if not isinstance(card, dict):
                    continue
                card_type = str(card.get("type") or "").strip()
                card_id = str(card.get("id") or "").strip()
                title = str(card.get("title") or "").strip()
                subtitle = str(card.get("subtitle") or "").strip()
                if not card_type or not card_id or not title:
                    continue
                line = f"卡片{idx}: type={card_type}, id={card_id}, title={title}"
                if subtitle:
                    line += f", subtitle={subtitle}"
                card_lines.append(line)

            if card_lines:
                content = f"{content}\n\n上一条回复中的可点击卡片:\n" + "\n".join(card_lines)

        history.append({"role": role, "content": content})
    return history


def _call_chat_llm(payload: ChatMessageRequest) -> dict[str, Any]:
    base_url = _chat_base_url()
    api_key = _chat_api_key()
    model = _chat_model()
    timeout_seconds = float(os.getenv("CHAT_LLM_TIMEOUT_SECONDS", "30"))

    if not base_url or not api_key or not model:
        raise ChatServiceError(
            "Missing chat model config: CHAT_LLM_BASE_URL / CHAT_LLM_API_KEY / CHAT_LLM_MODEL."
        )

    request_payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "你是一个严格按 JSON schema 输出的中文厨师助理。"},
            {"role": "user", "content": _build_llm_prompt(payload)},
        ],
    }

    body = None
    for attempt in range(2):
        req = Request(
            url=f"{base_url.rstrip('/')}/chat/completions",
            data=json.dumps(request_payload).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

        try:
            with urlopen(req, timeout=timeout_seconds) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                break
        except HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="ignore")
            if exc.code == 429 and attempt == 0:
                time.sleep(1.2)
                continue
            raise ChatServiceError(f"Chat model HTTP error {exc.code}: {err_body[:300]}") from exc
        except URLError as exc:
            raise ChatServiceError(f"Chat model network error: {exc}") from exc
        except Exception as exc:
            raise ChatServiceError(f"Chat model request failed: {exc}") from exc

    if body is None:
        raise ChatServiceError("Chat model did not return a response.")

    try:
        parsed = json.loads(body)
        content = parsed["choices"][0]["message"]["content"]
    except Exception as exc:
        raise ChatServiceError("Chat model response parse failed.") from exc

    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    return {"reply_text": content.strip() or "我暂时无法生成回复。", "action": {"type": "none"}}


def _cards_from_action(db: Session, action: dict[str, Any]) -> list[ChatCard]:
    action_type = str(action.get("type") or "none").strip()
    limit = action.get("limit")
    try:
        limit = int(limit) if limit is not None else 3
    except Exception:
        limit = 3
    limit = max(1, min(limit, 10))

    if action_type == "list_menus":
        menus = list_menus(db)[:limit]
        return [
            ChatCard(type="menu", id=str(menu.id), title=menu.name, subtitle=menu.description or "可复用菜单")
            for menu in menus
        ]

    if action_type == "search_recipes":
        query = str(action.get("query") or "").strip()
        if not query:
            return []
        results = search_recipes_hybrid(
            db,
            HybridSearchRequest(query=query, top_k=limit, semantic_weight=0.7),
        )
        return [
            ChatCard(
                type="recipe",
                id=str(item.recipe.id),
                title=item.recipe.name,
                subtitle=f"{item.recipe.cook_time_minutes} 分钟 · {item.recipe.difficulty}",
                image_url=item.recipe.cover_image_url,
            )
            for item in results.results
        ]

    if action_type == "get_recipe":
        raw_id = str(action.get("id") or "").strip()
        if not raw_id.isdigit():
            return []
        recipe = get_recipe_by_id(db, int(raw_id))
        if not recipe:
            return []
        return [
            ChatCard(
                type="recipe",
                id=str(recipe.id),
                title=recipe.name,
                subtitle=f"{recipe.cook_time_minutes} 分钟 · {recipe.difficulty}",
                image_url=recipe.cover_image_url,
            )
        ]

    if action_type == "go_plan":
        return [ChatCard(type="plan", id="today-plan", title="去今日计划", subtitle="查看要做的菜")]

    return []


def _execute_import_action(db: Session, action: dict[str, Any]) -> tuple[str | None, list[ChatCard]]:
    action_type = str(action.get("type") or "none").strip()

    if action_type == "import_xiachufang_recipe":
        url = str(action.get("url") or "").strip()
        if not url:
            return "我没有识别到有效的下厨房菜谱链接。", []
        return (
            "我已识别到这个下厨房菜谱链接。请在 App 内打开该页面，完成验证后由 App 提交页面 HTML 给后端导入。",
            [],
        )

    if action_type == "import_xiachufang_homepage":
        return (
            "我已识别到你要导入下厨房首页推荐菜。请在 App 内打开下厨房首页，完成验证后由 App 抓取推荐菜链接，并分别提交每个菜谱页面 HTML 给后端导入。",
            [],
        )

    return None, []


def _get_or_create_session(db: Session, session_id: str) -> ChatSession:
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).one_or_none()
    if session:
        return session

    session = ChatSession(session_id=session_id)
    db.add(session)
    db.flush()
    return session


def _save_message(db: Session, session: ChatSession, role: str, content: str, cards: list[ChatCard] | None = None) -> None:
    db.add(
        ChatMessage(
            session_ref_id=session.id,
            role=role,
            content=content,
            cards_json=[card.model_dump() for card in (cards or [])] or None,
        )
    )


def list_recent_chat_messages(db: Session, session_id: str, limit: int = 20) -> ChatHistoryResponse:
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).one_or_none()
    if not session:
        return ChatHistoryResponse(session_id=session_id, messages=[])

    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_ref_id == session.id)
        .order_by(ChatMessage.id.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    rows.reverse()

    return ChatHistoryResponse(
        session_id=session_id,
        messages=[
            ChatHistoryMessage(
                id=row.id,
                role=row.role,
                content=row.content,
                cards=[ChatCard(**card) for card in (row.cards_json or []) if isinstance(card, dict)],
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
            for row in rows
        ],
    )


def send_chat_message_via_openclaw(db: Session, payload: ChatMessageRequest) -> ChatMessageResponse:
    session_id = payload.session_id or f"chef-chat-{uuid.uuid4().hex[:12]}"
    session = _get_or_create_session(db, session_id)
    history_messages = _recent_history_messages(db, session_id, limit=10)
    _save_message(db, session, "user", payload.message)

    llm_payload = ChatMessageRequest(
        session_id=session_id,
        message=payload.message,
        context=payload.context,
    )
    reference_hint = _reference_hint_from_latest_cards(db, session_id, payload.message)

    base_url = _chat_base_url()
    api_key = _chat_api_key()
    model = _chat_model()
    timeout_seconds = float(os.getenv("CHAT_LLM_TIMEOUT_SECONDS", "30"))

    if not base_url or not api_key or not model:
        raise ChatServiceError(
            "Missing chat model config: CHAT_LLM_BASE_URL / CHAT_LLM_API_KEY / CHAT_LLM_MODEL."
        )

    request_payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "你是一个严格按 JSON schema 输出的中文厨师助理。"},
            *history_messages,
            *([{"role": "system", "content": reference_hint}] if reference_hint else []),
            {"role": "user", "content": _build_llm_prompt(llm_payload)},
        ],
    }

    body = None
    for attempt in range(2):
        req = Request(
            url=f"{base_url.rstrip('/')}/chat/completions",
            data=json.dumps(request_payload).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

        try:
            with urlopen(req, timeout=timeout_seconds) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                break
        except HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="ignore")
            if exc.code == 429 and attempt == 0:
                time.sleep(1.2)
                continue
            raise ChatServiceError(f"Chat model HTTP error {exc.code}: {err_body[:300]}") from exc
        except URLError as exc:
            raise ChatServiceError(f"Chat model network error: {exc}") from exc
        except Exception as exc:
            raise ChatServiceError(f"Chat model request failed: {exc}") from exc

    if body is None:
        raise ChatServiceError("Chat model did not return a response.")

    try:
        parsed = json.loads(body)
        content = parsed["choices"][0]["message"]["content"]
    except Exception as exc:
        raise ChatServiceError("Chat model response parse failed.") from exc

    try:
        llm_output = json.loads(content)
        if not isinstance(llm_output, dict):
            raise ValueError("chat response is not object")
    except Exception:
        llm_output = {"reply_text": content.strip() or "我暂时无法生成回复。", "action": {"type": "none"}}

    reply_text = str(llm_output.get("reply_text") or "").strip() or "我暂时无法生成回复。"
    action = llm_output.get("action")
    if not isinstance(action, dict):
        action = {"type": "none"}

    try:
        override_reply, import_cards = _execute_import_action(db, action)
        cards = import_cards if import_cards else _cards_from_action(db, action)
        if override_reply:
            reply_text = override_reply
    except Exception:
        cards = []

    _save_message(db, session, "assistant", reply_text, cards)
    db.commit()

    chat_action = None
    try:
        chat_action = ChatAction(**action)
    except Exception:
        chat_action = ChatAction(type="none")

    return ChatMessageResponse(session_id=session_id, reply_text=reply_text, cards=cards, action=chat_action)
