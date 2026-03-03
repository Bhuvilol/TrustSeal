module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['Space Grotesk', 'Segoe UI', 'sans-serif'],
        mono: ['IBM Plex Mono', 'Consolas', 'monospace']
      },
      colors: {
        surface: {
          900: '#081018',
          800: '#0f1d2a',
          700: '#152839',
          600: '#1d3348'
        },
        brand: {
          500: '#13b59c',
          400: '#2ec4af',
          300: '#58d5c3'
        },
        status: {
          gray: '#9ca3af',
          blue: '#60a5fa',
          yellow: '#fbbf24',
          green: '#22c55e',
          red: '#ef4444'
        }
      },
      boxShadow: {
        panel: '0 14px 40px rgba(2, 12, 21, 0.35)'
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: 0, transform: 'translateY(8px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' }
        }
      },
      animation: {
        'fade-up': 'fadeUp 0.35s ease-out both'
      }
    }
  },
  plugins: []
};
