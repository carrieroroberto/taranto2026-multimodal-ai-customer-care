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
    closeImage: "Chiudi immagine",
    recordAudio: "Registra audio",
    stopRecording: "Ferma registrazione",
    cancelRecording: "Annulla registrazione",
    sendAudio: "Invia audio",
    audioMessage: "Messaggio audio",
    typing: "Risposta in preparazione",
    unavailableAnswer: "Risposta non disponibile.",
    stoppedResponse: "Richiesta interrotta.",
    errorPrefix: "Si è verificato un errore:",
    feedbackLabel: "Valuta risposta",
    feedbackPositive: "Risposta utile",
    feedbackNegative: "Risposta non utile",
    themeToLight: "Passa alla modalità chiara",
    themeToDark: "Passa alla modalità scura",
    welcomePrefix: "Ciao, sono",
    welcomeMiddle: "! Come posso aiutarti per i ",
    eventName: "Giochi del Mediterraneo 2026",
    welcomeSuffix: " a Taranto?",
    welcomeSuggestions: [
      "Cosa sono?",
      "Qual è il programma degli eventi?",
      "Quali città sono coinvolte?",
    ],
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
    closeImage: "Close image",
    recordAudio: "Record audio",
    stopRecording: "Stop recording",
    cancelRecording: "Cancel recording",
    sendAudio: "Send audio",
    audioMessage: "Audio message",
    typing: "Preparing response",
    unavailableAnswer: "Answer unavailable.",
    stoppedResponse: "Request stopped.",
    errorPrefix: "An error occurred:",
    feedbackLabel: "Rate answer",
    feedbackPositive: "Helpful answer",
    feedbackNegative: "Not helpful",
    themeToLight: "Switch to light mode",
    themeToDark: "Switch to dark mode",
    welcomePrefix: "Hi, I am",
    welcomeMiddle: "! How can I help you with the ",
    eventName: "Mediterranean Games 2026",
    welcomeSuffix: " in Taranto?",
    welcomeSuggestions: [
      "What are they?",
      "What is the event schedule?",
      "Which cities are involved?",
    ],
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
    closeImage: "Cerrar imagen",
    recordAudio: "Grabar audio",
    stopRecording: "Detener grabación",
    cancelRecording: "Cancelar grabacion",
    sendAudio: "Enviar audio",
    audioMessage: "Mensaje de audio",
    typing: "Preparando respuesta",
    unavailableAnswer: "Respuesta no disponible.",
    stoppedResponse: "Solicitud interrumpida.",
    errorPrefix: "Se ha producido un error:",
    feedbackLabel: "Valorar respuesta",
    feedbackPositive: "Respuesta útil",
    feedbackNegative: "Respuesta no útil",
    themeToLight: "Cambiar a modo claro",
    themeToDark: "Cambiar a modo oscuro",
    welcomePrefix: "Hola, soy",
    welcomeMiddle: ". ¿Cómo puedo ayudarte con los ",
    eventName: "Juegos Mediterráneos 2026",
    welcomeSuffix: " en Taranto?",
    welcomeSuggestions: [
      "¿Qué son?",
      "¿Cuál es el programa de eventos?",
      "¿Qué ciudades participan?",
    ],
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
    closeImage: "Fermer l’image",
    recordAudio: "Enregistrer un audio",
    stopRecording: "Arrêter l’enregistrement",
    cancelRecording: "Annuler l'enregistrement",
    sendAudio: "Envoyer l'audio",
    audioMessage: "Message audio",
    typing: "Préparation de la réponse",
    unavailableAnswer: "Réponse non disponible.",
    stoppedResponse: "Réponse interrompue.",
    errorPrefix: "Une erreur s’est produite :",
    feedbackLabel: "Évaluer la réponse",
    feedbackPositive: "Réponse utile",
    feedbackNegative: "Réponse non utile",
    themeToLight: "Passer au mode clair",
    themeToDark: "Passer au mode sombre",
    welcomePrefix: "Bonjour, je suis",
    welcomeMiddle: ". Comment puis-je vous aider pour les ",
    eventName: "Jeux Méditerranéens 2026",
    welcomeSuffix: " à Taranto ?",
    welcomeSuggestions: [
      "Qu’est-ce que c’est ?",
      "Quel est le programme des événements ?",
      "Quelles villes sont impliquées ?",
    ],
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
    closeImage: "إغلاق الصورة",
    recordAudio: "تسجيل صوت",
    stopRecording: "إيقاف التسجيل",
    cancelRecording: "Cancel recording",
    sendAudio: "Send audio",
    audioMessage: "Audio message",
    typing: "يتم تحضير الرد",
    unavailableAnswer: "الإجابة غير متاحة.",
    stoppedResponse: "تم إيقاف الطلب.",
    errorPrefix: "حدث خطأ:",
    feedbackLabel: "تقييم الإجابة",
    feedbackPositive: "إجابة مفيدة",
    feedbackNegative: "إجابة غير مفيدة",
    themeToLight: "التبديل إلى الوضع الفاتح",
    themeToDark: "التبديل إلى الوضع الداكن",
    welcomePrefix: "مرحبًا، أنا",
    welcomeMiddle: "! كيف يمكنني مساعدتك بخصوص ",
    eventName: "ألعاب البحر الأبيض المتوسط 2026",
    welcomeSuffix: " في تارانتو؟",
    welcomeSuggestions: [
      "ما هي؟",
      "ما هو برنامج الفعاليات؟",
      "ما المدن المشاركة؟",
    ],
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
