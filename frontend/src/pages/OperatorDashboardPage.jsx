import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import { mainLogoUrl } from "../assets/index.js";
import { DecorativeBackground } from "../components/DecorativeBackground.jsx";
import { ThemeToggle } from "../components/ThemeToggle.jsx";
import {
  clearOperatorSession,
  fetchOperatorProfile,
  fetchTicketDetail,
  fetchTickets,
  generateTicketEmailDraft,
  getStoredOperatorSession,
  loginOperator,
  logoutOperator,
  storeOperatorSession,
  translateTicketConversation,
  updateTicketStatus,
} from "../services/operatorApi.js";

const PRIORITY_ORDER = { alta: 0, media: 1, bassa: 2 };
const THEME_STORAGE_KEY = "tarai-theme";
const TICKET_VIEW_STORAGE_KEY = "tarai-operator-ticket-view";
const themeLabels = {
  themeToLight: "Passa alla modalita chiara",
  themeToDark: "Passa alla modalita scura",
};

export function OperatorDashboardPage() {
  const [{ token, operator }, setSession] = useState(() => getStoredOperatorSession());
  const [tickets, setTickets] = useState([]);
  const [selectedTicketId, setSelectedTicketId] = useState(null);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [translatedMessages, setTranslatedMessages] = useState(null);
  const [statusFilter, setStatusFilter] = useState("aperto");
  const [sortBy, setSortBy] = useState("date");
  const [ticketView, setTicketView] = useState(() => getInitialTicketView());
  const [isMobileViewport, setIsMobileViewport] = useState(() => isOperatorMobileViewport());
  const [isLoadingTickets, setIsLoadingTickets] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [isDraftingEmail, setIsDraftingEmail] = useState(false);
  const [theme, setTheme] = useState(() => getInitialTheme());
  const [error, setError] = useState("");

  const isAuthenticated = Boolean(token);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.lang = "it";
    document.documentElement.dir = "ltr";
    document.title = "TarAI | Dashboard Operatore";
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);

    const themeColor = theme === "dark" ? "#061826" : "#06477a";
    document
      .querySelectorAll("meta[name='theme-color']")
      .forEach((metaElement) => {
        metaElement.setAttribute("content", themeColor);
      });
  }, [theme]);

  useEffect(() => {
    if (!token) {
      return;
    }

    let isCancelled = false;
    async function hydrateOperator() {
      try {
        const profile = await fetchOperatorProfile(token);
        if (!isCancelled) {
          updateSession(token, profile);
        }
      } catch (_error) {
        if (!isCancelled) {
          handleSessionExpired();
        }
      }
    }
    hydrateOperator();

    return () => {
      isCancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!token) {
      return;
    }
    loadTickets();
  }, [token, statusFilter]);

  useEffect(() => {
    window.localStorage.setItem(TICKET_VIEW_STORAGE_KEY, ticketView);
  }, [ticketView]);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 640px)");
    const handleViewportChange = () => setIsMobileViewport(mediaQuery.matches);

    handleViewportChange();
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", handleViewportChange);
    } else {
      mediaQuery.addListener(handleViewportChange);
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener("change", handleViewportChange);
      } else {
        mediaQuery.removeListener(handleViewportChange);
      }
    };
  }, []);

  async function loadTickets() {
    setIsLoadingTickets(true);
    setError("");
    try {
      const data = await fetchTickets(token, { status: statusFilter });
      setTickets(Array.isArray(data) ? data : []);
    } catch (loadError) {
      if (isUnauthorized(loadError)) {
        handleSessionExpired();
      } else {
        setError("Impossibile caricare i ticket.");
      }
    } finally {
      setIsLoadingTickets(false);
    }
  }

  useEffect(() => {
    if (!token || !selectedTicketId) {
      setSelectedTicket(null);
      return;
    }

    let isCancelled = false;
    async function loadDetail() {
      setIsLoadingDetail(true);
      setTranslatedMessages(null);
      setError("");
      try {
        const detail = await fetchTicketDetail(token, selectedTicketId);
        if (!isCancelled) {
          setSelectedTicket(detail);
        }
      } catch (detailError) {
        if (isUnauthorized(detailError)) {
          handleSessionExpired();
        } else if (!isCancelled) {
          setError("Impossibile caricare il dettaglio del ticket.");
        }
      } finally {
        if (!isCancelled) {
          setIsLoadingDetail(false);
        }
      }
    }

    loadDetail();
    return () => {
      isCancelled = true;
    };
  }, [token, selectedTicketId]);

  const sortedTickets = useMemo(() => {
    return [...tickets].sort((a, b) => {
      if (sortBy === "domain") {
        return String(a.domain || "").localeCompare(String(b.domain || ""), "it");
      }
      if (sortBy === "status") {
        return String(a.status || "").localeCompare(String(b.status || ""), "it");
      }
      if (sortBy === "date") {
        return dateRank(b.created_at) - dateRank(a.created_at);
      }
      return priorityRank(a.priority) - priorityRank(b.priority);
    });
  }, [tickets, sortBy]);
  const effectiveTicketView = isMobileViewport ? "list" : ticketView;

  function updateSession(nextToken, nextOperator) {
    storeOperatorSession({ token: nextToken, operator: nextOperator });
    setSession({ token: nextToken, operator: nextOperator });
  }

  function handleSessionExpired() {
    clearOperatorSession();
    setSession({ token: null, operator: null });
    setTickets([]);
    closeTicketModal();
    setError("Sessione operatore scaduta. Effettua di nuovo l'accesso.");
  }

  async function handleLogin(credentials) {
    setError("");
    const session = await loginOperator(credentials);
    updateSession(session.token, session.operator);
  }

  async function handleLogout() {
    try {
      if (token) {
        await logoutOperator(token);
      }
    } catch (_error) {
      // Il logout locale resta sufficiente per uscire dalla dashboard.
    }
    clearOperatorSession();
    setSession({ token: null, operator: null });
    setTickets([]);
    closeTicketModal();
  }

  function handleThemeToggle() {
    setTheme((currentTheme) => (currentTheme === "dark" ? "light" : "dark"));
  }

  function openTicket(ticketId) {
    setSelectedTicketId(ticketId);
  }

  function closeTicketModal() {
    setSelectedTicketId(null);
    setSelectedTicket(null);
    setTranslatedMessages(null);
  }

  async function handleToggleStatus() {
    if (!selectedTicket) {
      return;
    }

    const nextStatus = selectedTicket.status === "chiuso" ? "aperto" : "chiuso";
    try {
      await updateTicketStatus(token, selectedTicket.id, nextStatus);
      setSelectedTicket({ ...selectedTicket, status: nextStatus });
      setTickets((currentTickets) =>
        currentTickets.map((ticket) =>
          ticket.id === selectedTicket.id ? { ...ticket, status: nextStatus } : ticket,
        ),
      );
    } catch (_error) {
      setError("Impossibile aggiornare lo stato del ticket.");
    }
  }

  async function handleTranslateConversation() {
    if (!selectedTicket) {
      return;
    }

    setIsTranslating(true);
    setError("");
    try {
      const payload = await translateTicketConversation(token, selectedTicket.id);
      setTranslatedMessages(Array.isArray(payload.messages) ? payload.messages : []);
    } catch (_error) {
      setError("Impossibile tradurre la conversazione.");
    } finally {
      setIsTranslating(false);
    }
  }

  async function handleMailTo() {
    if (!selectedTicket?.user_email) {
      return;
    }

    setIsDraftingEmail(true);
    setError("");
    try {
      const draft = await generateTicketEmailDraft(token, selectedTicket.id);
      openMailTo(selectedTicket.user_email, draft.subject, draft.body);
    } catch (_error) {
      openMailTo(
        selectedTicket.user_email,
        `Riscontro alla richiesta TarAI - ${selectedTicket.domain || "assistenza"}`,
        `Ciao,\n\nabbiamo ricevuto la tua richiesta tramite TarAI.\n\n${selectedTicket.summary || ""}\n\nCordiali saluti,\nCustomer Care TarAI`,
      );
    } finally {
      setIsDraftingEmail(false);
    }
  }

  return (
    <div className="operator-surface app-surface relative flex h-dvh max-h-dvh flex-col overflow-hidden" data-theme={theme}>
      <DecorativeBackground />
      <OperatorTopbar
        isAuthenticated={isAuthenticated}
        theme={theme}
        onLogout={handleLogout}
        onThemeToggle={handleThemeToggle}
      />
      <main className="operator-stage relative z-10">
        {isAuthenticated ? (
          <section className="operator-panel">
            <OperatorPanelHeader operator={operator} onLogout={handleLogout} />
            <div className="operator-panel-body">
            <div className="operator-toolbar">
              <div className="min-w-0">
                <h1 className="brand-heading truncate">Dashboard Operatore</h1>
                <p className="brand-kicker">CUSTOMER CARE</p>
              </div>
              <OperatorControls
                sortBy={sortBy}
                statusFilter={statusFilter}
                ticketView={ticketView}
                onSortChange={setSortBy}
                onStatusChange={setStatusFilter}
                onViewModeChange={setTicketView}
              />
            </div>

            {error ? <div className="operator-alert">{error}</div> : null}

            <div className={`ticket-list ticket-list-${effectiveTicketView}`}>
              {isLoadingTickets ? (
                <OperatorEmptyState title="Caricamento Ticket" text="Recupero dei ticket in corso." />
              ) : sortedTickets.length ? (
                sortedTickets.map((ticket) => (
                  <TicketCard
                    key={ticket.id}
                    ticket={ticket}
                    onClick={() => openTicket(ticket.id)}
                  />
                ))
              ) : (
                <OperatorEmptyState title="Nessun Ticket" text="Non ci sono risultati per i filtri selezionati." />
              )}
            </div>
            </div>
          </section>
        ) : (
          <OperatorLoginCard error={error} onLogin={handleLogin} />
        )}
      </main>
      <div className="floating-mobile-actions operator-page-floating-actions">
        <ThemeToggle
          className="theme-toggle-mobile"
          theme={theme}
          t={themeLabels}
          onThemeToggle={handleThemeToggle}
        />
      </div>
      <TicketDetailModal
        isDraftingEmail={isDraftingEmail}
        isLoading={isLoadingDetail}
        isOpen={Boolean(selectedTicketId)}
        isTranslating={isTranslating}
        ticket={selectedTicket}
        translatedMessages={translatedMessages}
        onClose={closeTicketModal}
        onMailTo={handleMailTo}
        onStatusToggle={handleToggleStatus}
        onTranslate={handleTranslateConversation}
      />
    </div>
  );
}

