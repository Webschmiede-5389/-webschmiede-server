/** @type {import('tailwindcss').Config} */

export default {

  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],

  theme: {

    extend: {

      colors: {

        brand: {

          orange: "#FF6600",

          "orange-soft": "#FFF4ED",

          "orange-border": "#FFD4B8",

          ink: "#1A1A1A",

          muted: "#666666",

          bg: "#F5F5F5",

          border: "#E8E8E8",

        },

      },

      fontFamily: {

        sans: ["Inter", "system-ui", "sans-serif"],

      },

    },

  },

  plugins: [],

};

