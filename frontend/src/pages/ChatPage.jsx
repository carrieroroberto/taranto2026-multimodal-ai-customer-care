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
    if (shouldScroll) {
      scrollMessagesToBottom("smooth");
    }
  }, [messages, shouldScroll]);

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
    setShouldScroll(true);
    const detectedLocale = detectMessageLocale(message, locale);
    if (detectedLocale !== locale) {
      setLocale(detectedLocale);
    }

    // CASO INVIO EMAIL TICKET
    if (isEscalating) {
      setIsSendingTicket(true);
      try {
        const lastBotWithConv = [...messages].reverse().find(m => m.conversationId);
        if (!lastBotWithConv) throw new Error("No conversation found");

        const ticketResponse = await sendTicket({
          conversationId: lastBotWithConv.conversationId,
          userEmail: message,
          language: detectedLocale
        });

        // RESET IMMEDIATO STATO ESCALATION
        setIsEscalating(false); 
        
        // Aggiungi messaggio conferma in chat usando il messaggio dal backend
        const successText = ticketResponse.message || `${t.ticketSuccess} ${message}`;
        const successMsg = createMessage("assistant", successText);
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
        language: detectedLocale,
        signal: controller.signal
      });

      patchMessage(pendingMessage.id, {
        persistedId: response.bot_message_id || null,
        conversationId: response.conversation_id || null,
        feedbackDisabled: Boolean(response.should_escalate || response.needs_email_for_ticket),
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

      // TRIGGER ESCALATION SE IL BOT NON SA RISPONDERE O SE RICHIESTO DAL BACKEND
      const isRefusal = isRefusalText(response.answer, t.unavailableAnswer);
      if (response.needs_email_for_ticket || isRefusal) {
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
    const detectedLocale = trimmedMessage ? detectMessageLocale(trimmedMessage, locale) : locale;
    if (detectedLocale !== locale) {
      setLocale(detectedLocale);
    }
    
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
        language: detectedLocale,
        signal: controller.signal
      });

      patchMessage(pendingMessage.id, {
        persistedId: response.bot_message_id || null,
        conversationId: response.conversation_id || null,
        feedbackDisabled: Boolean(response.should_escalate || response.needs_email_for_ticket),
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

  function detectMessageLocale(text, fallback = "it") {
    const normalized = String(text || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();

    if (/[\u0600-\u06ff]/.test(text)) return "ar";

    const tokens = new Set(normalized.match(/[a-z0-9]+/g) || []);
    const scores = {
      it: scoreLanguage(tokens, normalized, [
        "ciao", "salve", "buongiorno", "buonasera", "voglio", "vorrei", "posso",
        "puoi", "potresti", "devo", "serve", "aiuto", "dove", "quando", "quanto",
        "quale", "quali", "chi", "che", "cosa", "come", "trovo", "trova", "sono", "sei",
        "perche", "un", "una", "il", "lo", "la", "tabella", "lingua", "messaggio", "risposta", "sempre",
        "dovrebbe", "selezionata", "risolvi", "problema", "biglietti",
        "operatore", "parlare", "mandato", "inviato", "appena", "italiano",
      ]),
      en: scoreLanguage(tokens, normalized, [
        "hello", "hi", "please", "want", "would", "could", "can", "where",
        "when", "what", "which", "who", "how", "why", "is", "are", "ticket", "tickets", "operator",
        "speak", "talk", "help", "english",
      ]),
      es: scoreLanguage(tokens, normalized, [
        "hola", "quiero", "quisiera", "puedo", "puedes", "donde", "cuando",
        "que", "quien", "quienes", "cual", "como", "es", "son", "entradas", "operador", "hablar", "espanol",
      ]),
      fr: scoreLanguage(tokens, normalized, [
        "bonjour", "salut", "veux", "voudrais", "peux", "pouvez", "quand",
        "quoi", "qui", "quel", "quelle", "comment", "pourquoi", "est", "sont", "billets", "operateur", "parler",
        "francais",
      ]),
    };

    const [localeEntry, score] = Object.entries(scores).sort((a, b) => b[1] - a[1])[0];
    return score > 0 ? localeEntry : fallback;
  }

  function scoreLanguage(tokens, normalized, markers) {
    return markers.reduce((score, marker) => {
      if (marker.includes(" ")) {
        return normalized.includes(marker) ? score + 2 : score;
      }
      return tokens.has(marker) ? score + 1 : score;
    }, 0);
  }

  function handleThemeToggle() {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  }

  function handleLocaleChange(nextLocale) {
    setLocale(nextLocale);
  }

  async function handleFeedback(message, satisfied) {
    const mId = message.persistedId || message.id;
    if (
      !mId ||
      message.isLoading ||
      message.isError ||
      isSending ||
      isSendingTicket ||
      message.satisfaction === satisfied
    ) {
      return;
    }

    // Disabilitiamo lo scroll automatico prima di aggiornare i messaggi per evitare sbalzi
    setShouldScroll(false);

    const previousSatisfaction = message.satisfaction;
    patchMessage(message.id, { satisfaction: satisfied });

    try {
      await sendFeedback({ sessionId: sessionIdRef.current, messageId: mId, satisfied });
      
      // ESCALATION SU FEEDBACK NEGATIVO - Solo se è l'ultimo messaggio bot
      const assistantMessages = messages.filter(m => m.role === "assistant" && !m.translationKey);
      const isLatestBotMessage = assistantMessages.length > 0 && assistantMessages[assistantMessages.length - 1].id === message.id;

      if (satisfied === false && isLatestBotMessage) {
        setIsEscalating(true);
        const apologyText = locale === "it" 
          ? "Mi dispiace che la risposta non sia stata soddisfacente. Se desideri, inserisci la tua email qui sotto per essere ricontattato da un operatore umano."
          : "I'm sorry the answer was not satisfactory. If you wish, enter your email below to be contacted by a human operator.";
          
        const apologyMsg = createMessage("assistant", apologyText);
        apologyMsg.conversationId = message.conversationId;
        apologyMsg.feedbackSupportFor = message.id;
        setMessages(prev => [...prev, apologyMsg]);
        // Se scatta l'escalation, allora torniamo a scrollare verso il basso
        setShouldScroll(true);
      } else if (previousSatisfaction === false && satisfied === true) {
        // Se l'utente cambia da pollice giù a pollice su, chiudi l'escalation se era legata a questo messaggio
        // Ma NON chiudere se l'escalation è stata innescata da un altro motivo (es. richiesta esplicita)
        if (messages.find(m => m.feedbackSupportFor === message.id)) {
           setIsEscalating(false);
           setMessages(prev =>
             prev.filter(existingMessage => existingMessage.feedbackSupportFor !== message.id),
           );
        }
      }
    } catch (e) {
      console.warn(e);
      patchMessage(message.id, { satisfaction: previousSatisfaction });
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
              feedbackCanCorrectNegative={true}
              feedbackDisabled={isSending || isSendingTicket}
              isSending={isSending || isSendingTicket}
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
  let text = m.content || "";
  let image = undefined;
  
  // Se è un'immagine ricaricata dal DB, estraiamo l'URL se presente e puliamo il testo
  if (m.type === "image") {
    // Estrai l'URL dell'immagine se è stato salvato
    const urlMatch = text.match(/\[IMAGE_URL:(.*?)\]/);
    if (urlMatch) {
      image = urlMatch[1];
      // Rimuovi il tag URL dal testo testuale
      text = text.replace(urlMatch[0], "").trim();
    }

    const originalMessageMatch = text.split("\nDescrizione immagine:")[0];
    const userPrompt = originalMessageMatch.replace("Immagine inviata dall'utente.", "").trim();
    text = userPrompt;
    
    // Se per vecchi messaggi non abbiamo salvato l'immagine, mettiamo un placeholder testuale
    if (!image && !text) {
      text = "📸 [Immagine inviata]";
    }
  }

  return {
    id: m.id,
    persistedId: m.id,
    conversationId: m.conversation_id,
    role: m.role === "bot" ? "assistant" : "user",
    text,
    image,
    messageType: m.type || "text",
    satisfaction: m.satisfaction ?? null,
    feedbackDisabled: isEscalationText(text),
    isLoading: false,
    isError: false,
  };
}

function isRefusalText(text, fallbackText) {
  if (!text) return false;
  if (text === fallbackText) return true;
  
  const normalized = String(text)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
    
  return (
    normalized.includes("non ho un dato abbastanza preciso") ||
    normalized.includes("preparare una richiesta per un operatore") ||
    normalized.includes("non ho informazioni") ||
    normalized.includes("canale ufficiale") ||
    normalized.includes("non sono in grado di rispondere") ||
    normalized.includes("i don't have enough precise data") ||
    normalized.includes("prepare a request for an operator")
  );
}

function normalizeSources(s) {
  return Array.isArray(s) ? s.filter(x => x?.url).slice(0, 3) : [];
}

function isEscalationText(text) {
  const normalized = String(text || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
  return (
    normalized.includes("non ho un dato abbastanza preciso") ||
    normalized.includes("preparare una richiesta per un operatore") ||
    normalized.includes("inserisci l'email") ||
    normalized.includes("enter your email") ||
    normalized.includes("ingresa tu correo") ||
    normalized.includes("saisissez votre e-mail")
  );
}

function detectMessageLocale(text, fallback = "it") {
  const normalized = String(text || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();

  if (/[\u0600-\u06ff]/.test(text)) return "ar";

  const tokens = new Set(normalized.match(/[a-z0-9]+/g) || []);
  const scores = {
    it: scoreLanguage(tokens, normalized, [
      "ciao", "salve", "buongiorno", "buonasera", "voglio", "vorrei", "posso",
      "puoi", "potresti", "devo", "serve", "aiuto", "dove", "quando", "quanto",
      "quale", "quali", "chi", "che", "cosa", "come", "trovo", "trova", "sono", "sei",
      "perche", "un", "una", "il", "lo", "la", "tabella", "lingua", "messaggio", "risposta", "sempre",
      "dovrebbe", "selezionata", "risolvi", "problema", "biglietti",
      "operatore", "parlare", "mandato", "inviato", "appena", "italiano",
    ]),
    en: scoreLanguage(tokens, normalized, [
      "hello", "hi", "please", "want", "would", "could", "can", "where",
      "when", "what", "which", "who", "how", "why", "is", "are", "ticket", "tickets", "operator",
      "speak", "talk", "help", "english",
    ]),
    es: scoreLanguage(tokens, normalized, [
      "hola", "quiero", "quisiera", "puedo", "puedes", "donde", "cuando",
      "que", "quien", "quienes", "cual", "como", "es", "son", "entradas", "operador", "hablar", "espanol",
    ]),
    fr: scoreLanguage(tokens, normalized, [
      "bonjour", "salut", "veux", "voudrais", "peux", "pouvez", "quand",
      "quoi", "qui", "quel", "quelle", "comment", "pourquoi", "est", "sont", "billets", "operateur", "parler",
      "francais",
    ]),
  };

  const [locale, score] = Object.entries(scores).sort((a, b) => b[1] - a[1])[0];
  return score > 0 ? locale : fallback;
}

function scoreLanguage(tokens, normalized, markers) {
  return markers.reduce((score, marker) => {
    if (marker.includes(" ")) {
      return normalized.includes(marker) ? score + 2 : score;
    }
    return tokens.has(marker) ? score + 1 : score;
  }, 0);
}