function OperatorControls({
  sortBy,
  statusFilter,
  ticketView,
  onSortChange,
  onStatusChange,
  onViewModeChange,
}) {
  return (
    <div className="operator-controls">
      <div className="operator-filters">
        <label>
          Stato
          <select
            className="operator-status-select"
            value={statusFilter}
            onChange={(event) => onStatusChange(event.target.value)}
          >
            <option value="tutti">Qualsiasi</option>
            <option value="aperto">Aperto</option>
            <option value="chiuso">Chiuso</option>
          </select>
        </label>
        <label>
          Ordina per
          <select
            className="operator-sort-select"
            value={sortBy}
            onChange={(event) => onSortChange(event.target.value)}
          >
            <option value="date">Data</option>
            <option value="priority">Priorità</option>
            <option value="domain">Dominio</option>
            <option value="status">Stato</option>
          </select>
        </label>
      </div>
      <TicketViewToggle viewMode={ticketView} onViewModeChange={onViewModeChange} />
    </div>
  );
}

function OperatorTopbar({
  isAuthenticated,
  theme,
  onLogout,
  onThemeToggle,
}) {
  return (
    <header className="topbar relative z-10 shadow-sm backdrop-blur-xl">
      <div className="topbar-inner mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <div className="min-w-0">
            <h1 className="brand-heading truncate">TarAI | Giochi del Mediterraneo</h1>
            <p className="brand-kicker">Assistente AI multimodale per Taranto 2026</p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <div className="hidden items-center gap-2 md:flex">
            <a
              className="date-chip"
              href="https://www.ta2026.com/en/piano-dei-giochi/"
              target="_blank"
              rel="noreferrer"
            >
              21 AGO - 3 SET 2026
            </a>
            <a
              className="tag-chip"
              href="https://www.ta2026.com/en/"
              target="_blank"
              rel="noreferrer"
            >
              #TA2026
            </a>
          </div>
          {isAuthenticated ? (
            <button className="operator-logout-button" type="button" onClick={onLogout}>
              Logout
            </button>
          ) : null}
          <ThemeToggle
            className="theme-toggle-desktop"
            theme={theme}
            t={themeLabels}
            onThemeToggle={onThemeToggle}
          />
        </div>
      </div>
    </header>
  );
}

