const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

export async function startConversation({ sessionId }) {
  const response = await fetchWithTimeout(`${DEFAULT_API_BASE}/conversations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id: sessionId,
    }),
    timeoutMs: 30000,
  });

  const payload = await parseJsonResponse(response);

  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }

  return payload;
}

export async function fetchConversationMessages({ sessionId }) {
  const response = await fetchWithTimeout(
    `${DEFAULT_API_BASE}/conversations/${encodeURIComponent(sessionId)}/messages`,
    {
      method: "GET",
      timeoutMs: 30000,
    },
  );

  const payload = await parseJsonResponse(response);

  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }

  return payload;
}

export async function saveConversationMessage({
  sessionId,
  role,
  content,
  messageType = "text",
  mediaUrl = null,
  sources = null,
}) {
  const response = await fetchWithTimeout(
    `${DEFAULT_API_BASE}/conversations/${encodeURIComponent(sessionId)}/messages`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        role,
        content,
        message_type: messageType,
        media_url: mediaUrl,
        sources,
      }),
      timeoutMs: 30000,
    },
  );

  const payload = await parseJsonResponse(response);

  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }

  return payload;
}

export async function deleteConversationMessages({ sessionId, messageIds }) {
  const response = await fetchWithTimeout(
    `${DEFAULT_API_BASE}/conversations/${encodeURIComponent(sessionId)}/messages`,
    {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message_ids: messageIds,
      }),
      timeoutMs: 30000,
    },
  );

  const payload = await parseJsonResponse(response);

  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }

  return payload;
}

export async function sendChatMessage({ message, sessionId, language, signal }) {
  const response = await fetchWithTimeout(`${DEFAULT_API_BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      language,
    }),
    timeoutMs: 180000,
    signal,
  });

  const payload = await parseJsonResponse(response);

  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }

  return payload;
}

export async function sendFeedback({ sessionId, messageId, satisfied }) {
  const response = await fetchWithTimeout(`${DEFAULT_API_BASE}/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id: sessionId,
      message_id: messageId,
      rating: satisfied ? 5 : 1,
    }),
    timeoutMs: 30000,
  });

  const payload = await parseJsonResponse(response);

  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }

  return payload;
}

export async function updateMessageFeedback({ messageId, satisfaction }) {
  const response = await fetchWithTimeout(
    `${DEFAULT_API_BASE}/messages/${encodeURIComponent(messageId)}/feedback`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ satisfaction }),
      timeoutMs: 30000,
    },
  );

  const payload = await parseJsonResponse(response);

  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }

  return payload;
}

export async function sendTicket({
  conversationId,
  escalatedMessageId,
  userEmail,
  language,
  signal,
}) {
  const response = await fetchWithTimeout(`${DEFAULT_API_BASE}/tickets`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      conversation_id: conversationId,
      escalated_message_id: escalatedMessageId || null,
      user_email: userEmail,
      language,
    }),
    timeoutMs: 30000,
    signal,
  });

  const payload = await parseJsonResponse(response);

  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }

  return payload;
}

export async function sendMultimodalMessage({ file, message, sessionId, language, signal }) {
  const formData = new FormData();
  formData.append("file", file);
  if (message) {
    formData.append("message", message);
  }
  if (sessionId) {
    formData.append("session_id", sessionId);
  }
  if (language) {
    formData.append("language", language);
  }

  const endpoint = file.type.startsWith("audio/")
    ? `${DEFAULT_API_BASE}/chat/audio`
    : `${DEFAULT_API_BASE}/chat/multimodal`;

  const response = await fetchWithTimeout(endpoint, {
    method: "POST",
    body: formData,
    timeoutMs: 300000, // 5 minutes for multimodal processing
    signal,
  });

  const payload = await parseJsonResponse(response);

  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }

  return payload;
}

async function parseJsonResponse(response) {
  const text = await response.text();
  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text);
  } catch (_error) {
    return { detail: text };
  }
}

async function fetchWithTimeout(url, options = {}) {
  const { timeoutMs = 30000, signal, ...fetchOptions } = options;
  const controller = new AbortController();
  let didTimeout = false;
  const timeoutId = window.setTimeout(() => {
    didTimeout = true;
    controller.abort();
  }, timeoutMs);

  const abortFromCaller = () => controller.abort();
  if (signal?.aborted) {
    abortFromCaller();
  } else {
    signal?.addEventListener("abort", abortFromCaller, { once: true });
  }

  try {
    return await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === "AbortError" && didTimeout) {
      throw new Error("Timeout della richiesta");
    }

    throw error;
  } finally {
    window.clearTimeout(timeoutId);
    signal?.removeEventListener("abort", abortFromCaller);
  }
}

