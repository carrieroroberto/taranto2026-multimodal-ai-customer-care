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
  deleteConversationMessages,
  fetchConversationMessages,
  saveConversationMessage,
  sendChatMessage,
  sendMultimodalMessage,
  sendTicket,
  startConversation,
  updateMessageFeedback,
} from "../services/chatApi.js";
import { getOrCreateSessionId } from "../utils/session.js";
import { stopAudioPlayback } from "../utils/audioPlayback.js";
import { isSupportedSpeechLanguage, speakTextOnce } from "../utils/textToSpeech.js";

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
const TICKET_THINKING_MIN_MS = 450;

export function ChatPage() {
  const [messages, setMessages] = useState(initialMessages);
  const [isSending, setIsSending] = useState(false);
  const [isEscalating, setIsEscalating] = useState(false);
  const [isSendingTicket, setIsSendingTicket] = useState(false);
  const [theme, setTheme] = useState(() => getInitialTheme());
  const [locale, setLocale] = useState(() => getInitialLocale());
  const [composerResetSignal, setComposerResetSignal] = useState(0);
  const sessionIdRef = useRef(getOrCreateSessionId());
  const messageListRef = useRef(null);
  const abortControllerRef = useRef(null);
  const scrollAnimationFrameRef = useRef(null);
  const scrollScheduleFrameRef = useRef(null);
  const localeScrollTimeoutRef = useRef(null);
  const previousLocaleRef = useRef(locale);
  
  const [shouldScroll, setShouldScroll] = useState(true);
  
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

        const persistedMessages = restorePersistedEscalationState(
          payload.messages.map(mapPersistedMessage),
        );
        
        if (persistedMessages.length > 0) {
          setMessages((currentMessages) => {
            const onlyWelcome =
              currentMessages.length === 1 &&
              currentMessages[0]?.id === initialMessages[0].id;

            return onlyWelcome
              ? [initialMessages[0], ...persistedMessages]
              : currentMessages;
          });

          setIsEscalating(Boolean(findActiveEscalationFlowId(persistedMessages)));
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

    const didSwitchLocale = previousLocaleRef.current !== locale;
    previousLocaleRef.current = locale;
    if (didSwitchLocale && isMobileViewport()) {
      setShouldScroll(true);
      scheduleScrollMessagesToBottom("smooth");

      if (localeScrollTimeoutRef.current) {
        window.clearTimeout(localeScrollTimeoutRef.current);
      }
      localeScrollTimeoutRef.current = window.setTimeout(() => {
        localeScrollTimeoutRef.current = null;
        scheduleScrollMessagesToBottom("smooth");
      }, 140);
    }
  }, [locale, localeConfig.dir, localeConfig.htmlLang, t.pageTitle]);

  useEffect(() => {
    if (shouldScroll) {
      scheduleScrollMessagesToBottom("smooth");
    }
  }, [messages, shouldScroll]);

  useEffect(() => {
    return () => {
      if (scrollAnimationFrameRef.current) {
        window.cancelAnimationFrame(scrollAnimationFrameRef.current);
      }
      if (scrollScheduleFrameRef.current) {
        window.cancelAnimationFrame(scrollScheduleFrameRef.current);
      }
      if (localeScrollTimeoutRef.current) {
        window.clearTimeout(localeScrollTimeoutRef.current);
      }
    };
  }, []);

  function scrollMessagesToBottom(behavior = "smooth") {
    const messageListElement = messageListRef.current;
    if (!messageListElement) return;

    const targetTop = Math.max(0, messageListElement.scrollHeight - messageListElement.clientHeight);
    if (behavior !== "smooth") {
      messageListElement.scrollTo({ top: targetTop, behavior });
      return;
    }

    animateMessageScroll(messageListElement, targetTop);
  }

  function scheduleScrollMessagesToBottom(behavior = "smooth") {
    if (scrollScheduleFrameRef.current) {
      window.cancelAnimationFrame(scrollScheduleFrameRef.current);
    }

    scrollScheduleFrameRef.current = window.requestAnimationFrame(() => {
      scrollScheduleFrameRef.current = window.requestAnimationFrame(() => {
        scrollScheduleFrameRef.current = null;
        scrollMessagesToBottom(behavior);
      });
    });
  }

  function animateMessageScroll(messageListElement, targetTop) {
    if (scrollAnimationFrameRef.current) {
      window.cancelAnimationFrame(scrollAnimationFrameRef.current);
    }

    const startTop = messageListElement.scrollTop;
    const distance = targetTop - startTop;
    if (Math.abs(distance) < 1) {
      messageListElement.scrollTop = targetTop;
      return;
    }

    const durationMs = 260;
    const startedAt = performance.now();

    function step(now) {
      const progress = Math.min(1, (now - startedAt) / durationMs);
      const eased = 1 - Math.pow(1 - progress, 3);
      messageListElement.scrollTop = startTop + distance * eased;

      if (progress < 1) {
        scrollAnimationFrameRef.current = window.requestAnimationFrame(step);
      } else {
        scrollAnimationFrameRef.current = null;
        messageListElement.scrollTop = targetTop;
      }
    }

    scrollAnimationFrameRef.current = window.requestAnimationFrame(step);
  }

  function handleStop() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsSending(false);
      setIsSendingTicket(false);
    }
  }

  async function handleSend(message) {
    if (!message || isSending || isSendingTicket) return;
    stopAudioPlayback();
    setShouldScroll(true);
    const requestLocale = locale;

    // CASO INVIO EMAIL TICKET
    if (isEscalating) {
      const supportEmail = message.trim();
      const feedbackTarget = findTicketFeedbackTarget(messages);
      const escalationFlowFor = feedbackTarget?.id || findActiveEscalationFlowId(messages);
      const userMessage = createMessage("user", supportEmail);
      const pendingMessage = createMessage("assistant", "", true);
      userMessage.escalationFlowFor = escalationFlowFor;
      pendingMessage.escalationFlowFor = escalationFlowFor;
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setMessages((prev) => [...prev, userMessage, pendingMessage]);
      const persistedUserEmailPromise = persistConversationMessageQuietly(userMessage, {
        role: "user",
        text: supportEmail,
      });
      setIsSendingTicket(true);
      try {
        await wait(TICKET_THINKING_MIN_MS);

        if (controller.signal.aborted) {
          await persistedUserEmailPromise;
          const stoppedText = t.stoppedResponse;
          patchMessage(pendingMessage.id, {
            text: stoppedText,
            isLoading: false,
            isError: true,
          });
          await persistConversationMessageQuietly(pendingMessage, {
            role: "assistant",
            text: stoppedText,
          });
          return;
        }

        if (!isValidEmail(supportEmail)) {
          await persistedUserEmailPromise;
          const invalidEmailText = t.ticketInvalidEmail || "Inserisci un indirizzo email valido.";
          patchMessage(pendingMessage.id, {
            text: invalidEmailText,
            isLoading: false,
            isError: true,
            feedbackDisabled: true,
          });
          await persistConversationMessageQuietly(pendingMessage, {
            role: "assistant",
            text: invalidEmailText,
          });
          return;
        }

        const lastBotWithConv = [...messages].reverse().find(m => m.conversationId);
        const conversationId = lastBotWithConv?.conversationId || sessionIdRef.current;
        const escalatedMessageId = feedbackTarget?.persistedId || null;

        const ticketResponse = await sendTicket({
          conversationId,
          escalatedMessageId,
          userEmail: supportEmail,
          language: requestLocale,
          signal: controller.signal,
        });

        await persistedUserEmailPromise;

        // RESET IMMEDIATO STATO ESCALATION
        setIsEscalating(false); 
        
        const successText = ticketResponse.message;
        if (!successText) {
          throw new Error(t.ticketError || "Impossibile inviare il ticket.");
        }

        // Aggiungi messaggio conferma in chat usando il messaggio dal backend
        patchMessage(pendingMessage.id, {
          text: successText,
          isLoading: false,
          isError: false,
          conversationId: ticketResponse.ticket?.conversation_id || conversationId,
          feedbackDisabled: true,
        });
        await persistConversationMessageQuietly(pendingMessage, {
          role: "assistant",
          text: successText,
        });
        if (feedbackTarget) {
          patchMessage(feedbackTarget.id, { feedbackLocked: true });
        }
      } catch (error) {
        console.error("Ticket submission failed", error);
        await persistedUserEmailPromise;
        const errorText =
          error.name === "AbortError"
            ? t.stoppedResponse
            : getTicketErrorMessage(error, t);
        patchMessage(pendingMessage.id, {
          text: errorText,
          isLoading: false,
          isError: true,
          feedbackDisabled: true,
        });
        await persistConversationMessageQuietly(pendingMessage, {
          role: "assistant",
          text: errorText,
        });
      } finally {
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
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
        language: requestLocale,
        signal: controller.signal
      });

      patchMessage(pendingMessage.id, {
        persistedId: response.bot_message_id || null,
        conversationId: response.conversation_id || null,
        createdAt: response.bot_created_at || pendingMessage.createdAt,
        feedbackDisabled: Boolean(response.should_escalate || response.needs_email_for_ticket),
        escalationFlowFor: response.needs_email_for_ticket ? pendingMessage.id : null,
        text: response.answer || t.unavailableAnswer,
        sources: normalizeSources(response.sources),
        isLoading: false,
      });
      
      patchMessage(userMessage.id, {
        persistedId: response.user_message_id || null,
        conversationId: response.conversation_id || null,
        createdAt: response.user_created_at || userMessage.createdAt,
      });

      if (response.language_detected && response.language && response.language !== locale) {
        setLocale(response.language);
      }

      if (response.needs_email_for_ticket) {
        setIsEscalating(true);
      }
    } catch (error) {
      if (error.name === "AbortError") {
        patchMessage(pendingMessage.id, {
          text: t.stoppedResponse,
          isLoading: false,
          isError: true,
        });
        return;
      }
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
    stopAudioPlayback();

    const isImage = file.type.startsWith("image/");
    const trimmedMessage = message.trim();
    if (isImage && !trimmedMessage) return;

    const objectUrl = URL.createObjectURL(file);
    const userMessage = createMessage("user", isImage ? trimmedMessage : "");
    const requestLocale = locale;
    
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
        language: requestLocale,
        signal: controller.signal
      });
      const answerText = response.answer || t.unavailableAnswer;
      const responseLanguage = isSupportedSpeechLanguage(response.language)
        ? response.language
        : requestLocale;

      patchMessage(pendingMessage.id, {
        persistedId: response.bot_message_id || null,
        conversationId: response.conversation_id || null,
        createdAt: response.bot_created_at || pendingMessage.createdAt,
        feedbackDisabled: Boolean(response.should_escalate || response.needs_email_for_ticket),
        escalationFlowFor: response.needs_email_for_ticket ? pendingMessage.id : null,
        text: answerText,
        sources: normalizeSources(response.sources),
        isLoading: false,
      });
      patchMessage(userMessage.id, {
        persistedId: response.user_message_id || null,
        conversationId: response.conversation_id || null,
        createdAt: response.user_created_at || userMessage.createdAt,
      });

      if (response.language_detected && response.language && response.language !== locale) {
        setLocale(response.language);
      }

      if (response.needs_email_for_ticket) {
        setIsEscalating(true);
      }

      if (!isImage) {
        speakTextOnce(answerText, responseLanguage);
      }
    } catch (error) {
      if (error.name === "AbortError") {
        patchMessage(pendingMessage.id, {
          text: t.stoppedResponse,
          isLoading: false,
          isError: true,
        });
        return;
      }
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

  async function persistConversationMessage(message, overrides = {}) {
    const role = overrides.role || message.role;
    const text = overrides.text ?? message.text ?? "";
    const savedMessage = await saveConversationMessage({
      sessionId: sessionIdRef.current,
      role: role === "assistant" ? "bot" : "user",
      content: text,
      messageType: overrides.messageType || message.messageType || "text",
      mediaUrl: overrides.mediaUrl || null,
      sources: overrides.sources || null,
    });

    patchMessage(message.id, {
      persistedId: savedMessage.id || null,
      conversationId: savedMessage.conversation_id || null,
      createdAt: savedMessage.created_at || message.createdAt,
    });

    return savedMessage;
  }

  async function persistConversationMessageQuietly(message, overrides = {}) {
    try {
      return await persistConversationMessage(message, overrides);
    } catch (error) {
      console.warn("Unable to persist conversation message", error);
      return null;
    }
  }

  async function deletePersistedEscalationMessages(escalationFlowId) {
    if (!escalationFlowId) {
      return;
    }

    const messageIds = messages
      .filter((message) => isEscalationFlowMessage(message, escalationFlowId))
      .map((message) => message.persistedId)
      .filter(Boolean);

    if (!messageIds.length) {
      return;
    }

    try {
      await deleteConversationMessages({
        sessionId: sessionIdRef.current,
        messageIds,
      });
    } catch (error) {
      console.warn("Unable to delete escalation messages", error);
    }
  }

  function handleThemeToggle() {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  }

  function handleLocaleChange(nextLocale) {
    setLocale(nextLocale);
  }

  async function handleFeedback(message, satisfied) {
    const messageId = message.persistedId || message.id;
    const activeEscalationFlowId = findActiveEscalationFlowId(messages);
    const isActiveEscalationTarget =
      isEscalating && activeEscalationFlowId === message.id;
    const nextSatisfaction =
      message.satisfaction === satisfied ? null : satisfied;
    if (
      !messageId ||
      message.isLoading ||
      message.isError ||
      isSending ||
      isSendingTicket ||
      (isEscalating && !isActiveEscalationTarget) ||
      message.feedbackLocked ||
      message.satisfaction === nextSatisfaction
    ) {
      return;
    }

    // Disabilitiamo lo scroll automatico prima di aggiornare i messaggi per evitare sbalzi
    setShouldScroll(false);

    const previousSatisfaction = message.satisfaction;
    patchMessage(message.id, { satisfaction: nextSatisfaction });

    try {
      await updateMessageFeedback({
        messageId,
        satisfaction: nextSatisfaction,
      });
      
      // ESCALATION SU FEEDBACK NEGATIVO - Solo se è l'ultimo messaggio bot
      if (nextSatisfaction === false) {
        setIsEscalating(true);
        const apologyText =
          t.feedbackSupportPrompt ||
          "Mi dispiace che la risposta non sia stata soddisfacente. Se desideri, scrivi la tua email nella casella di testo per essere ricontattato da un operatore umano.";
          
        const apologyMsg = createMessage("assistant", apologyText);
        apologyMsg.conversationId = message.conversationId;
        apologyMsg.feedbackSupportFor = message.id;
        apologyMsg.escalationFlowFor = message.id;
        apologyMsg.feedbackDisabled = true;
        setMessages(prev => [...prev, apologyMsg]);
        await persistConversationMessageQuietly(apologyMsg, {
          role: "assistant",
          text: apologyText,
        });
        // Se scatta l'escalation, allora torniamo a scrollare verso il basso
        setShouldScroll(true);
      } else if (previousSatisfaction === false) {
        // Se l'utente cambia da pollice giù a pollice su, chiudi l'escalation se era legata a questo messaggio
        // Ma NON chiudere se l'escalation è stata innescata da un altro motivo (es. richiesta esplicita)
        if (messages.find(m => m.feedbackSupportFor === message.id)) {
           await deletePersistedEscalationMessages(message.id);
           setIsEscalating(false);
           setShouldScroll(true);
           setComposerResetSignal((value) => value + 1);
           setMessages(prev =>
             prev.filter(existingMessage => !isEscalationFlowMessage(existingMessage, message.id)),
           );
        }
      }
    } catch (e) {
      console.warn(e);
      patchMessage(message.id, { satisfaction: previousSatisfaction });
    }
  }

  async function handleCancelEscalation() {
    const feedbackTarget = findTicketFeedbackTarget(messages);
    const escalationFlowId = feedbackTarget?.id || findActiveEscalationFlowId(messages);

    setIsEscalating(false);
    setShouldScroll(true);

    if (!escalationFlowId) {
      scheduleScrollMessagesToBottom("smooth");
      return;
    }

    const targetMessageId = feedbackTarget?.persistedId || feedbackTarget?.id;
    await deletePersistedEscalationMessages(escalationFlowId);

    setMessages(prev =>
      prev
        .filter(existingMessage => !isEscalationFlowMessage(existingMessage, escalationFlowId))
        .map(existingMessage =>
          feedbackTarget && existingMessage.id === feedbackTarget.id
            ? { ...existingMessage, satisfaction: null }
            : existingMessage,
        ),
    );

    if (!targetMessageId) {
      return;
    }

    try {
      await updateMessageFeedback({ messageId: targetMessageId, satisfaction: null });
    } catch (error) {
      console.warn(error);
    }
  }

  const activeEscalationFlowId = findActiveEscalationFlowId(messages);
  const messageInteractionsDisabled = isSending || isSendingTicket || isEscalating;

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
              feedbackCanCorrectNegative={true}
              feedbackDisabled={messageInteractionsDisabled}
              activeEscalationFlowId={activeEscalationFlowId}
              allowActiveEscalationFeedback={
                isEscalating && !isSending && !isSendingTicket
              }
              isSending={messageInteractionsDisabled}
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
              suggestedQuestions={t.welcomeSuggestions || []}
              theme={theme}
              t={t}
              onContentLoad={() => scrollMessagesToBottom("smooth")}
              onFeedback={handleFeedback}
              onSuggestionClick={handleSend}
            />

            <ChatComposer
              isSending={isSending || isSendingTicket}
              locale={locale}
              t={t}
              onSend={handleSend}
              onFileSend={handleFileSend}
              onStop={handleStop}
              isEscalating={isEscalating}
              onCancelEscalation={handleCancelEscalation}
              resetDraftSignal={composerResetSignal}
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

function isMobileViewport() {
  if (typeof window === "undefined") {
    return false;
  }
  return window.matchMedia?.("(max-width: 767px)")?.matches ?? false;
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function createMessage(role, text, isLoading = false) {
  return {
    id: globalThis.crypto?.randomUUID?.() || Date.now().toString(),
    role,
    text,
    persistedId: null,
    conversationId: null,
    createdAt: new Date().toISOString(),
    messageType: "text",
    satisfaction: null,
    feedbackLocked: false,
    escalationFlowFor: null,
    isLoading,
    isError: false,
  };
}

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || "").trim());
}