function OperatorPanelHeader({ operator, onLogout }) {
  return (
    <div className="chat-header operator-panel-header">
      <div className="flex min-w-0 items-center gap-3">
        <span className="chat-header-avatar operator-panel-avatar" aria-hidden="true">
          <img src={mainLogoUrl} alt="" />
        </span>
        <div className="min-w-0">
          <h2 className="chat-bot-name truncate text-lg font-black leading-tight sm:text-xl">
            {formatOperatorName(operator?.name)}
          </h2>
          <p className="chat-bot-status operator-panel-status flex items-center gap-2 text-sm font-medium leading-none">
            <span className="chat-online-dot" aria-hidden="true" />
            Online
          </p>
        </div>
      </div>
      <button className="operator-logout-button operator-panel-logout-mobile" type="button" onClick={onLogout}>
        Logout
      </button>
    </div>
  );
}

function OperatorLoginCard({ error, onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [localError, setLocalError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    setLocalError("");
    setIsSubmitting(true);
    try {
      await onLogin({ email: email.trim(), password });
    } catch (_error) {
      setLocalError("Credenziali operatore non valide.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="operator-login-card">
      <div className="operator-login-heading">
        <h1 className="brand-heading truncate">Accesso Operatore</h1>
        <p className="brand-kicker">AREA RISERVATA</p>
      </div>
      <p className="operator-login-copy">
        Dashboard per la Gestione dei Ticket di TarAI.
      </p>
      <form className="operator-login-form" onSubmit={handleSubmit}>
        <label>
          <span className="operator-login-label">
            <EmailFieldIcon />
            Email
          </span>
          <input
            autoComplete="username"
            placeholder="Inserisci e-mail"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label>
          <span className="operator-login-label">
            <PasswordFieldIcon />
            Password
          </span>
          <input
            autoComplete="current-password"
            placeholder="Inserisci password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {localError || error ? <div className="operator-alert">{localError || error}</div> : null}
        <button className="operator-primary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Accesso in corso" : "Accedi"}
        </button>
      </form>
    </section>
  );
}

function EmailFieldIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" focusable="false">
      <path d="M4.75 6.75h14.5v10.5H4.75z" />
      <path d="m5.25 7.25 6.75 5.5 6.75-5.5" />
    </svg>
  );
}

function PasswordFieldIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" focusable="false">
      <circle cx="8.25" cy="12.25" r="3.5" />
      <path d="M11.75 12.25h8" />
      <path d="M17.25 12.25v2.25" />
      <path d="M20 12.25v2.25" />
    </svg>
  );
}

function OperatorAvatar() {
  return (
    <span className="operator-avatar" aria-hidden="true">
      <img src={mainLogoUrl} alt="" />
    </span>
  );
}

function TicketViewToggle({ viewMode, onViewModeChange }) {
  return (
    <div className="ticket-view-toggle" aria-label="Tipo visualizzazione ticket">
      <button
        className={viewMode === "cards" ? "is-active" : ""}
        type="button"
        title="Vista card"
        aria-label="Vista card"
        aria-pressed={viewMode === "cards"}
        onClick={() => onViewModeChange("cards")}
      >
        <GridIcon />
      </button>
      <button
        className={viewMode === "list" ? "is-active" : ""}
        type="button"
        title="Vista lista"
        aria-label="Vista lista"
        aria-pressed={viewMode === "list"}
        onClick={() => onViewModeChange("list")}
      >
        <ListIcon />
      </button>
    </div>
  );
}

function GridIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4.5 4.5h6v6h-6v-6Zm9 0h6v6h-6v-6Zm-9 9h6v6h-6v-6Zm9 0h6v6h-6v-6Z"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.9"
      />
    </svg>
  );
}

function ListIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="2.2"
      />
    </svg>
  );
}

function TicketCard({ ticket, onClick }) {
  const priority = normalizedLabel(ticket.priority, "media");
  const status = normalizedLabel(ticket.status, "aperto");
  const domain = ticket.domain || "informazioni generali";

  return (
    <button
      className={`ticket-card ticket-priority-${priority} ticket-status-${status}`}
      type="button"
      onClick={onClick}
    >
      <div className="ticket-card-header">
        <span className="ticket-status-pill">{status}</span>
        <span className="ticket-meta-pills">
          <span>{priority}</span>
          <span>{domain}</span>
        </span>
      </div>
      <div className="ticket-card-body">
        <p>{ticket.summary || "Ticket senza summary disponibile."}</p>
      </div>
      <div className="ticket-card-footer">
        <time className="ticket-card-date" dateTime={ticket.created_at || ""}>
          {formatDate(ticket.created_at)}
        </time>
        <span className="ticket-card-email">
          {ticket.user_email}
        </span>
      </div>
    </button>
  );
}

function TicketDetailModal({
  isDraftingEmail,
  isLoading,
  isOpen,
  isTranslating,
  ticket,
  translatedMessages,
  onClose,
  onMailTo,
  onStatusToggle,
  onTranslate,
}) {
  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    const previousBodyOverflow = document.body.style.overflow;
    function handleKeyDown(event) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <div className="image-lightbox operator-ticket-lightbox" role="dialog" aria-modal="true" onClick={onClose}>
      <button className="image-lightbox-close" type="button" aria-label="Chiudi ticket" onClick={onClose}>
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M6 6l12 12M18 6L6 18"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="2.4"
          />
        </svg>
      </button>
      <div className="operator-ticket-modal" onClick={(event) => event.stopPropagation()}>
        {isLoading || !ticket ? (
          <OperatorEmptyState title="Apertura ticket" text="Caricamento conversazione." />
        ) : (
          <TicketDetail
            isDraftingEmail={isDraftingEmail}
            isTranslating={isTranslating}
            ticket={ticket}
            translatedMessages={translatedMessages}
            onMailTo={onMailTo}
            onStatusToggle={onStatusToggle}
            onTranslate={onTranslate}
          />
        )}
      </div>
    </div>,
    document.body,
  );
}

