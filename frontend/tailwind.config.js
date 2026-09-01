/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      // Roles map to CSS custom properties defined in index.css, so light and
      // dark swap in one place and charts can use the same var() strings.
      colors: {
        surface: "var(--surface-1)",
        raised: "var(--surface-2)",
        sunken: "var(--surface-0)",
        line: "var(--border)",
        ink: "var(--text-primary)",
        inkmid: "var(--text-secondary)",
        inkmute: "var(--text-muted)",
        series1: "var(--series-1)",
        series2: "var(--series-2)",
        series3: "var(--series-3)",
        series4: "var(--series-4)",
        good: "var(--status-good)",
        warn: "var(--status-warning)",
        crit: "var(--status-critical)",
      },
      fontFamily: {
        sans: ['"Inter var"', "Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,0.04), 0 1px 3px rgba(0,0,0,0.06)",
        pop: "0 8px 24px -6px rgba(0,0,0,0.18)",
      },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
        risein: { "0%": { opacity: 0, transform: "translateY(4px)" }, "100%": { opacity: 1, transform: "none" } },
      },
      animation: {
        shimmer: "shimmer 1.4s infinite",
        risein: "risein .28s ease-out both",
      },
    },
  },
  plugins: [],
};