function getTicketErrorMessage(error, t) {
  const message = String(error?.message || "");
  if (/invalid email/i.test(message)) {
    return t.ticketInvalidEmail;
  }
  return t.ticketError || message || "Impossibile inviare il ticket.";
}

function mapPersistedMessage(m) {
  let text = m.content || "";
  let image = undefined;
  let audio = undefined;
  
  // Se è un'immagine ricaricata dal DB, estraiamo l'URL se presente e puliamo il testo
  if (m.type === "image") {
    image = normalizePersistedMediaUrl(m.media_url);
    // Estrai l'URL dell'immagine se è stato salvato
    const urlMatch = text.match(/\[IMAGE_URL:(.*?)\]/);
    if (!image && urlMatch) {
      image = urlMatch[1];
    }
    if (urlMatch) {
      // Rimuovi il tag URL dal testo testuale
      text = text.replace(urlMatch[0], "").trim();
    }

    const userPrompt = stripHiddenMultimodalText(text)
      .replace("Immagine inviata dall'utente.", "")
      .trim();
    text = userPrompt;
    
    // Se per vecchi messaggi non abbiamo salvato l'immagine, mettiamo un placeholder testuale
    if (!image && !text) {
      text = "📸 [Immagine inviata]";
    }
  } else if (m.type === "audio") {
    const persistedAudioUrl = normalizePersistedMediaUrl(m.media_url);
    if (persistedAudioUrl) {
      audio = { url: persistedAudioUrl };
    }
    const urlMatch = text.match(/\[AUDIO_URL:(.*?)\]/);
    if (!audio && urlMatch) {
      audio = { url: urlMatch[1] };
    }
    if (urlMatch) {
      text = text.replace(urlMatch[0], "").trim();
    }
    text = "";
    if (text === "[AUDIO_INCOMPRENSIBILE]") {
      text = "🎤 [Audio non trascritto]";
    }
  }

  return {
    id: m.id,
    persistedId: m.id,
    conversationId: m.conversation_id,
    role: m.role === "bot" ? "assistant" : "user",
    text,
    image,
    audio,
    messageType: m.type || "text",
    sources: normalizeSources(m.sources),
    satisfaction: m.satisfaction ?? null,
    feedbackLocked: Boolean(m.ticket_opened),
    feedbackDisabled: isTicketServiceText(text),
    createdAt: m.created_at || null,
    isLoading: false,
    isError: isTicketErrorText(text),
  };
}