function TicketDetail({
  isDraftingEmail,
  isTranslating,
  ticket,
  translatedMessages,
  onMailTo,
  onStatusToggle,
  onTranslate,
}) {
  const messages = translatedMessages || ticket.conversation || [];

  return (
    <>
      <div className="operator-detail-header">
        <div>
          <p className="operator-kicker">Ticket selezionato</p>
          <h2>{ticket.domain || "Informazioni generali"}</h2>
          <span>{formatDate(ticket.created_at)}</span>
        </div>
        <div className="operator-detail-actions">
          <button type="button" onClick={onStatusToggle}>
            Segna come {ticket.status === "chiuso" ? "aperto" : "chiuso"}
          </button>
          <button type="button" disabled={isTranslating} onClick={onTranslate}>
            {isTranslating ? "Traduzione" : "Traduci chat"}
          </button>
          <button className="operator-primary-button" type="button" disabled={isDraftingEmail} onClick={onMailTo}>
            {isDraftingEmail ? "Bozza email" : "Rispondi via email"}
          </button>
        </div>
      </div>

      <div className="operator-ticket-summary">
        <div>
          <span>Priorita</span>
          <strong>{ticket.priority || "media"}</strong>
        </div>
        <div>
          <span>Stato</span>
          <strong>{ticket.status || "aperto"}</strong>
        </div>
        <div>
          <span>Email utente</span>
          <strong>{ticket.user_email}</strong>
        </div>
      </div>

      <p className="operator-summary-text">{ticket.summary}</p>

      <div className="operator-conversation">
        {messages.length ? (
          messages.map((message) => (
            <OperatorConversationMessage key={message.id} message={message} />
          ))
        ) : (
          <OperatorEmptyState title="Conversazione vuota" text="Non sono presenti messaggi associati al ticket." />
        )}
      </div>
    </>
  );
}

function OperatorConversationMessage({ message }) {
  const isBot = message.role === "bot";
  const content = message.translated_content ?? message.content;
  const mediaLabel =
    !content && message.type === "image"
      ? "Immagine inviata dall'utente"
      : !content && message.type === "audio"
        ? "Audio inviato dall'utente"
        : "";

  return (
    <article className={isBot ? "operator-message operator-message-bot" : "operator-message operator-message-user"}>
      <span>{isBot ? "Bot" : "Utente"} - {formatDate(message.created_at)}</span>
      <p>{content || mediaLabel || "Messaggio senza contenuto testuale."}</p>
      {message.media_url && message.type === "image" ? (
        <img className="operator-message-media" src={message.media_url} alt="" />
      ) : null}
      {message.media_url && message.type === "audio" ? (
        <audio className="operator-message-audio" src={message.media_url} controls />
      ) : null}
    </article>
  );
}

function OperatorEmptyState({ title, text }) {
  return (
    <div className="operator-empty-state">
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}

function normalizedLabel(value, fallback) {
  return String(value || fallback).trim().toLowerCase();
}

function priorityRank(priority) {
  return PRIORITY_ORDER[normalizedLabel(priority, "media")] ?? 9;
}

function dateRank(value) {
  if (!value) {
    return 0;
  }
  const date = new Date(String(value).replace(" ", "T"));
  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

function getInitialTheme() {
  const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
  return saved || (window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ? "dark" : "light");
}

function getInitialTicketView() {
  const saved = window.localStorage.getItem(TICKET_VIEW_STORAGE_KEY);
  return saved === "list" ? "list" : "cards";
}

function isOperatorMobileViewport() {
  if (typeof window === "undefined" || !window.matchMedia) {
    return false;
  }
  return window.matchMedia("(max-width: 640px)").matches;
}

function formatDate(value) {
  if (!value) {
    return "";
  }
  const date = new Date(String(value).replace(" ", "T"));
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("it-IT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatOperatorName(name) {
  return String(name || "Operatore").toLocaleUpperCase("it-IT");
}

function openMailTo(email, subject, body) {
  const href = `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(subject || "")}&body=${encodeURIComponent(body || "")}`;
  window.location.href = href;
}

function isUnauthorized(error) {
  return String(error?.message || "").includes("401");
}
