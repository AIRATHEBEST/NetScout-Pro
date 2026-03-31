/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  safelist: [
    { pattern: /bg-(blue|green|red|purple|yellow|orange)-\d+/ },
    { pattern: /text-(blue|green|red|purple|yellow|orange)-\d+/ },
  ],
  theme: { extend: {} },
  plugins: [],
}
