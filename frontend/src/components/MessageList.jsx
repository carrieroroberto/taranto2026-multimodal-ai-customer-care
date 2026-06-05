import { useEffect, useRef, useState } from "react";

import { chatBotUrl, chatUserUrl } from "../assets/index.js";
import { ImageLightbox } from "./ImageLightbox.jsx";
import { STOP_AUDIO_PLAYBACK_EVENT, stopAudioPlayback } from "../utils/audioPlayback.js";

const FALLBACK_SOURCE_ICON = "/icons/source-fallback.svg";

export function MessageList({
  feedbackCanCorrectNegative = false,
  feedbackDisabled = false,
  activeEscalationFlowId = null,
  allowActiveEscalationFeedback = false,
  isSending,
  messages,
  listRef,
  mobileActionSlot,
  suggestedQuestions = [],
  t,
  onContentLoad,
  onFeedback,
  onSuggestionClick,
}) {
  const [previewImage, setPreviewImage] = useState(null);

  return (
    <>
      <div className="message-list-shell">
        <div
          ref={listRef}
          id="messageList"
          className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-8"
        >
          <div aria-live="polite">
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message}
                t={t}
                onImageOpen={setPreviewImage}
                onContentLoad={onContentLoad}
                feedbackCanCorrectNegative={feedbackCanCorrectNegative}
                feedbackDisabled={feedbackDisabled}
                activeEscalationFlowId={activeEscalationFlowId}
                allowActiveEscalationFeedback={allowActiveEscalationFeedback}
                onFeedback={onFeedback}
                onSuggestionClick={onSuggestionClick}
                showSuggestions={!isSending}
                suggestedQuestions={suggestedQuestions}
              />
            ))}
          </div>
        </div>
        {mobileActionSlot}
      </div>
      <ImageLightbox
        closeLabel={t.closeImage}
        image={previewImage}
        onClose={() => setPreviewImage(null)}
      />
    </>
  );
}

function ChatMessage({
  message,
  t,
  onImageOpen,
  onContentLoad,
  feedbackCanCorrectNegative,
  feedbackDisabled,
  activeEscalationFlowId,
  allowActiveEscalationFeedback,
  onFeedback,
  onSuggestionClick,
  showSuggestions,
  suggestedQuestions,
}) {
  const isUser = message.role === "user";
  const sources = getVisibleSources(message, isUser);
  const blockClassName = isUser
    ? "chat-message-block chat-message-block-user"
    : "chat-message-block";
  const turnClassName = isUser ? "chat-turn chat-turn-user" : "chat-turn";
  const avatarClassName = isUser
    ? "chat-avatar chat-avatar-user"
    : "chat-avatar chat-avatar-assistant";
  const stackClassName = sources.length
    ? "chat-message-stack chat-message-stack-with-sources"
    : "chat-message-stack";
  const bubbleClassName = isUser
    ? `chat-bubble chat-bubble-user${message.image ? " chat-bubble-image" : ""}`
    : message.isError
      ? "chat-bubble chat-bubble-error"
      : `chat-bubble chat-bubble-assistant${sources.length ? " chat-bubble-with-sources" : ""}`;

  return (
    <article className={blockClassName}>
      {!message.translationKey && !message.isLoading ? (
        <MessageTimestamp timestamp={message.createdAt} />
      ) : null}
      <div className={turnClassName}>
        <div className={avatarClassName}>
          <img
            src={isUser ? chatUserUrl : chatBotUrl}
            alt={isUser ? t.userLabel : t.botName}
          />
        </div>
        <div className={stackClassName}>
          <div className={bubbleClassName}>
            {message.isLoading ? (
              <TypingIndicator label={t.typing} />
            ) : message.translationKey === "welcome" ? (
              <WelcomeMessage t={t} />
            ) : (
              <>
                {message.image ? (
                  <button
                    className="message-image-button"
                    type="button"
                    aria-label="Apri immagine"
                    onClick={() => onImageOpen(message.image)}
                  >
                    <img
                      className="message-image-preview"
                      src={message.image}
                      alt=""
                      aria-hidden="true"
                      onLoad={onContentLoad}
                    />
                  </button>
                ) : null}
                {message.audio ? (
                  <AudioWaveform audio={message.audio} label={t.audioMessage} />
                ) : null}
                {message.text && message.messageType !== "audio" && sources.length ? (
                  <TextWithInlineSources
                    className={
                      message.image ? "message-text message-text-under-media" : ""
                    }
                    emphasizeTicketEmail={shouldEmphasizeTicketEmail(message, isUser)}
                    sources={sources}
                    text={message.text}
                  />
                ) : message.text && message.messageType !== "audio" ? (
                  <span
                    className={
                      message.image ? "message-text message-text-under-media" : ""
                    }
                  >
                    <FormattedMessageText
                      emphasizeTicketEmail={shouldEmphasizeTicketEmail(message, isUser)}
                      text={message.text}
                    />
                  </span>
                ) : null}
              </>
            )}
          </div>
          {message.translationKey === "welcome" ? (
            <WelcomeSuggestions
              disabled={!showSuggestions}
              questions={suggestedQuestions}
              onSuggestionClick={onSuggestionClick}
            />
          ) : null}
        <MessageFeedback
          disabled={feedbackDisabled}
          activeEscalationFlowId={activeEscalationFlowId}
          allowActiveEscalationFeedback={allowActiveEscalationFeedback}
          message={message}
          t={t}
            onFeedback={onFeedback}
          />
        </div>
      </div>
    </article>
  );
}

