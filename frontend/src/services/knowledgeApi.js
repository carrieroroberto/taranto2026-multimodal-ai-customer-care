const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

export async function fetchKnowledgeOptions(token) {
  return knowledgeFetch("/knowledge/options", { token });
}

export async function createKnowledgeRecord(token, payload) {
  return knowledgeFetch("/knowledge/records", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

async function knowledgeFetch(path, { method = "GET", token, body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${DEFAULT_API_BASE}${path}`, {
    method,
    headers,
    body,
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
