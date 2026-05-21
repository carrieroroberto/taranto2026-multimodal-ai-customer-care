const SESSION_KEY = "taranto2026.sessionId";

export function getOrCreateSessionId() {
  const existing = localStorage.getItem(SESSION_KEY);
  if (existing) {
    return existing;
  }

  const sessionId =
    globalThis.crypto?.randomUUID?.() ||
    `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;

  localStorage.setItem(SESSION_KEY, sessionId);
  return sessionId;
}
