/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ink: '#171717',
        canvas: '#F8F8F4',
        lime: {
          400: '#D8FF3E',
          500: '#c2f022',
        }
      }
    },
  },
  plugins: [],
}
