import { LanguageSelector } from "./LanguageSelector.jsx";
import { ThemeToggle } from "./ThemeToggle.jsx";

export function AppHeader({
  locale,
  locales,
  theme,
  t,
  onLocaleChange,
  onThemeToggle,
}) {
  return (
    <header className="topbar relative z-10 shadow-sm backdrop-blur-xl">
      <div className="topbar-inner mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <div className="min-w-0">
            <h1 className="brand-heading truncate">{t.appTitle}</h1>
            <p className="brand-kicker">{t.appSubtitle}</p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <div className="hidden items-center gap-2 md:flex">
            <a
              className="date-chip"
              href="https://www.ta2026.com/en/piano-dei-giochi/"
              target="_blank"
              rel="noreferrer"
            >
              {t.dateRange}
            </a>
            <a
              className="tag-chip"
              href="https://www.ta2026.com/en/"
              target="_blank"
              rel="noreferrer"
            >
              #TA2026
            </a>
          </div>
          <LanguageSelector
            className="language-select-desktop"
            locale={locale}
            locales={locales}
            t={t}
            onLocaleChange={onLocaleChange}
          />
          <ThemeToggle
            className="theme-toggle-desktop"
            theme={theme}
            t={t}
            onThemeToggle={onThemeToggle}
          />
        </div>
      </div>
    </header>
  );
}