function MessageTimestamp({ timestamp }) {
  const label = formatMessageTimestamp(timestamp);
  if (!label) {
    return null;
  }

  return <span className="message-timestamp">{label}</span>;
}

function MessageFeedback({
  disabled,
  activeEscalationFlowId,
  allowActiveEscalationFeedback,
  message,
  t,
  onFeedback,
}) {
  const canShow =
    message.role === "assistant" &&
    !message.translationKey &&
    !message.isLoading &&
    !message.isError &&
    !message.feedbackDisabled &&
    message.persistedId;

  if (!canShow) {
    return null;
  }

  // Se 'disabled' è true, aggiungiamo la classe 'is-disabled' che grigisce tutto
  const canEditActiveEscalation =
    allowActiveEscalationFeedback &&
    activeEscalationFlowId === message.id &&
    message.satisfaction === false;
  const isDisabled = (disabled && !canEditActiveEscalation) || message.feedbackLocked;
  const containerClassName = isDisabled ? "message-feedback is-disabled" : "message-feedback";

  return (
    <div className={containerClassName} aria-label={t.feedbackLabel}>
      <span className="feedback-helpful-text">{t.feedbackHelpful}</span>
      <button
        className={
          message.satisfaction === true
            ? "message-feedback-button is-selected"
            : "message-feedback-button"
        }
        type="button"
        aria-pressed={message.satisfaction === true}
        aria-label={t.feedbackPositive}
        disabled={isDisabled}
        title={t.feedbackPositive}
        onClick={() => onFeedback?.(message, true)}
      >
        <span className="feedback-emoji feedback-emoji-positive" data-emoji="👍🏻" aria-hidden="true" />
      </button>
      <button
        className={
          message.satisfaction === false
            ? "message-feedback-button is-selected"
            : "message-feedback-button"
        }
        type="button"
        aria-pressed={message.satisfaction === false}
        aria-label={t.feedbackNegative}
        disabled={isDisabled}
        title={t.feedbackNegative}
        onClick={() => onFeedback?.(message, false)}
      >
        <span className="feedback-emoji feedback-emoji-negative" data-emoji="👎🏻" aria-hidden="true" />
      </button>
    </div>
  );
}

