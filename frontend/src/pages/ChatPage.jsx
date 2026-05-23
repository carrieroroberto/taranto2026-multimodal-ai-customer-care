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
import {
  fetchConversationMessages,
  sendChatMessage,
  sendFeedback,
  sendMultimodalMessage,
  sendTicket,
  startConversation,
} from "../services/chatApi.js";
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
  const [isEscalating, setIsEscalating] = useState(false);
  const [isSendingTicket, setIsSendingTicket] = useState(false);
  const [theme, setTheme] = useState(() => getInitialTheme());
  const [locale, setLocale] = useState(() => getInitialLocale());
  const sessionIdRef = useRef(getOrCreateSessionId());
  const messageListRef = useRef(null);
  const abortControllerRef = useRef(null);
  const scrollAnimationFrameRef = useRef(null);
  
  const localeConfig = getLocaleConfig(locale);
  const t = translations[locale] || translations["it"];

  useEffect(() => {
    let isCancelled = false;
    const sessionId = sessionIdRef.current;

    async function hydrateConversation() {
      try {
        await startConversation({ sessionId });
        const payload = await fetchConversationMessages({ sessionId });
        
        if (isCancelled || !payload || !Array.isArray(payload.messages)) {
          return;
        }

        const persistedMessages = payload.messages.map(mapPersistedMessage);
        
        if (persistedMessages.length > 0) {
          setMessages((currentMessages) => {
            const onlyWelcome =
              currentMessages.length === 1 &&
              currentMessages[0]?.id === initialMessages[0].id;

            return onlyWelcome
              ? [initialMessages[0], ...persistedMessages]
              : currentMessages;
          });

          // PERSIST ESCALATION STATE
          const lastMsg = persistedMessages[persistedMessages.length - 1];
          if (lastMsg && lastMsg.role === "assistant") {
            const text = (lastMsg.text || "").toLowerCase();
            if (
              text.includes("inserisci l'email") || 
              text.includes("enter your email") ||
              text.includes("ingresa tu correo") ||
              text.includes("saisissez votre e-mail")
            ) {
              setIsEscalating(true);
            }
          }
        }
      } catch (error) {
        console.error("Hydration error:", error);
      }
    }

    hydrateConversation();

    return () => {
      isCancelled = true;
    };
  }, []);

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
    scrollMessagesToBottom("smooth");
  }, [messages]);

  function scrollMessagesToBottom(behavior = "smooth") {
    const messageListElement = messageListRef.current;
    if (!messageListElement) return;

    const targetTop = Math.max(0, messageListElement.scrollHeight - messageListElement.clientHeight);
    messageListElement.scrollTo({ top: targetTop, behavior });
  }

  function handleStop() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsSending(false);
    }
  }

  async function handleSend(message) {
    if (!message || isSending) return;

    // CASO INVIO EMAIL TICKET
    if (isEscalating) {
      setIsSendingTicket(true);
      try {
        const lastBotWithConv = [...messages].reverse().find(m => m.conversationId);
        if (!lastBotWithConv) throw new Error("No conversation found");

        await sendTicket({
          conversationId: lastBotWithConv.conversationId,
          userEmail: message,
          language: locale
        });

        // RESET IMMEDIATO STATO ESCALATION
        setIsEscalating(false); 
        
        // Aggiungi messaggio conferma in chat
        const successMsg = createMessage("assistant", t.ticketSuccess);
        setMessages(prev => [...prev, successMsg]);
      } catch (error) {
        console.error("Ticket submission failed", error);
        alert(t.ticketError);
      } finally {
        setIsSendingTicket(false);
      }
      return;
    }

    // CASO MESSAGGIO CHAT NORMALE
    const userMessage = createMessage("user", message);
    const pendingMessage = createMessage("assistant", "", true);

    setMessages((prev) => [...prev, userMessage, pendingMessage]);
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
        persistedId: response.bot_message_id || null,
        conversationId: response.conversation_id || null,
        text: response.answer || t.unavailableAnswer,
        sources: normalizeSources(response.sources),
        isLoading: false,
      });
      
      patchMessage(userMessage.id, {
        persistedId: response.user_message_id || null,
        conversationId: response.conversation_id || null,
      });

      // AUTO-SWITCH LINGUA BASATO SUL MESSAGGIO
      if (response.language && response.language !== locale) {
        setLocale(response.language);
      }

      if (response.needs_email_for_ticket) {
        setIsEscalating(true);
      }
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
    if (!file || isSending) return;

    const isImage = file.type.startsWith("image/");
    const trimmedMessage = message.trim();
    if (isImage && !trimmedMessage) return;

    const objectUrl = URL.createObjectURL(file);
    const userMessage = createMessage("user", isImage ? trimmedMessage : "");
    
    if (isImage) {
      userMessage.messageType = "image";
      userMessage.image = objectUrl;
    } else {
      userMessage.messageType = "audio";
      userMessage.audio = {
        url: objectUrl,
        durationMs: metadata.durationMs || 0,
        waveform: metadata.waveform || null,
      };
    }

    const pendingMessage = createMessage("assistant", "", true);
    setMessages((prev) => [...prev, userMessage, pendingMessage]);
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
        persistedId: response.bot_message_id || null,
        conversationId: response.conversation_id || null,
        text: response.answer || t.unavailableAnswer,
        sources: normalizeSources(response.sources),
        isLoading: false,
      });
      patchMessage(userMessage.id, {
        persistedId: response.user_message_id || null,
        conversationId: response.conversation_id || null,
      });

      // AUTO-SWITCH LINGUA
      if (response.language && response.language !== locale) {
        setLocale(response.language);
      }

      if (response.needs_email_for_ticket) {
        setIsEscalating(true);
      }
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
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  }

  function handleLocaleChange(nextLocale) {
    setLocale(nextLocale);
  }

  async function handleFeedback(message, satisfied) {
    const mId = message.persistedId || message.id;
    if (!mId || message.isLoading || message.isError) return;

    patchMessage(message.id, { satisfaction: satisfied });

    try {
      await sendFeedback({ sessionId: sessionIdRef.current, messageId: mId, satisfied });
      
      // ESCALATION SU FEEDBACK NEGATIVO
      if (satisfied === false) {
        setIsEscalating(true);
        const apologyText = locale === "it" 
          ? "Mi dispiace che la risposta non sia stata soddisfacente. Se desideri, inserisci la tua email qui sotto per essere ricontattato da un operatore umano."
          : "I'm sorry the answer was not satisfactory. If you wish, enter your email below to be contacted by a human operator.";
          
        const apologyMsg = createMessage("assistant", apologyText);
        apologyMsg.conversationId = message.conversationId;
        setMessages(prev => [...prev, apologyMsg]);
      }
    } catch (e) {
      console.warn(e);
    }
  }

  function handleCancelEscalation() {
    setIsEscalating(false);
  }

  return (
    <div className="app-surface relative flex h-dvh max-h-dvh flex-col overflow-hidden" data-theme={theme}>
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
              isSending={isSending}
              messages={messages}
              listRef={messageListRef}
              suggestedQuestions={t.welcomeSuggestions || []}
              theme={theme}
              t={t}
              onContentLoad={() => scrollMessagesToBottom("smooth")}
              onFeedback={handleFeedback}
              onSuggestionClick={handleSend}
            />

            <ChatComposer
              isSending={isSending || isSendingTicket}
              t={t}
              onSend={handleSend}
              onFileSend={handleFileSend}
              onStop={handleStop}
              isEscalating={isEscalating}
              onCancelEscalation={handleCancelEscalation}
            />
          </section>
        </div>
      </main>
    </div>
  );
}

function getInitialTheme() {
  const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
  return saved || (window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ? "dark" : "light");
}

function createMessage(role, text, isLoading = false) {
  return {
    id: globalThis.crypto?.randomUUID?.() || Date.now().toString(),
    role,
    text,
    persistedId: null,
    conversationId: null,
    messageType: "text",
    satisfaction: null,
    isLoading,
    isError: false,
  };
}

function mapPersistedMessage(m) {
  return {
    id: m.id,
    persistedId: m.id,
    conversationId: m.conversation_id,
    role: m.role === "bot" ? "assistant" : "user",
    text: m.content,
    messageType: m.type || "text",
    satisfaction: m.satisfaction ?? null,
    isLoading: false,
    isError: false,
  };
}

function normalizeSources(s) {
  return Array.isArray(s) ? s.filter(x => x?.url).slice(0, 3) : [];
}
