const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";
const OPERATOR_TOKEN_KEY = "tarai-operator-token";
const OPERATOR_KEY = "tarai-operator";

export function getStoredOperatorSession() {
  const token = window.localStorage.getItem(OPERATOR_TOKEN_KEY);
  const rawOperator = window.localStorage.getItem(OPERATOR_KEY);
  let operator = null;
  if (rawOperator) {
    try {
      operator = JSON.parse(rawOperator);
    } catch (_error) {
      operator = null;
    }
  }
  return { token, operator };
}

export function storeOperatorSession({ token, operator }) {
  window.localStorage.setItem(OPERATOR_TOKEN_KEY, token);
  window.localStorage.setItem(OPERATOR_KEY, JSON.stringify(operator));
}

export function clearOperatorSession() {
  window.localStorage.removeItem(OPERATOR_TOKEN_KEY);
  window.localStorage.removeItem(OPERATOR_KEY);
}

export async function loginOperator({ email, password }) {
  const payload = await operatorFetch("/operator/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  return {
    token: payload.access_token,
    operator: payload.operator,
  };
}

export async function fetchOperatorProfile(token) {
  return operatorFetch("/operator/me", { token });
}

export async function logoutOperator(token) {
  return operatorFetch("/operator/logout", { method: "POST", token });
}

export async function fetchTickets(token, { status } = {}) {
  const params = new URLSearchParams();
  if (status && status !== "tutti") {
    params.set("status", status);
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return operatorFetch(`/operator/tickets${suffix}`, { token });
}

export async function fetchTicketDetail(token, ticketId) {
  return operatorFetch(`/operator/tickets/${encodeURIComponent(ticketId)}`, { token });
}

export async function updateTicketStatus(token, ticketId, status) {
  return operatorFetch(`/operator/tickets/${encodeURIComponent(ticketId)}/status`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ status }),
  });
}

export async function translateTicketConversation(token, ticketId) {
  return operatorFetch(`/operator/tickets/${encodeURIComponent(ticketId)}/translate`, {
    method: "POST",
    token,
  });
}

export async function generateTicketEmailDraft(token, ticketId) {
  return operatorFetch(`/operator/tickets/${encodeURIComponent(ticketId)}/email-draft`, {
    method: "POST",
    token,
  });
}

async function operatorFetch(path, { method = "GET", token, body } = {}) {
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