function restorePersistedEscalationState(messages) {
  let latestFeedbackTarget = null;
  let activeFlowId = null;

  return messages.map((message) => {
    const nextMessage = { ...message };

    if (
      message.role === "assistant" &&
      message.persistedId &&
      message.satisfaction === false &&
      !message.feedbackLocked &&
      !isTicketServiceText(message.text)
    ) {
      latestFeedbackTarget = message;
    }

    if (
      message.role === "assistant" &&
      isEscalationText(message.text) &&
      latestFeedbackTarget
    ) {
      activeFlowId = latestFeedbackTarget.id;
      nextMessage.feedbackSupportFor = activeFlowId;
      nextMessage.escalationFlowFor = activeFlowId;
      nextMessage.feedbackDisabled = true;
      return nextMessage;
    }

    if (activeFlowId && message.id !== activeFlowId) {
      nextMessage.escalationFlowFor = activeFlowId;
      if (message.role === "assistant") {
        nextMessage.feedbackDisabled = true;
      }
    }

    return nextMessage;
  });
}

function normalizePersistedMediaUrl(value) {
  const url = String(value || "").trim();
  return url || null;
}

function stripHiddenMultimodalText(value) {
  return String(value || "")
    .split("\nDescrizione immagine:")[0]
    .split("\nTesto estratto dall'immagine:")[0]
    .split("\nAnalisi immagine:")[0]
    .trim();
}

