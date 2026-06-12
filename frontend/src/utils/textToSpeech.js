let speechPrimed = false;

export function primeTextToSpeech(language) {
  const speech = getSpeechSynthesis();
  if (!speech || typeof SpeechSynthesisUtterance === "undefined" || speechPrimed) {
    return;
  }

  loadSpeechVoices();

  const utterance = new SpeechSynthesisUtterance(".");
  const speechLanguage = getSpeechLanguage(language);
  utterance.lang = speechLanguage;
  utterance.volume = 0;
  utterance.rate = 1;
  utterance.pitch = 1;

  const voice = findPreferredSpeechVoice(speechLanguage);
  if (voice) {
    utterance.voice = voice;
  }

  utterance.onend = () => {
    speechPrimed = true;
  };
  utterance.onerror = () => {
    speechPrimed = true;
  };

  try {
    speech.cancel();
    speech.speak(utterance);
    speech.resume?.();
    window.setTimeout(() => {
      speech.cancel();
      speechPrimed = true;
    }, 120);
  } catch (_error) {
    speechPrimed = true;
  }
}

export function speakTextOnce(text, language, options = {}) {
  const speechText = normalizeSpeechText(text);
  const speech = getSpeechSynthesis();
  if (!speechText || !speech || typeof SpeechSynthesisUtterance === "undefined") {
    options.onEnd?.();
    return;
  }

  const speechLanguage = getSpeechLanguage(language);
  let didStart = false;
  let didFinish = false;

  const notifyStart = () => {
    if (didStart) {
      return;
    }
    didStart = true;
    options.onStart?.();
  };

  const notifyEnd = () => {
    if (didFinish) {
      return;
    }
    didFinish = true;
    options.onEnd?.();
  };

  function speakNow() {
    const utterance = new SpeechSynthesisUtterance(speechText);
    utterance.lang = speechLanguage;
    utterance.rate = 0.96;
    utterance.pitch = 1.04;

    const voice = findPreferredSpeechVoice(speechLanguage);
    if (voice) {
      utterance.voice = voice;
    }

    let resumeTimer = null;
    const clearResumeTimer = () => {
      if (resumeTimer) {
        window.clearInterval(resumeTimer);
        resumeTimer = null;
      }
    };

    utterance.onstart = notifyStart;
    utterance.onend = () => {
      clearResumeTimer();
      notifyEnd();
    };
    utterance.onerror = () => {
      clearResumeTimer();
      notifyEnd();
    };

    speech.cancel();
    speech.speak(utterance);
    speech.resume?.();
    notifyStart();

    resumeTimer = window.setInterval(() => {
      speech.resume?.();
    }, 250);

    window.setTimeout(clearResumeTimer, 3000);
  }

  const voices = loadSpeechVoices();
  if (voices.length) {
    window.requestAnimationFrame(speakNow);
    return;
  }

  const handleVoicesChanged = () => {
    window.speechSynthesis?.removeEventListener?.("voiceschanged", handleVoicesChanged);
    window.requestAnimationFrame(speakNow);
  };

  window.speechSynthesis?.addEventListener?.("voiceschanged", handleVoicesChanged);
  window.setTimeout(() => {
    window.speechSynthesis?.removeEventListener?.("voiceschanged", handleVoicesChanged);
    speakNow();
  }, 500);
}

export function isSupportedSpeechLanguage(language) {
  const normalized = String(language || "").toLowerCase().split("-")[0];
  return ["ar", "en", "es", "fr", "it"].includes(normalized);
}

function getSpeechSynthesis() {
  return typeof window !== "undefined" ? window.speechSynthesis : null;
}

function loadSpeechVoices() {
  return getSpeechSynthesis()?.getVoices?.() || [];
}

function normalizeSpeechText(text) {
  return String(text || "")
    .replace(/\[[^\]]+\]\([^)]+\)/g, "")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[*_`#>~-]+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function getSpeechLanguage(language) {
  const normalized = String(language || "").toLowerCase().split("-")[0];
  return {
    ar: "ar-SA",
    en: "en-US",
    es: "es-ES",
    fr: "fr-FR",
    it: "it-IT",
  }[normalized] || "en-US";
}

function findPreferredSpeechVoice(language) {
  const voices = loadSpeechVoices();
  if (!voices.length) {
    return null;
  }

  const languageCode = language.toLowerCase();
  const languagePrefix = languageCode.split("-")[0];

  return voices
    .map((voice) => ({
      voice,
      score: scoreVoice(voice, languageCode, languagePrefix),
    }))
    .sort((a, b) => b.score - a.score)[0]?.voice || null;
}

function scoreVoice(voice, languageCode, languagePrefix) {
  const name = String(voice.name || "").toLowerCase();
  const lang = String(voice.lang || "").toLowerCase();
  let score = 0;

  if (lang === languageCode) {
    score += 100;
  } else if (lang.startsWith(languagePrefix)) {
    score += 70;
  }

  if (languagePrefix === "it") {
    if (name.includes("elsa")) score += 120;
    if (name.includes("isabella")) score += 90;
    if (name.includes("federica")) score += 80;
    if (name.includes("alice")) score += 70;
    if (name.includes("lucia")) score += 60;
  }

  if (name.includes("natural") || name.includes("neural")) score += 35;
  if (name.includes("premium") || name.includes("enhanced")) score += 25;
  if (name.includes("microsoft")) score += 12;
  if (name.includes("apple")) score += 10;
  if (name.includes("google")) score += 8;

  return score;
}