function formatMessageTimestamp(timestamp) {
  if (!timestamp) {
    return "";
  }

  const normalizedTimestamp =
    typeof timestamp === "string" ? timestamp.replace(" ", "T") : timestamp;
  const date = new Date(normalizedTimestamp);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const datePart = new Intl.DateTimeFormat("it-IT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
  const timePart = new Intl.DateTimeFormat("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);

  return `${datePart}, ${timePart}`;
}

function WelcomeSuggestions({ disabled, questions, onSuggestionClick }) {
  if (!questions.length) {
    return null;
  }

  return (
    <div className="welcome-suggestions">
      {questions.map((question) => (
        <button
          key={question}
          className="welcome-suggestion-button"
          type="button"
          disabled={disabled}
          onClick={() => onSuggestionClick?.(question)}
        >
          {question}
        </button>
      ))}
    </div>
  );
}

function TextWithInlineSources({
  className,
  emphasizeTicketEmail = false,
  sources,
  text,
}) {
  return (
    <span className={className ? `${className} message-text-with-sources` : "message-text-with-sources"}>
      <span>
        <FormattedMessageText
          emphasizeTicketEmail={emphasizeTicketEmail}
          text={text}
        />
      </span>
      {"\u00a0"}
      <SourceFavicons sources={sources} />
    </span>
  );
}

function FormattedMessageText({ emphasizeTicketEmail = false, text }) {
  if (!emphasizeTicketEmail) {
    return text;
  }

  const emailMatch = String(text || "").match(
    /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i,
  );
  if (!emailMatch) {
    return text;
  }

  const email = emailMatch[0];
  const before = text.slice(0, emailMatch.index);
  const after = text.slice(emailMatch.index + email.length);

  return (
    <>
      {before}
      <strong>{email}</strong>
      {after}
    </>
  );
}

function shouldEmphasizeTicketEmail(message, isUser) {
  if (isUser || message.isError || message.isLoading || !message.text) {
    return false;
  }

  const text = String(message.text);
  const normalized = normalizeSourceText(text);
  const latinSuccessPatterns = [
    "richiesta inviata con successo",
    "request sent successfully",
    "solicitud enviada correctamente",
    "demande envoyee avec succes",
  ];
  const hasLatinSuccessPattern = latinSuccessPatterns.some((pattern) =>
    normalized.includes(pattern),
  );
  const hasArabicSuccessPattern = text.includes(
    "\u062a\u0645 \u0625\u0631\u0633\u0627\u0644 \u0627\u0644\u0637\u0644\u0628 \u0628\u0646\u062c\u0627\u062d",
  );

  return hasLatinSuccessPattern || hasArabicSuccessPattern;
}

function SourceFavicons({ sources }) {
  const mapSources = uniqueMapSources(sources);

  return (
    <span className="source-favicons" aria-label="Sorgenti consultate">
      {mapSources.map((source, index) => (
        <a
          key={`${source.maps_url}-${index}`}
          className="source-maps-link"
          href={source.maps_url}
          target="_blank"
          rel="noreferrer"
          title="Apri in Google Maps"
        >
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" />
          </svg>
        </a>
      ))}
      {sources.map((source, index) => (
        <span key={`${source.url}-${index}`} className="source-favicon-group">
          <a
            className="source-favicon-link"
            href={source.url}
            target="_blank"
            rel="noreferrer"
            title={source.title || source.url}
          >
            <img
              src={getFaviconUrl(source.url)}
              alt=""
              aria-hidden="true"
              onError={(event) => {
                event.currentTarget.onerror = null;
                event.currentTarget.src = FALLBACK_SOURCE_ICON;
              }}
            />
          </a>
        </span>
      ))}
    </span>
  );
}

function getVisibleSources(message, isUser) {
  if (
    isUser ||
    message.isError ||
    message.isLoading ||
    message.translationKey ||
    isServiceAnswerText(message.text) ||
    !Array.isArray(message.sources)
  ) {
    return [];
  }

  const visibleSources = [];
  const seenSources = new Set();
  for (const source of message.sources) {
    if (typeof source?.url !== "string" || !source.url.trim()) {
      continue;
    }
    const key = canonicalSourceKey(source.url);
    if (seenSources.has(key)) {
      continue;
    }
    seenSources.add(key);
    visibleSources.push(source);
    if (visibleSources.length === 3) {
      break;
    }
  }
  return visibleSources;
}

function isServiceAnswerText(text) {
  const normalized = normalizeSourceText(text);
  if (!normalized) {
    return true;
  }

  return [
    "ciao sono tara",
    "come posso aiutarti",
    "how can i help",
    "how may i help",
    "como puedo ayudarte",
    "comment puis je vous aider",
    "scrivi la tua email",
    "inserisci la tua email",
    "write your email",
    "enter your email",
    "verrai ricontattato",
    "human operator",
    "operatore umano",
    "al momento non ho un dato abbastanza preciso",
    "i don t have enough precise information",
    "i don t have enough precise information",
    "no tengo informacion suficientemente precisa",
    "je n ai pas d informations suffisamment precises",
  ].some((pattern) => normalized.includes(pattern));
}

function normalizeSourceText(text) {
  return String(text || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function canonicalSourceKey(url) {
  try {
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, "");
  } catch {
    return String(url).trim().toLowerCase().replace(/\/+$/, "");
  }
}

function uniqueMapSources(sources) {
  const uniqueSources = [];
  const seenMaps = new Set();
  for (const source of sources) {
    if (!source?.maps_url) {
      continue;
    }
    const key = String(source.maps_url).trim().toLowerCase();
    if (seenMaps.has(key)) {
      continue;
    }
    seenMaps.add(key);
    uniqueSources.push(source);
  }
  return uniqueSources;
}

function getFaviconUrl(url) {
  try {
    const domain = new URL(url).hostname;
    return `https://www.google.com/s2/favicons?domain=${domain}&sz=64`;
  } catch {
    return FALLBACK_SOURCE_ICON;
  }
}

function AudioWaveform({ audio, label }) {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [durationMs, setDurationMs] = useState(audio?.durationMs || 0);
  const fallbackBars = [12, 18, 10, 24, 16, 28, 14, 22, 12, 18, 26, 15, 21, 11];
  const bars = audio?.waveform?.length ? audio.waveform : fallbackBars;
  const audioUrl = typeof audio === "object" ? audio.url : null;

  useEffect(() => {
    setDurationMs(audio?.durationMs || 0);
    setIsPlaying(false);
  }, [audio?.durationMs, audioUrl]);

  useEffect(() => {
    function handleStopAudioPlayback() {
      const audioElement = audioRef.current;
      if (!audioElement) {
        return;
      }

      audioElement.pause();
      setIsPlaying(false);
    }

    window.addEventListener(STOP_AUDIO_PLAYBACK_EVENT, handleStopAudioPlayback);
    return () => {
      window.removeEventListener(STOP_AUDIO_PLAYBACK_EVENT, handleStopAudioPlayback);
    };
  }, []);

  async function handleTogglePlayback() {
    const audioElement = audioRef.current;
    if (!audioElement) {
      return;
    }

    if (isPlaying) {
      audioElement.pause();
      setIsPlaying(false);
      return;
    }

    try {
      stopAudioPlayback();
      await audioElement.play();
      setIsPlaying(true);
    } catch (_error) {
      setIsPlaying(false);
    }
  }

  function handleLoadedMetadata() {
    const audioElement = audioRef.current;
    if (!audioElement || durationMs > 0) {
      return;
    }

    if (Number.isFinite(audioElement.duration)) {
      setDurationMs(audioElement.duration * 1000);
    }
  }

  return (
    <div className="audio-waveform" aria-label={label || "Audio message"}>
      <button
        className="audio-play-button"
        type="button"
        aria-label={isPlaying ? "Pausa audio" : "Riproduci audio"}
        disabled={!audioUrl}
        onClick={handleTogglePlayback}
      >
        {isPlaying ? (
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <rect x="7" y="5" width="3.5" height="14" rx="1" />
            <rect x="13.5" y="5" width="3.5" height="14" rx="1" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M8 5v14l11-7z" />
          </svg>
        )}
      </button>
      <span className="audio-bars" aria-hidden="true">
        {bars.map((height, index) => (
          <span key={`${height}-${index}`} style={{ height }} />
        ))}
      </span>
      <span className="audio-duration">{formatDuration(durationMs)}</span>
      {audioUrl ? (
        <audio
          ref={audioRef}
          preload="metadata"
          src={audioUrl}
          onEnded={(event) => {
            event.currentTarget.currentTime = 0;
            setIsPlaying(false);
          }}
          onLoadedMetadata={handleLoadedMetadata}
        />
      ) : null}
    </div>
  );
}

function formatDuration(durationMs) {
  const totalSeconds =
    durationMs > 0 ? Math.max(1, Math.ceil(durationMs / 1000)) : 0;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function WelcomeMessage({ t }) {
  return (
    <>
      {t.welcomePrefix} <strong>{t.botName}</strong>
      {t.welcomeMiddle}
      <strong>{t.eventName}</strong>
      {" "}
      <strong>{t.welcomeSuffix.trim()}</strong>
    </>
  );
}

function TypingIndicator({ label }) {
  return (
    <span className="typing" aria-label={label}>
      <span />
      <span />
      <span />
    </span>
  );
}
