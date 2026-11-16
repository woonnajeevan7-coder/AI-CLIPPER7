/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0B0B0F',
        surface: '#14141B',
        surfaceElevated: '#1A1A24',
        border: '#22222E',
        borderSubtle: '#181822',
        foreground: '#F4F4F8',
        muted: '#A1A1AA',
        accent: {
          DEFAULT: '#8B5CF6',
          hover: '#7C3AED',
          light: '#A78BFA',
          glow: 'rgba(139, 92, 246, 0.15)',
        },
        status: {
          success: '#10B981',
          warning: '#F59E0B',
          error: '#EF4444',
        },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['var(--font-mono)', 'JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        'accent-glow': '0 0 24px rgba(139, 92, 246, 0.35)',
        'accent-glow-sm': '0 0 12px rgba(139, 92, 246, 0.25)',
        'card-glow': '0 12px 36px -8px rgba(0, 0, 0, 0.65), 0 0 0 1px rgba(139, 92, 246, 0.15)',
        'card-glow-hover': '0 20px 48px -10px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(139, 92, 246, 0.4)',
        'radar-glow': '0 0 20px 2px rgba(16, 185, 129, 0.4)',
      },
      aspectRatio: {
        '9/16': '9 / 16',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'float-slow': {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-5px)' },
        },
        'pulse-subtle': {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.8', transform: 'scale(1.03)' },
        },
        wave1: {
          '0%, 100%': { height: '4px' },
          '50%': { height: '14px' },
        },
        wave2: {
          '0%, 100%': { height: '12px' },
          '50%': { height: '5px' },
        },
        wave3: {
          '0%, 100%': { height: '6px' },
          '50%': { height: '16px' },
        },
        wave4: {
          '0%, 100%': { height: '15px' },
          '50%': { height: '6px' },
        },
      },
      animation: {
        shimmer: 'shimmer 2.5s ease-in-out infinite',
        float: 'float-slow 4s ease-in-out infinite',
        'pulse-subtle': 'pulse-subtle 2.5s ease-in-out infinite',
        wave1: 'wave1 1s ease-in-out infinite',
        wave2: 'wave2 1.2s ease-in-out infinite 0.15s',
        wave3: 'wave3 0.9s ease-in-out infinite 0.3s',
        wave4: 'wave4 1.1s ease-in-out infinite 0.2s',
      },
    },
  },
  plugins: [],
};
