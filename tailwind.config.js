/** @type {import('tailwindcss').Config} */

import colors from "tailwindcss/colors";

export default {
  content: [
    "client/*.html",
    "client/*.{js,vue}",
    "client/components/**/*.{js,vue}",
    "client/partials/**/*.{js,vue}",
    "client/views/**/*.{js,vue}",
  ],
  darkMode: "selector",
  theme: {
    fontFamily: {
      sans: ["Poppins", "sans-serif"],
    },
    screens: {
      sm: "640px",
      md: "768px",
      lg: "1024px",
    },
    extend: {
      colors: {
        // Dynamic
        "theme-brand": "rgb(var(--theme-brand) / <alpha-value>)",
        "theme-background": "rgb(var(--theme-background) / <alpha-value>)",
        "theme-background-elevated":
          "rgb(var(--theme-background-elevated) / <alpha-value>)",
        "theme-panel": "rgb(var(--theme-panel) / <alpha-value>)",
        "theme-panel-strong":
          "rgb(var(--theme-panel-strong) / <alpha-value>)",
        "theme-nav": "rgb(var(--theme-nav) / <alpha-value>)",
        "theme-text": "rgb(var(--theme-text) / <alpha-value>)",
        "theme-text-muted": "rgb(var(--theme-text-muted) / <alpha-value>)",
        "theme-text-very-muted":
          "rgb(var(--theme-text-very-muted) / <alpha-value>)",
        "theme-accent": "rgb(var(--theme-accent) / <alpha-value>)",
        "theme-shadow": "rgb(var(--theme-shadow) / <alpha-value>)",
        "theme-border": "rgb(var(--theme-border) / <alpha-value>)",
        // Static
        "theme-success": colors.emerald[600],
        "theme-danger": colors.rose[600],
      },
    },
  },
  plugins: [],
};
