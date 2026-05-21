const DEFAULT_API_BASE = getDefaultApiBase();

export async function sendChatMessage({ message, sessionId, signal }) {
  const response = await fetchWithTimeout(`${DEFAULT_API_BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
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

export async function sendMultimodalMessage({ file, sessionId, signal }) {
  const formData = new FormData();
  formData.append("file", file);
  if (sessionId) {
    formData.append("session_id", sessionId);
  }

  const response = await fetchWithTimeout(`${DEFAULT_API_BASE}/chat/multimodal`, {
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
  const { timeoutMs = 30000, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("Timeout della richiesta");
    }

    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function getDefaultApiBase() {
  if (window.location.protocol.startsWith("http") && window.location.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }

  return "http://127.0.0.1:8000";
}
