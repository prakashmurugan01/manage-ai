/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"]
      },
      colors: {
        ink: {
          950: "#070A0F",
          900: "#0B111B",
          800: "#111827",
          700: "#1F2937"
        }
      },
      boxShadow: {
        glow: "0 20px 80px rgba(20, 184, 166, 0.16)"
      }
    }
  },
  plugins: []
};
