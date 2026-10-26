/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#F0F4F9',
          100: '#E1E9F2',
          200: '#B6C8DE',
          300: '#8AA7CA',
          400: '#4D75A8',
          500: '#234E85',
          600: '#1A3C67',
          700: '#142B4A', // Primary Navy
          800: '#0E1E34',
          900: '#091322',
          950: '#040A12',
        },
        aicte: {
          primary: '#142B4A',
          hover: '#0E1E34',
          light: '#F4F7FB',
          gold: '#C59B27',
          blue: '#1D4ED8',
        },
        slate: {
          bg: '#F4F7FB',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px 0 rgba(0, 0, 0, 0.03)',
        'subtle': '0 2px 6px -1px rgba(20, 43, 74, 0.06), 0 1px 4px -1px rgba(20, 43, 74, 0.04)',
        'dropdown': '0 10px 25px -5px rgba(20, 43, 74, 0.1), 0 8px 10px -6px rgba(20, 43, 74, 0.08)',
      }
    },
  },
  plugins: [],
}
