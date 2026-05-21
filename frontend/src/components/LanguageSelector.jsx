export function LanguageSelector({
  locale,
  locales,
  t,
  onLocaleChange,
  className = "",
}) {
  return (
    <label className={`language-select-wrap ${className}`.trim()}>
      <span className="sr-only">{t.languageLabel}</span>
      <select
        className="language-select"
        aria-label={t.languageLabel}
        value={locale}
        onChange={(event) => onLocaleChange(event.target.value)}
      >
        {locales.map((supportedLocale) => (
          <option key={supportedLocale.code} value={supportedLocale.code}>
            {supportedLocale.flag} {supportedLocale.name}
          </option>
        ))}
      </select>
    </label>
  );
}
