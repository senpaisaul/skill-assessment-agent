/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          950: "#0b1215",
          900: "#0f181c",
          800: "#162025",
          700: "#1e2d33",
        },
        brand: {
          50: "#ecfdf5",
          400: "#2dd4bf",
          500: "#14b8a6",
          600: "#0d9488",
          700: "#0f766e",
        },
        accent: {
          400: "#fbbf24",
          500: "#eab308",
          600: "#ca8a04",
        },
        bloom: {
          1: "#f87171",
          2: "#fbbf24",
          3: "#34d399",
          4: "#38bdf8",
          5: "#a78bfa",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
