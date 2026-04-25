/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Deep slate background, indigo brand, accents for proficiency levels
        bg: { 950: "#0a0a0f", 900: "#0f0f17", 800: "#1a1a25", 700: "#262635" },
        brand: {
          50: "#eef2ff",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
        },
        // Bloom-level color ramp (1=red, 5=emerald) for proficiency badges
        bloom: {
          1: "#ef4444",
          2: "#f59e0b",
          3: "#10b981",
          4: "#3b82f6",
          5: "#8b5cf6",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
