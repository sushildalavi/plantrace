/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#06111f",
        panel: "#0b1629",
        "panel-2": "#10203a",
        "panel-3": "#17314f",
        edge: "#203551",
        "edge-bright": "#5ea4ff",
        primary: "#eef5ff",
        secondary: "#9eb3d1",
        muted: "#6f88a8",
        accent: {
          DEFAULT: "#4ea1ff",
          soft: "#78d0ff",
          dim: "#1d4ed8",
        },
        ok: "#2dd4bf",
        warn: "#fbbf24",
        bad: "#fb7185",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        display: [
          "Fraunces",
          "Iowan Old Style",
          "Palatino Linotype",
          "Georgia",
          "serif",
        ],
        mono: [
          "IBM Plex Mono",
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      letterSpacing: {
        tightest: "-0.04em",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(78, 161, 255, 0.24), 0 0 24px -6px rgba(78, 161, 255, 0.38)",
        "glow-soft": "0 0 0 1px rgba(78, 161, 255, 0.14), 0 0 28px -10px rgba(78, 161, 255, 0.22)",
        "inner-edge": "inset 0 1px 0 rgba(255,255,255,0.08)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.97)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "slide-down": {
          "0%": { opacity: "0", transform: "translateY(-8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.9)", opacity: "0.7" },
          "80%, 100%": { transform: "scale(2.4)", opacity: "0" },
        },
        "ticker": {
          "0%": { transform: "translateY(10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.52s cubic-bezier(0.22, 1, 0.36, 1) both",
        "fade-in": "fade-in 0.4s ease-out both",
        "scale-in": "scale-in 0.32s cubic-bezier(0.22, 1, 0.36, 1) both",
        "slide-down": "slide-down 0.32s cubic-bezier(0.22, 1, 0.36, 1) both",
        shimmer: "shimmer 1.6s linear infinite",
        "pulse-ring": "pulse-ring 1.6s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        ticker: "ticker 0.42s cubic-bezier(0.22, 1, 0.36, 1) both",
      },
    },
  },
  plugins: [],
};
