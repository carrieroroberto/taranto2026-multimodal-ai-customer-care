import { chatBotUrl, chatUserDarkUrl, chatUserUrl } from "../assets/index.js";

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
          message.text
        )}
      </div>
    </article>
  );
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