function findTicketFeedbackTarget(messages) {
  const supportPrompt = [...messages]
    .reverse()
    .find((message) => message.feedbackSupportFor);

  if (!supportPrompt) {
    return null;
  }

  return (
    messages.find((message) => message.id === supportPrompt.feedbackSupportFor) ||
    null
  );
}

function findActiveEscalationFlowId(messages) {
  const activeMessage = [...messages]
    .reverse()
    .find((message) => message.escalationFlowFor);
  return activeMessage?.escalationFlowFor || null;
}

function isEscalationFlowMessage(message, flowId) {
  return (
    message.escalationFlowFor === flowId ||
    message.feedbackSupportFor === flowId ||
    message.id === flowId && message.feedbackDisabled && isEscalationText(message.text)
  );
}

function normalizeSources(s) {
  return Array.isArray(s) ? s.filter(x => x?.url).slice(0, 3) : [];
}

function isEscalationText(text) {
  const normalized = normalizeServiceText(text);
  return (
    normalized.includes("inserisci l'email") ||
    normalized.includes("scrivi la tua email") ||
    normalized.includes("enter your email") ||
    normalized.includes("write your email") ||
    normalized.includes("escribe tu correo") ||
    normalized.includes("ecrivez votre adresse e-mail") ||
    normalized.includes("ecrivez votre adresse e mail") ||
    normalized.includes("ingresa tu correo") ||
    normalized.includes("saisissez votre e-mail")
  );
}

