import { useEffect, useState } from "react";

import { chatBotUrl } from "../assets/index.js";

const GAMES_START_AT = new Date("2026-08-21T00:00:00+02:00").getTime();
const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export function ChatHeader({ t }) {
  return (
    <div className="chat-header">
      <div className="flex min-w-0 items-center gap-3">
        <div className="chat-header-avatar" aria-hidden="true">
          <img src={chatBotUrl} alt="" />
          <span className="chat-header-avatar-status" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="chat-bot-name truncate text-lg font-black leading-tight sm:text-xl">
              {t.botName}
            </h2>
          </div>
          <div className="chat-bot-status hidden items-center gap-2 text-sm font-medium leading-none sm:flex">
            <span className="h-2 w-2 rounded-full bg-emerald-400 ring-2 ring-emerald-100" />
            {t.online}
          </div>
        </div>
      </div>
      <GamesCountdown t={t} />
    </div>
  );
}

function GamesCountdown({ t }) {
  const [timeLeft, setTimeLeft] = useState(() => getTimeLeft());

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setTimeLeft(getTimeLeft());
    }, SECOND);

    return () => window.clearInterval(intervalId);
  }, []);

  if (timeLeft.total <= 0) {
    return <div className="countdown-status">{t.gamesStarted}</div>;
  }

  return (
    <a
      className="countdown"
      href="https://www.ta2026.com/en/"
      target="_blank"
      rel="noreferrer"
      aria-label={t.officialSiteAria}
    >
      <span className="countdown-label">{t.countdownLabel}</span>
      <CountdownUnit value={timeLeft.days} label={t.countdownUnits.days} />
      <CountdownUnit value={timeLeft.hours} label={t.countdownUnits.hours} />
      <CountdownUnit value={timeLeft.minutes} label={t.countdownUnits.minutes} />
      <CountdownUnit value={timeLeft.seconds} label={t.countdownUnits.seconds} />
    </a>
  );
}

function CountdownUnit({ value, label }) {
  return (
    <span className="countdown-unit">
      <span className="countdown-unit-inner">
        <strong>{String(value).padStart(2, "0")}</strong>
        <span>{label}</span>
      </span>
    </span>
  );
}

function getTimeLeft() {
  const total = Math.max(0, GAMES_START_AT - Date.now());

  return {
    total,
    days: Math.floor(total / DAY),
    hours: Math.floor((total % DAY) / HOUR),
    minutes: Math.floor((total % HOUR) / MINUTE),
    seconds: Math.floor((total % MINUTE) / SECOND),
  };
}
