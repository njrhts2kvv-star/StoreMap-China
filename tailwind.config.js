import { createRequire } from 'module';
const require = createRequire(import.meta.url);

export default {
  content: ['./index.html', './src/**/*.{ts,tsx,js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          dji: '#00F0D1',
          insta: '#FEE600',
          dark: '#0A1726',
        },
        'app-bg': '#F2F4F6',
      },
      boxShadow: { glass: '0 8px 30px rgba(0,0,0,0.04)' },
      borderRadius: { xl2: '32px' },
      backdropBlur: { md: '12px' },
      keyframes: {
        markerPulse: {
          '0%, 100%': { transform: 'scale(1)', boxShadow: '0 0 0 0 rgba(34,197,94,0.35)' },
          '50%': { transform: 'scale(1.08)', boxShadow: '0 0 0 8px rgba(34,197,94,0)' },
        },
      },
      animation: {
        markerPulse: 'markerPulse 1.8s ease-out infinite',
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
};
