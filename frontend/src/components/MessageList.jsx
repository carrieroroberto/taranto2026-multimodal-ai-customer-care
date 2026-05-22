import { useEffect, useRef, useState } from "react";

import { chatBotUrl, chatUserDarkUrl, chatUserUrl } from "../assets/index.js";

const FALLBACK_SOURCE_ICON = "/icons/source-fallback.svg";

export function MessageList({ messages, listRef, mobileActionSlot, theme, t }) {
  return (
    <div
      ref={listRef}
      id="messageList"
      className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-8"
    >
      <div aria-live="polite">
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} theme={theme} t={t} />
        ))}
      </div>
      {mobileActionSlot}
    </div>
  );
}

function ChatMessage({ message, theme, t }) {
  const isUser = message.role === "user";
  const userAvatarUrl = theme === "dark" ? chatUserDarkUrl : chatUserUrl;
  const sources = getVisibleSources(message, isUser);
  const turnClassName = isUser ? "chat-turn chat-turn-user" : "chat-turn";
  const avatarClassName = isUser
    ? "chat-avatar chat-avatar-user"
    : "chat-avatar chat-avatar-assistant";
  const bubbleClassName = isUser
    ? "chat-bubble chat-bubble-user"
    : message.isError
      ? "chat-bubble chat-bubble-error"
      : "chat-bubble chat-bubble-assistant";

  return (
    <article className={turnClassName}>
      <div className={avatarClassName}>
        <img
          src={isUser ? userAvatarUrl : chatBotUrl}
          alt={isUser ? t.userLabel : t.botName}
        />
      </div>
      <div className={bubbleClassName}>
        {message.isLoading ? (
          <TypingIndicator label={t.typing} />
        ) : message.translationKey === "welcome" ? (
          <WelcomeMessage t={t} />
        ) : (
          <>
            {message.image ? (
              <img
                className="message-image-preview"
                src={message.image}
                alt=""
                aria-hidden="true"
              />
            ) : null}
            {message.audio ? (
              <AudioWaveform audio={message.audio} label={t.audioMessage} />
            ) : null}
            {message.text}
            {sources.length ? (
              <>
                {" "}
                <SourceFavicons sources={sources} />
              </>
            ) : null}
          </>
        )}
      </div>
    </article>
  );
}

function SourceFavicons({ sources }) {
  return (
    <span className="source-favicons" aria-label="Sorgenti consultate">
      {sources.map((source, index) => (
        <a
          key={`${source.url}-${index}`}
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

  return message.sources
    .filter((source) => typeof source?.url === "string" && source.url.trim())
    .slice(0, 3);
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
