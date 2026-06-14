import { useEffect, useMemo, useState } from "react";

import { mainLogoUrl } from "../assets/index.js";
import { DecorativeBackground } from "../components/DecorativeBackground.jsx";
import { ThemeToggle } from "../components/ThemeToggle.jsx";
import {
  clearOperatorSession,
  fetchOperatorProfile,
  getStoredOperatorSession,
  loginOperator,
  logoutOperator,
  storeOperatorSession,
} from "../services/operatorApi.js";
import {
  createKnowledgeRecord,
  fetchKnowledgeOptions,
} from "../services/knowledgeApi.js";

const THEME_STORAGE_KEY = "talos-theme";
const KNOWLEDGE_PAGE_TITLE = "T.A.L.O.S. | Taranto 2026 AI Live Operator Support";
const DEFAULT_FORM = {
  title: "",
  item_type: "",
  domain: "",
  source_url: "",
  document: "",
  address: "",
  latitude: "",
  longitude: "",
};
const LOCATION_METADATA_TYPES = new Set(["venue", "event_schedule", "transport", "accessibility"]);
const LOCATION_METADATA_DOMAINS = new Set(["venue", "accessibility"]);
const themeLabels = {
  themeToLight: "Passa alla modalita chiara",
  themeToDark: "Passa alla modalita scura",
};

