/** @type {import('tailwindcss').Config} */

import animate from "tailwindcss-animate";
import { carbonTwMapping } from "./src/styles/carbon-tw-mapping";

export default {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      screens: {
        lg: "1055px",
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "system-ui", "ui-sans-serif", "sans-serif"],
      },
      colors: { cds: carbonTwMapping },
    },
  },
  plugins: [animate],
  corePlugins: { preflight: false },
};
