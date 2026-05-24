import { useEffect, useRef, useState } from "react";

import { chatBotUrl, chatUserDarkUrl, chatUserUrl } from "../assets/index.js";
import { ImageLightbox } from "./ImageLightbox.jsx";

const FALLBACK_SOURCE_ICON = "/icons/source-fallback.svg";

export function MessageList({
  feedbackCanCorrectNegative = false,
  feedbackDisabled = false,
  isSending,
  messages,
  listRef,
  mobileActionSlot,
  suggestedQuestions = [],
  theme,
  t,
  onContentLoad,
  onFeedback,
  onSuggestionClick,
}) {
  const [previewImage, setPreviewImage] = useState(null);

  return (
    <>
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
              theme={theme}
              t={t}
              onImageOpen={setPreviewImage}
              onContentLoad={onContentLoad}
              feedbackCanCorrectNegative={feedbackCanCorrectNegative}
              feedbackDisabled={feedbackDisabled}
              onFeedback={onFeedback}
              onSuggestionClick={onSuggestionClick}
              showSuggestions={!isSending}
              suggestedQuestions={suggestedQuestions}
            />
          ))}
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
  theme,
  t,
  onImageOpen,
  onContentLoad,
  feedbackCanCorrectNegative,
  feedbackDisabled,
  onFeedback,
  onSuggestionClick,
  showSuggestions,
  suggestedQuestions,
}) {
  const isUser = message.role === "user";
  const userAvatarUrl = theme === "dark" ? chatUserDarkUrl : chatUserUrl;
  const sources = getVisibleSources(message, isUser);
  const turnClassName = isUser ? "chat-turn chat-turn-user" : "chat-turn";
  const avatarClassName = isUser
    ? "chat-avatar chat-avatar-user"
    : "chat-avatar chat-avatar-assistant";
  const bubbleClassName = isUser
    ? `chat-bubble chat-bubble-user${message.image ? " chat-bubble-image" : ""}`
    : message.isError
      ? "chat-bubble chat-bubble-error"
      : `chat-bubble chat-bubble-assistant${sources.length ? " chat-bubble-with-sources" : ""}`;

  return (
    <article className={turnClassName}>
      <div className={avatarClassName}>
        <img
          src={isUser ? userAvatarUrl : chatBotUrl}
          alt={isUser ? t.userLabel : t.botName}
        />
      </div>
      <div className="chat-message-stack">
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
              {message.text && sources.length ? (
                <TextWithInlineSources
                  className={
                    message.image ? "message-text message-text-under-media" : ""
                  }
                  sources={sources}
                  text={message.text}
                />
              ) : message.text ? (
                <span
                  className={
                    message.image ? "message-text message-text-under-media" : ""
                  }
                >
                  {message.text}
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
          message={message}
          t={t}
          onFeedback={onFeedback}
        />
      </div>
    </article>
  );
}

function MessageFeedback({ disabled, message, t, onFeedback }) {
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
  const containerClassName = disabled ? "message-feedback is-disabled" : "message-feedback";

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
        disabled={disabled}
        title={t.feedbackPositive}
        onClick={() => onFeedback?.(message, true)}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M2 21h4V9H2v12Zm20-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L13.17 1 6.59 7.59C6.22 7.95 6 8.45 6 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-2Z" />
        </svg>
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
        disabled={disabled}
        title={t.feedbackNegative}
        onClick={() => onFeedback?.(message, false)}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M22 3h-4v12h4V3ZM2 14c0 1.1.9 2 2 2h6.31l-.95 4.57-.03.32c0 .41.17.79.44 1.06L10.83 23l6.58-6.59c.37-.36.59-.86.59-1.41V5c0-1.1-.9-2-2-2H7c-.83 0-1.54.5-1.84 1.22L2.14 11.27c-.09.23-.14.47-.14.73v2Z" />
        </svg>
      </button>
    </div>
  );
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

function TextWithInlineSources({ className, sources, text }) {
  const match = text.match(/(\S+)(\s*)$/);

  if (!match) {
    return (
      <span className={className}>
        <span className="message-inline-tail">
          <SourceFavicons sources={sources} />
        </span>
      </span>
    );
  }

  const lastWord = match[1];
  const trailingWhitespace = match[2];
  const prefix = text.slice(
    0,
    text.length - lastWord.length - trailingWhitespace.length,
  );

  return (
    <span className={className}>
      {prefix}
      <span className="message-inline-tail">
        {lastWord}
        {trailingWhitespace}
        <SourceFavicons sources={sources} />
      </span>
    </span>
  );
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