export function KnowledgeBaseAdminPage() {
  const [{ token, operator }, setSession] = useState(() => getStoredOperatorSession());
  const [theme, setTheme] = useState(() => getInitialTheme());
  const [options, setOptions] = useState({ domains: [], item_types: [] });
  const [form, setForm] = useState(DEFAULT_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.lang = "it";
    document.documentElement.dir = "ltr";
    document.title = KNOWLEDGE_PAGE_TITLE;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    if (!token) {
      return;
    }

    let isCancelled = false;
    async function hydrate() {
      try {
        const [profile, nextOptions] = await Promise.all([
          fetchOperatorProfile(token),
          fetchKnowledgeOptions(token),
        ]);
        if (!isCancelled) {
          updateSession(token, profile);
          setOptions(nextOptions);
        }
      } catch (_error) {
        if (!isCancelled) {
          handleSessionExpired();
        }
      }
    }
    hydrate();

    return () => {
      isCancelled = true;
    };
  }, [token]);

  const itemTypes = useMemo(
    () => options.item_types?.length ? options.item_types : ["custom_information"],
    [options.item_types],
  );
  const domains = useMemo(
    () => options.domains?.length ? options.domains : ["general"],
    [options.domains],
  );
  const isLocationFieldsEnabled = useMemo(
    () => isLocationMetadataEnabled(form.item_type, form.domain),
    [form.item_type, form.domain],
  );

  function updateSession(nextToken, nextOperator) {
    const nextSession = { token: nextToken, operator: nextOperator };
    storeOperatorSession(nextSession);
    setSession(nextSession);
  }

  function handleSessionExpired() {
    clearOperatorSession();
    setSession({ token: null, operator: null });
    setError("Sessione scaduta. Effettua di nuovo l'accesso.");
  }

  async function handleLogin(credentials) {
    const nextSession = await loginOperator(credentials);
    updateSession(nextSession.token, nextSession.operator);
  }

  async function handleLogout() {
    try {
      if (token) {
        await logoutOperator(token);
      }
    } catch (_error) {
      // La sessione locale va comunque rimossa.
    } finally {
      clearOperatorSession();
      setSession({ token: null, operator: null });
    }
  }

  function updateForm(field, value) {
    setForm((currentForm) => {
      const nextForm = { ...currentForm, [field]: value };
      if (
        (field === "item_type" || field === "domain")
        && !isLocationMetadataEnabled(nextForm.item_type, nextForm.domain)
      ) {
        nextForm.address = "";
        nextForm.latitude = "";
        nextForm.longitude = "";
      }
      return nextForm;
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    setIsSubmitting(true);
    try {
      const payload = normalizeFormPayload(form, isLocationFieldsEnabled);
      const result = await createKnowledgeRecord(token, payload);
      setSuccess(`Record ${result.record.id} aggiunto, indicizzato e disponibile per il ChatBot.`);
      setForm({ ...DEFAULT_FORM, item_type: payload.item_type, domain: payload.domain });
    } catch (submitError) {
      if (isUnauthorized(submitError)) {
        handleSessionExpired();
      } else {
        setError(getErrorMessage(submitError));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!token) {
    return (
      <KnowledgeSurface
        isAuthenticated={false}
        theme={theme}
        onLogout={handleLogout}
        onThemeToggle={() => setTheme(toggleTheme)}
      >
        <OperatorLoginCard error={error} onLogin={handleLogin} />
      </KnowledgeSurface>
    );
  }

  return (
    <KnowledgeSurface
      isAuthenticated={true}
      theme={theme}
      onLogout={handleLogout}
      onThemeToggle={() => setTheme(toggleTheme)}
    >
      <section className="knowledge-panel">
        <KnowledgePanelHeader operator={operator} onLogout={handleLogout} />

        <main className="knowledge-main">
          <form className="knowledge-form" onSubmit={handleSubmit}>
            <div className="knowledge-section-heading">
              <h2>Nuovo Record Knowledge Base</h2>
              <span>{form.document.trim().length}/12000</span>
            </div>

            <div className="knowledge-grid knowledge-grid-two">
              <label>
                <RequiredFieldLabel>Titolo</RequiredFieldLabel>
                <input
                  required
                  maxLength={180}
                  placeholder="Inserire il titolo del contenuto informativo"
                  value={form.title}
                  onChange={(event) => updateForm("title", event.target.value)}
                />
              </label>
              <label>
                <RequiredFieldLabel>Fonte</RequiredFieldLabel>
                <input
                  required
                  maxLength={500}
                  placeholder="Inserire URL della fonte"
                  value={form.source_url}
                  onChange={(event) => updateForm("source_url", event.target.value)}
                />
              </label>
            </div>

            <div className="knowledge-grid knowledge-grid-two">
              <label>
                <RequiredFieldLabel>Tipo</RequiredFieldLabel>
                <select
                  required
                  className={!form.item_type ? "knowledge-select-placeholder" : undefined}
                  value={form.item_type}
                  onChange={(event) => updateForm("item_type", event.target.value)}
                >
                  <option value="" disabled>Selezionare il tipo di informazione</option>
                  {itemTypes.map((itemType) => (
                    <option key={itemType} value={itemType}>{formatOption(itemType)}</option>
                  ))}
                </select>
              </label>
              <label>
                <RequiredFieldLabel>Dominio</RequiredFieldLabel>
                <select
                  required
                  className={!form.domain ? "knowledge-select-placeholder" : undefined}
                  value={form.domain}
                  onChange={(event) => updateForm("domain", event.target.value)}
                >
                  <option value="" disabled>Selezionare il dominio informativo</option>
                  {domains.map((domain) => (
                    <option key={domain} value={domain}>{formatOption(domain)}</option>
                  ))}
                </select>
              </label>
            </div>

            <label>
              <RequiredFieldLabel>Documento</RequiredFieldLabel>
              <textarea
                required
                minLength={40}
                maxLength={12000}
                placeholder="Inserire il testo del contenuto informativo da aggiungere alla knowledge base"
                value={form.document}
                onChange={(event) => updateForm("document", event.target.value)}
              />
            </label>

            <div className="knowledge-grid knowledge-grid-three">
              <label>
                <RequiredFieldLabel required={isLocationFieldsEnabled}>Indirizzo</RequiredFieldLabel>
                <input
                  maxLength={300}
                  disabled={!isLocationFieldsEnabled}
                  required={isLocationFieldsEnabled}
                  placeholder="Inserire indirizzo completo del luogo"
                  value={form.address}
                  onChange={(event) => updateForm("address", event.target.value)}
                />
              </label>
              <label>
                <RequiredFieldLabel required={isLocationFieldsEnabled}>Latitudine</RequiredFieldLabel>
                <input
                  inputMode="decimal"
                  disabled={!isLocationFieldsEnabled}
                  required={isLocationFieldsEnabled}
                  placeholder="Inserire latitudine del luogo"
                  value={form.latitude}
                  onChange={(event) => updateForm("latitude", event.target.value)}
                />
              </label>
              <label>
                <RequiredFieldLabel required={isLocationFieldsEnabled}>Longitudine</RequiredFieldLabel>
                <input
                  inputMode="decimal"
                  disabled={!isLocationFieldsEnabled}
                  required={isLocationFieldsEnabled}
                  placeholder="Inserire longitudine del luogo"
                  value={form.longitude}
                  onChange={(event) => updateForm("longitude", event.target.value)}
                />
              </label>
            </div>

            {error ? <div className="operator-alert">{error}</div> : null}
            {success ? <div className="knowledge-success">{success}</div> : null}

            <div className="knowledge-actions">
              <button className="operator-primary-button" type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Indicizzazione…" : "Aggiungi"}
              </button>
            </div>
          </form>
        </main>
      </section>
    </KnowledgeSurface>
  );
}

function KnowledgeSurface({ children, isAuthenticated, theme, onLogout, onThemeToggle }) {
  return (
    <div className="app-surface operator-surface knowledge-surface relative flex h-dvh max-h-dvh flex-col overflow-hidden" data-theme={theme}>
      <DecorativeBackground />
      <header className="topbar relative z-10 shadow-sm backdrop-blur-xl">
        <div className="topbar-inner mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <div className="min-w-0">
              <h1 className="brand-heading truncate">
                <span className="app-title-desktop">T.A.L.O.S | Giochi del Mediterraneo</span>
                <span className="app-title-mobile">T.A.L.O.S. | Taranto 2026</span>
              </h1>
              <p className="brand-kicker">Taranto 2026 AI Live Operator Support</p>
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
      <main className="operator-stage relative z-10">{children}</main>
      <div className="floating-mobile-actions operator-page-floating-actions">
        <ThemeToggle
          className="theme-toggle-mobile"
          theme={theme}
          t={themeLabels}
          onThemeToggle={onThemeToggle}
        />
      </div>
    </div>
  );
}

function KnowledgePanelHeader({ operator, onLogout }) {
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

function RequiredFieldLabel({ children, required = true }) {
  return (
    <span>
      {children}
      {required ? <span className="knowledge-required-mark" aria-hidden="true">*</span> : null}
    </span>
  );
}

function OperatorLoginCard({ error, onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
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
        Gestione della Knowledge Base di T.A.L.O.S.
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
          <span className="operator-password-field">
            <input
              autoComplete="current-password"
              placeholder="Inserisci password"
              type={isPasswordVisible ? "text" : "password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <button
              className="operator-password-toggle"
              type="button"
              aria-label={isPasswordVisible ? "Nascondi password" : "Mostra password"}
              aria-pressed={isPasswordVisible}
              onClick={() => setIsPasswordVisible((currentValue) => !currentValue)}
            >
              <PasswordVisibilityIcon isVisible={isPasswordVisible} />
            </button>
          </span>
        </label>
        {localError || error ? <div className="operator-alert">{localError || error}</div> : null}
        <button className="operator-primary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Accesso in corso" : "Accedi"}
        </button>
      </form>
    </section>
  );
}

function normalizeFormPayload(form, includeLocationMetadata) {
  const payload = {
    title: form.title.trim(),
    item_type: form.item_type,
    domain: form.domain,
    source_url: form.source_url.trim(),
    document: form.document.trim(),
  };
  if (!includeLocationMetadata) {
    return payload;
  }
  if (form.address.trim()) {
    payload.address = form.address.trim();
  }
  if (form.latitude.trim()) {
    payload.latitude = Number(form.latitude.replace(",", "."));
  }
  if (form.longitude.trim()) {
    payload.longitude = Number(form.longitude.replace(",", "."));
  }
  return payload;
}

function isLocationMetadataEnabled(itemType, domain) {
  return LOCATION_METADATA_TYPES.has(itemType) || LOCATION_METADATA_DOMAINS.has(domain);
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

function PasswordVisibilityIcon({ isVisible }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" focusable="false">
      <path d="M3.75 12s2.85-5 8.25-5 8.25 5 8.25 5-2.85 5-8.25 5-8.25-5-8.25-5Z" />
      <circle cx="12" cy="12" r="2.45" />
      {!isVisible ? <path d="M5 19 19 5" /> : null}
    </svg>
  );
}

function getInitialTheme() {
  const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
  return saved || (window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ? "dark" : "light");
}

function toggleTheme(currentTheme) {
  return currentTheme === "dark" ? "light" : "dark";
}

function isUnauthorized(error) {
  const message = String(error?.message || "");
  return message.includes("401") || /credential|validate|unauthorized/i.test(message);
}

function getErrorMessage(error) {
  const message = String(error?.message || "");
  if (message.includes("already exists")) {
    return "Esiste gia un record con questo ID.";
  }
  if (message.includes("validation")) {
    return "Controlla i campi inseriti.";
  }
  return message || "Impossibile aggiungere il record.";
}

function formatOperatorName(name) {
  return (name || "Operatore").toLocaleUpperCase("it-IT");
}

function formatOption(value) {
  return String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