function isTicketServiceText(text) {
  const normalized = normalizeServiceText(text);
  return (
    isEscalationText(text) ||
    normalized.includes("inserisci un indirizzo email valido") ||
    normalized.includes("enter a valid email address") ||
    normalized.includes("introduce una direccion de correo valida") ||
    normalized.includes("saisissez une adresse e-mail valide") ||
    normalized.includes("أدخل عنوان بريد إلكتروني صالح") ||
    normalized.includes("richiesta inviata con successo") ||
    normalized.includes("request sent successfully") ||
    normalized.includes("solicitud enviada correctamente") ||
    normalized.includes("demande envoyee avec succes") ||
    normalized.includes("تم إرسال الطلب بنجاح") ||
    normalized.includes("impossibile inviare il ticket") ||
    normalized.includes("failed to send ticket") ||
    normalized.includes("error al enviar la solicitud") ||
    normalized.includes("echec de l'envoi de la demande") ||
    normalized.includes("فشل إرسال الطلب") ||
    normalized.includes("richiesta interrotta") ||
    normalized.includes("request stopped") ||
    normalized.includes("solicitud interrumpida") ||
    normalized.includes("reponse interrompue") ||
    normalized.includes("تم إيقاف الطلب")
  );
}

function isTicketErrorText(text) {
  const normalized = normalizeServiceText(text);
  return (
    normalized.includes("inserisci un indirizzo email valido") ||
    normalized.includes("enter a valid email address") ||
    normalized.includes("introduce una direccion de correo valida") ||
    normalized.includes("saisissez une adresse e-mail valide") ||
    normalized.includes("أدخل عنوان بريد إلكتروني صالح") ||
    normalized.includes("impossibile inviare il ticket") ||
    normalized.includes("failed to send ticket") ||
    normalized.includes("error al enviar la solicitud") ||
    normalized.includes("echec de l'envoi de la demande") ||
    normalized.includes("فشل إرسال الطلب") ||
    normalized.includes("richiesta interrotta") ||
    normalized.includes("request stopped") ||
    normalized.includes("solicitud interrumpida") ||
    normalized.includes("reponse interrompue") ||
    normalized.includes("تم إيقاف الطلب")
  );
}

function normalizeServiceText(text) {
  return String(text || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}
