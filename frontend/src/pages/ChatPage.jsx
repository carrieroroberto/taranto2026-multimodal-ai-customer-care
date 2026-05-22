import { useEffect, useRef, useState } from "react";

import { AppHeader } from "../components/AppHeader.jsx";
import { ChatComposer } from "../components/ChatComposer.jsx";
import { ChatHeader } from "../components/ChatHeader.jsx";
import { DecorativeBackground } from "../components/DecorativeBackground.jsx";
import { LanguageSelector } from "../components/LanguageSelector.jsx";
import { MessageList } from "../components/MessageList.jsx";
import { ThemeToggle } from "../components/ThemeToggle.jsx";
import {
  getInitialLocale,
  getLocaleConfig,
  LOCALE_STORAGE_KEY,
  translations,
  SUPPORTED_LOCALES,
} from "../i18n.js";
import { sendChatMessage, sendMultimodalMessage } from "../services/chatApi.js";
import { getOrCreateSessionId } from "../utils/session.js";

const initialMessages = [
  {
    id: "welcome",
    role: "assistant",
    translationKey: "welcome",
    isLoading: false,
    isError: false,
  },
];

const THEME_STORAGE_KEY = "tarai-theme";

export function ChatPage() {
  const [messages, setMessages] = useState(initialMessages);
  const [isSending, setIsSending] = useState(false);
  const [theme, setTheme] = useState(() => getInitialTheme());
  const [locale, setLocale] = useState(() => getInitialLocale());
  const sessionIdRef = useRef(getOrCreateSessionId());
  const messageListRef = useRef(null);
  const abortControllerRef = useRef(null);
  const localeConfig = getLocaleConfig(locale);
  const t = translations[locale];

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);

    const themeColor = theme === "dark" ? "#061826" : "#06477a";
    document
      .querySelectorAll("meta[name='theme-color']")
      .forEach((metaElement) => {
        metaElement.setAttribute("content", themeColor);
      });
  }, [theme]);

  useEffect(() => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    document.documentElement.lang = localeConfig.htmlLang;
    document.documentElement.dir = localeConfig.dir;
    document.title = t.pageTitle;
  }, [locale, localeConfig.dir, localeConfig.htmlLang, t.pageTitle]);

  useEffect(() => {
    let secondFrameId = null;

    const firstFrameId = window.requestAnimationFrame(() => {
      scrollMessagesToBottom("smooth");
      secondFrameId = window.requestAnimationFrame(() => {
        scrollMessagesToBottom("smooth");
      });
    });

    const fallbackTimeoutId = window.setTimeout(() => {
      scrollMessagesToBottom("smooth");
    }, 120);

    return () => {
      window.cancelAnimationFrame(firstFrameId);
      if (secondFrameId) {
        window.cancelAnimationFrame(secondFrameId);
      }
      window.clearTimeout(fallbackTimeoutId);
    };
  }, [messages]);

  function scrollMessagesToBottom(behavior = "smooth") {
    const messageListElement = messageListRef.current;
    if (!messageListElement) {
      return;
    }

    messageListElement.scrollTo({
      top: messageListElement.scrollHeight,
      behavior,
    });
  }

  function handleStop() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsSending(false);
      
      // Update the last assistant message to show it was stopped
      setMessages((currentMessages) => {
        const lastMessage = currentMessages[currentMessages.length - 1];
        if (lastMessage?.role === "assistant" && lastMessage.isLoading) {
          return [
            ...currentMessages.slice(0, -1),
            {
              ...lastMessage,
              text: t.stoppedResponse,
              isLoading: false,
              isError: true,
            },
          ];
        }
        return currentMessages;
      });
    }
  }

  async function handleSend(message) {
    if (!message || isSending) {
      return;
    }

    const userMessage = createMessage("user", message);
    const pendingMessage = createMessage("assistant", "", true);

    setMessages((currentMessages) => [
      ...currentMessages,
      userMessage,
      pendingMessage,
    ]);
    setIsSending(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await sendChatMessage({
        message,
        sessionId: sessionIdRef.current,
        language: locale,
        signal: controller.signal
      });

      patchMessage(pendingMessage.id, {
        text: response.answer || t.unavailableAnswer,
        sources: normalizeSources(response.sources),
        isLoading: false,
      });
    } catch (error) {
      if (error.name === "AbortError") return;
      patchMessage(pendingMessage.id, {
        text: `${t.errorPrefix} ${error.message}.`,
        isLoading: false,
        isError: true,
      });
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
        setIsSending(false);
      }
    }
  }

  async function handleFileSend(file, message = "", metadata = {}) {
    if (!file || isSending) {
      return;
    }

    const isImage = file.type.startsWith("image/");
    const trimmedMessage = message.trim();
    if (isImage && !trimmedMessage) {
      return;
    }

    const objectUrl = URL.createObjectURL(file);
    
    const userMessage = createMessage(
      "user",
      isImage ? trimmedMessage : ""
    );
    if (isImage) {
      userMessage.image = objectUrl;
    } else {
      userMessage.audio = {
        url: objectUrl,
        durationMs: metadata.durationMs || 0,
        waveform: metadata.waveform || null,
      };
    }

    const pendingMessage = createMessage("assistant", "", true);

    setMessages((currentMessages) => [
      ...currentMessages,
      userMessage,
      pendingMessage,
    ]);
    setIsSending(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await sendMultimodalMessage({
        file,
        message: isImage ? trimmedMessage : undefined,
        sessionId: sessionIdRef.current,
        language: locale,
        signal: controller.signal
      });

      patchMessage(pendingMessage.id, {
        text: response.answer || t.unavailableAnswer,
        sources: normalizeSources(response.sources),
        isLoading: false,
      });
    } catch (error) {
      if (error.name === "AbortError") return;
      patchMessage(pendingMessage.id, {
        text: `${t.errorPrefix} ${error.message}.`,
        isLoading: false,
        isError: true,
      });
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
        setIsSending(false);
      }
    }
  }

  function patchMessage(messageId, patch) {
    setMessages((currentMessages) =>
      currentMessages.map((message) =>
        message.id === messageId ? { ...message, ...patch } : message,
      ),
    );
  }

  function handleThemeToggle() {
    setTheme((currentTheme) => (currentTheme === "dark" ? "light" : "dark"));
  }

  function handleLocaleChange(nextLocale) {
    setLocale(nextLocale);
  }

  return (
    <div
      className="app-surface relative flex h-dvh max-h-dvh flex-col overflow-hidden"
      data-theme={theme}
      dir={localeConfig.dir}
      lang={localeConfig.htmlLang}
    >
      <DecorativeBackground />
      <AppHeader
        locale={locale}
        locales={SUPPORTED_LOCALES}
        theme={theme}
        t={t}
        onLocaleChange={handleLocaleChange}
        onThemeToggle={handleThemeToggle}
      />
      <main className="main-stage relative z-10">
        <div className="chat-card-frame w-full max-w-5xl">
          <section className="chat-shell flex h-full w-full flex-col overflow-hidden">
            <ChatHeader t={t} />
            <MessageList
              messages={messages}
              listRef={messageListRef}
              mobileActionSlot={
                <div className="floating-mobile-actions">
                  <LanguageSelector
                    className="language-select-mobile"
                    locale={locale}
                    locales={SUPPORTED_LOCALES}
                    t={t}
                    onLocaleChange={handleLocaleChange}
                  />
                  <ThemeToggle
                    className="theme-toggle-mobile"
                    theme={theme}
                    t={t}
                    onThemeToggle={handleThemeToggle}
                  />
                </div>
              }
              theme={theme}
              t={t}
              onContentLoad={() => scrollMessagesToBottom("smooth")}
            />
            <ChatComposer
              isSending={isSending}
              t={t}
              onSend={handleSend}
              onFileSend={handleFileSend}
              onStop={handleStop}
            />
          </section>
        </div>
      </main>
    </div>
  );
}

function getInitialTheme() {
  if (typeof window === "undefined") {
    return "light";
  }

  const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (savedTheme === "dark" || savedTheme === "light") {
    return savedTheme;
  }

  return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches
    ? "dark"
    : "light";
}

function createMessage(role, text, isLoading = false) {
  return {
    id:
      globalThis.crypto?.randomUUID?.() ||
      `${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role,
    text,
    isLoading,
    isError: false,
  };
}

function normalizeSources(sources) {
  if (!Array.isArray(sources)) {
    return [];
  }

  return sources
    .filter((source) => typeof source?.url === "string" && source.url.trim())
    .slice(0, 3);
}
