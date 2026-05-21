export function ThemeToggle({ theme, t, onThemeToggle, className = "" }) {
  const isDarkTheme = theme === "dark";
  const label = isDarkTheme ? t.themeToLight : t.themeToDark;

  return (
    <button
      className={`theme-toggle ${className}`.trim()}
      type="button"
      aria-label={label}
      aria-pressed={isDarkTheme}
      title={label}
      onClick={onThemeToggle}
    >
      {isDarkTheme ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M20.2 14.7A7.8 7.8 0 0 1 9.3 3.8a8.3 8.3 0 1 0 10.9 10.9Z"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="4.2" stroke="currentColor" strokeWidth="2" />
      <path
        d="M12 2.8v2.1m0 14.2v2.1M4.4 4.4l1.5 1.5m12.2 12.2 1.5 1.5M2.8 12h2.1m14.2 0h2.1M4.4 19.6l1.5-1.5M18.1 5.9l1.5-1.5"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="2"
      />
    </svg>
  );
}
