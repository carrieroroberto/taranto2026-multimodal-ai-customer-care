export const LOCALE_STORAGE_KEY = "tarai-locale";

export const SUPPORTED_LOCALES = [
  { code: "it", flag: "🇮🇹", name: "Italiano", htmlLang: "it", dir: "ltr" },
  { code: "en", flag: "🇬🇧", name: "English", htmlLang: "en", dir: "ltr" },
  { code: "es", flag: "🇪🇸", name: "Español", htmlLang: "es", dir: "ltr" },
  { code: "fr", flag: "🇫🇷", name: "Français", htmlLang: "fr", dir: "ltr" },
  { code: "ar", flag: "🇸🇦", name: "العربية", htmlLang: "ar", dir: "rtl" },
];

export const DEFAULT_LOCALE = "en";

export const translations = {
  it: {
    appTitle: "TarAI | Giochi del Mediterraneo",
    appSubtitle: "Assistente AI multimodale per Taranto 2026",
    pageTitle:
      "TarAI | Assistente AI multimodale per i Giochi del Mediterraneo 2026 a Taranto",
    dateRange: "21 AGO - 3 SET 2026",
    languageLabel: "Lingua",
    botName: "TARA",
    userLabel: "Utente",
    online: "Online",
    countdownLabel: "Mancano",
    countdownUnits: { days: "gg", hours: "h", minutes: "m", seconds: "s" },
    gamesStarted: "Giochi in corso",
    officialSiteAria: "Apri il sito ufficiale Taranto 2026",
    messageLabel: "Messaggio",
    messagePlaceholder: "Scrivi un messaggio",
    sendMessage: "Invia messaggio",
    stopMessage: "Interrompi risposta",
    uploadImage: "Invia immagine",
    removeImage: "Rimuovi immagine",
    recordAudio: "Registra audio",
    stopRecording: "Ferma registrazione",
    typing: "Risposta in preparazione",
    unavailableAnswer: "Risposta non disponibile.",
    errorPrefix: "Si è verificato un errore:",
    themeToLight: "Passa alla modalità chiara",
    themeToDark: "Passa alla modalità scura",
    welcomePrefix: "Ciao, sono",
    welcomeMiddle: "! Come posso aiutarti per i ",
    eventName: "Giochi del Mediterraneo 2026",
    welcomeSuffix: " a Taranto?",
  },

  en: {
    appTitle: "TarAI | Mediterranean Games",
    appSubtitle: "Multimodal AI Assistant for Taranto 2026",
    pageTitle:
      "TarAI | Multimodal AI Assistant for the Mediterranean Games Taranto 2026",
    dateRange: "21 AUG - 3 SEP 2026",
    languageLabel: "Language",
    botName: "TARA",
    userLabel: "User",
    online: "Online",
    countdownLabel: "Time left",
    countdownUnits: { days: "d", hours: "h", minutes: "m", seconds: "s" },
    gamesStarted: "Games in progress",
    officialSiteAria: "Open the official Taranto 2026 website",
    messageLabel: "Message",
    messagePlaceholder: "Write a message",
    sendMessage: "Send message",
    stopMessage: "Stop response",
    uploadImage: "Upload image",
    removeImage: "Remove image",
    recordAudio: "Record audio",
    stopRecording: "Stop recording",
    typing: "Preparing response",
    unavailableAnswer: "Answer unavailable.",
    errorPrefix: "An error occurred:",
    themeToLight: "Switch to light mode",
    themeToDark: "Switch to dark mode",
    welcomePrefix: "Hi, I am",
    welcomeMiddle: "! How can I help you with the ",
    eventName: "Mediterranean Games 2026",
    welcomeSuffix: " in Taranto?",
  },

  es: {
    appTitle: "TarAI | Juegos Mediterráneos",
    appSubtitle: "Asistente de IA multimodal para Taranto 2026",
    pageTitle:
      "TarAI | Asistente de IA multimodal para los Juegos Mediterráneos Taranto 2026",
    dateRange: "21 AGO - 3 SEP 2026",
    languageLabel: "Idioma",
    botName: "TARA",
    userLabel: "Usuario",
    online: "En línea",
    countdownLabel: "Faltan",
    countdownUnits: { days: "d", hours: "h", minutes: "m", seconds: "s" },
    gamesStarted: "Juegos en curso",
    officialSiteAria: "Abrir el sitio oficial de Taranto 2026",
    messageLabel: "Mensaje",
    messagePlaceholder: "Escribe un mensaje",
    sendMessage: "Enviar mensaje",
    stopMessage: "Detener respuesta",
    uploadImage: "Subir imagen",
    removeImage: "Quitar imagen",
    recordAudio: "Grabar audio",
    stopRecording: "Detener grabación",
    typing: "Preparando respuesta",
    unavailableAnswer: "Respuesta no disponible.",
    errorPrefix: "Se ha producido un error:",
    themeToLight: "Cambiar a modo claro",
    themeToDark: "Cambiar a modo oscuro",
    welcomePrefix: "Hola, soy",
    welcomeMiddle: ". ¿Cómo puedo ayudarte con los ",
    eventName: "Juegos Mediterráneos 2026",
    welcomeSuffix: " en Taranto?",
  },

  fr: {
    appTitle: "TarAI | Jeux Méditerranéens",
    appSubtitle: "Assistant IA multimodal pour Taranto 2026",
    pageTitle:
      "TarAI | Assistant IA multimodal pour les Jeux Méditerranéens Taranto 2026",
    dateRange: "21 AOÛT - 3 SEPT. 2026",
    languageLabel: "Langue",
    botName: "TARA",
    userLabel: "Utilisateur",
    online: "En ligne",
    countdownLabel: "Temps restant",
    countdownUnits: { days: "j", hours: "h", minutes: "min", seconds: "s" },
    gamesStarted: "Jeux en cours",
    officialSiteAria: "Ouvrir le site officiel Taranto 2026",
    messageLabel: "Message",
    messagePlaceholder: "Écrire un message",
    sendMessage: "Envoyer le message",
    stopMessage: "Arrêter la réponse",
    uploadImage: "Envoyer une image",
    removeImage: "Supprimer l’image",
    recordAudio: "Enregistrer un audio",
    stopRecording: "Arrêter l’enregistrement",
    typing: "Préparation de la réponse",
    unavailableAnswer: "Réponse non disponible.",
    errorPrefix: "Une erreur s’est produite :",
    themeToLight: "Passer au mode clair",
    themeToDark: "Passer au mode sombre",
    welcomePrefix: "Bonjour, je suis",
    welcomeMiddle: ". Comment puis-je vous aider pour les ",
    eventName: "Jeux Méditerranéens 2026",
    welcomeSuffix: " à Taranto ?",
  },

  ar: {
    appTitle: "TarAI | ألعاب المتوسط",
    appSubtitle: "مساعد ذكاء اصطناعي متعدد الوسائط لتارانتو 2026",
    pageTitle:
      "TarAI | مساعد ذكاء اصطناعي متعدد الوسائط لألعاب البحر الأبيض المتوسط 2026 في تارانتو",
    dateRange: "21 أغسطس - 3 سبتمبر 2026",
    languageLabel: "اللغة",
    botName: "TARA",
    userLabel: "المستخدم",
    online: "متصل",
    countdownLabel: "الوقت المتبقي",
    countdownUnits: { days: "ي", hours: "س", minutes: "د", seconds: "ث" },
    gamesStarted: "الألعاب جارية",
    officialSiteAria: "فتح الموقع الرسمي لتارانتو 2026",
    messageLabel: "رسالة",
    messagePlaceholder: "اكتب رسالة",
    sendMessage: "إرسال الرسالة",
    stopMessage: "إيقاف الرد",
    uploadImage: "إرسال صورة",
    removeImage: "إزالة الصورة",
    recordAudio: "تسجيل صوت",
    stopRecording: "إيقاف التسجيل",
    typing: "يتم تحضير الرد",
    unavailableAnswer: "الإجابة غير متاحة.",
    errorPrefix: "حدث خطأ:",
    themeToLight: "التبديل إلى الوضع الفاتح",
    themeToDark: "التبديل إلى الوضع الداكن",
    welcomePrefix: "مرحبًا، أنا",
    welcomeMiddle: "! كيف يمكنني مساعدتك بخصوص ",
    eventName: "ألعاب البحر الأبيض المتوسط 2026",
    welcomeSuffix: " في تارانتو؟",
  },
};

export function getLocaleConfig(locale) {
  return (
    SUPPORTED_LOCALES.find((supportedLocale) => supportedLocale.code === locale) ||
    SUPPORTED_LOCALES.find(
      (supportedLocale) => supportedLocale.code === DEFAULT_LOCALE,
    ) ||
    SUPPORTED_LOCALES[0]
  );
}

export function getInitialLocale() {
  if (typeof window === "undefined") {
    return DEFAULT_LOCALE;
  }

  const savedLocale = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  if (isSupportedLocale(savedLocale)) {
    return savedLocale;
  }

  const browserLanguages = navigator.languages?.length
    ? navigator.languages
    : [navigator.language];

  for (const browserLanguage of browserLanguages) {
    const locale = browserLanguage?.toLowerCase().split("-")[0];
    if (isSupportedLocale(locale)) {
      return locale;
    }
  }

  return DEFAULT_LOCALE;
}

function isSupportedLocale(locale) {
  return SUPPORTED_LOCALES.some(
    (supportedLocale) => supportedLocale.code === locale,
  );
}