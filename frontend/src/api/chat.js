import { apiFetch } from "./client";

export function sendChatMessage({ session_id, message, context = {} }) {
  return apiFetch("/chat/messages", {
    method: "POST",
    body: JSON.stringify({
      session_id,
      message,
      context
    })
  });
}

export function getChatMessages(sessionId, limit = 20) {
  return apiFetch(`/chat/sessions/${sessionId}/messages?limit=${limit}`);
}
