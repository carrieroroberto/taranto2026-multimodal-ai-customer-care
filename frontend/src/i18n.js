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
    appTitle: "T.A.L.O.S | Giochi del Mediterraneo",
    mobileAppTitle: "T.A.L.O.S. | Taranto 2026",
    appSubtitle: "Taranto 2026 AI Live Operator Support",
    pageTitle:
      "T.A.L.O.S. | Taranto 2026 AI Live Operator Support",
    dateRange: "21 AGO - 3 SET 2026",
    languageLabel: "Lingua",
    botName: "TALOS",
    userLabel: "Utente",
    online: "Online",
    countdownLabel: "Mancano",
    countdownUnits: { days: "g", hours: "h", minutes: "m", seconds: "s" },
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
    feedbackHelpful: "Ti è stato utile?",
    feedbackPositive: "Risposta utile",
    feedbackNegative: "Risposta non utile",
    feedbackSupportPrompt:
      "Mi dispiace che la risposta non sia stata soddisfacente. Se desideri, scrivi la tua email nella casella di testo per essere ricontattato da un operatore umano.",
    themeToLight: "Passa alla modalità chiara",
    themeToDark: "Passa alla modalità scura",
    clearChat: "Pulisci chat",
    welcomePrefix: "Ciao, sono",
    welcomeMiddle: "! Come posso aiutarti per i ",
    eventName: "Giochi del Mediterraneo 2026",
    welcomeSuffix: " a Taranto?",
    welcomeSuggestions: [
      "Cosa sono?",
      "Qual è il programma degli eventi?",
      "Quali città sono coinvolte?",
    ],
    ticketEmailPlaceholder: "Indirizzo email",
    ticketError: "Impossibile inviare il ticket.",
    ticketInvalidEmail: "Inserisci un indirizzo email valido.",
    ticketCancel: "Annulla",
  },

  en: {
    appTitle: "T.A.L.O.S | Mediterranean Games",
    mobileAppTitle: "T.A.L.O.S. | Taranto 2026",
    appSubtitle: "Taranto 2026 AI Live Operator Support",
    pageTitle:
      "T.A.L.O.S. | Taranto 2026 AI Live Operator Support",
    dateRange: "21 AUG - 3 SEP 2026",
    languageLabel: "Language",
    botName: "TALOS",
    userLabel: "User",
    online: "Online",
    countdownLabel: "Left",
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
    feedbackHelpful: "Was this helpful?",
    feedbackPositive: "Helpful answer",
    feedbackNegative: "Not helpful",
    feedbackSupportPrompt:
      "I'm sorry the answer was not satisfactory. If you wish, write your email in the text box to be contacted by a human operator.",
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
    ticketEmailPlaceholder: "Email address",
    ticketError: "Failed to send ticket.",
    ticketInvalidEmail: "Enter a valid email address.",
    ticketCancel: "Cancel",
  },

  es: {
    appTitle: "T.A.L.O.S | Juegos Mediterráneos",
    mobileAppTitle: "T.A.L.O.S. | Taranto 2026",
    appSubtitle: "Taranto 2026 AI Live Operator Support",
    pageTitle:
      "T.A.L.O.S. | Taranto 2026 AI Live Operator Support",
    dateRange: "21 AGO - 3 SEP 2026",
    languageLabel: "Idioma",
    botName: "TALOS",
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
    feedbackHelpful: "¿Te resultó útil?",
    feedbackPositive: "Respuesta utile",

    feedbackNegative: "Respuesta no útil",
    feedbackSupportPrompt:
      "Siento que la respuesta no haya sido satisfactoria. Si lo deseas, escribe tu correo electrónico en el cuadro de texto para que un operador humano te contacte.",
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
    ticketEmailPlaceholder: "Correo electrónico",
    ticketError: "Error al enviar la solicitud.",
    ticketInvalidEmail: "Introduce una dirección de correo válida.",
    ticketCancel: "Cancelar",
  },

  fr: {
    appTitle: "T.A.L.O.S | Jeux Méditerranéens",
    mobileAppTitle: "T.A.L.O.S. | Tarente 2026",
    appSubtitle: "Taranto 2026 AI Live Operator Support",
    pageTitle:
      "T.A.L.O.S. | Taranto 2026 AI Live Operator Support",
    dateRange: "21 AOÛT - 3 SEPT. 2026",
    languageLabel: "Langue",
    botName: "TALOS",
    userLabel: "Utilisateur",
    online: "En ligne",
    countdownLabel: "Restant",
    countdownUnits: { days: "j", hours: "h", minutes: "m", seconds: "s" },
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
    feedbackHelpful: "Cela vous a-t-il été utile ?",
    feedbackPositive: "Réponse utile",

    feedbackNegative: "Réponse non utile",
    feedbackSupportPrompt:
      "Je suis désolé que la réponse n'ait pas été satisfaisante. Si vous le souhaitez, écrivez votre adresse e-mail dans la zone de texte afin d'être recontacté par un opérateur humain.",
    themeToLight: "Passer au mode clair",
    themeToDark: "Passer au mode sombre",
    welcomePrefix: "Bonjour, je suis",
    welcomeMiddle: ". Comment puis-je vous aider pour les ",
    eventName: "Jeux Méditerranéens 2026",
    welcomeSuffix: " à Taranto ?",
    welcomeSuggestions: [
      "Qu’est-ce que c’est ?",
      "Quel est le programme des événements ?",
      "Quelles villes sono coinvolte ?",
    ],
    ticketEmailPlaceholder: "Adresse courriel",
    ticketError: "Échec de l'envoi de la demande.",
    ticketInvalidEmail: "Saisissez une adresse e-mail valide.",
    ticketCancel: "Annuler",
  },

  ar: {
    appTitle: "T.A.L.O.S | ألعاب المتوسط",
    mobileAppTitle: "T.A.L.O.S. | \u062A\u0627\u0631\u0627\u0646\u062A\u0648 2026",
    appSubtitle: "Taranto 2026 AI Live Operator Support",
    pageTitle:
      "T.A.L.O.S. | Taranto 2026 AI Live Operator Support",
    dateRange: "21 أغسطس - 3 سبتمبر 2026",
    languageLabel: "اللغة",
    botName: "TALOS",
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
    feedbackHelpful: "هل كان هذا مفيدًا؟",
    feedbackPositive: "إجابة مفيدة",
    feedbackNegative: "إجابة غير مفيدة",
    feedbackSupportPrompt:
      "نأسف لأن الإجابة لم تكن مُرضية. إذا رغبت، اكتب بريدك الإلكتروني في مربع النص ليتم التواصل معك من قبل موظف.",
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
    ticketEmailPlaceholder: "عنوان البريد الإلكتروني",
    ticketError: "فشل إرسال الطلب.",
    ticketInvalidEmail: "أدخل عنوان بريد إلكتروني صالحًا.",
    ticketCancel: "إلغاء",
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
