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
          saffron: '#FF9933',
          green: '#138808',
        },
        gov: {
          navy: '#0B1B3D',
          dark: '#071228',
          blue: '#1E40AF',
          lightBlue: '#EFF6FF',
          surface: '#F8FAFC',
          card: '#FFFFFF',
          border: '#E2E8F0',
          borderDark: '#CBD5E1',
          gold: '#C59B27',
          textMuted: '#64748B',
          textDark: '#0F1E33',
        },
        slate: {
          bg: '#F4F7FB',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgba(15, 30, 51, 0.05), 0 1px 2px 0 rgba(15, 30, 51, 0.03)',
        'subtle': '0 2px 6px -1px rgba(20, 43, 74, 0.06), 0 1px 4px -1px rgba(20, 43, 74, 0.04)',
        'elevated': '0 4px 12px -2px rgba(20, 43, 74, 0.08), 0 2px 6px -1px rgba(20, 43, 74, 0.05)',
        'dropdown': '0 10px 25px -5px rgba(20, 43, 74, 0.12), 0 8px 10px -6px rgba(20, 43, 74, 0.08)',
      }
    },
  },
  plugins: [],
}
