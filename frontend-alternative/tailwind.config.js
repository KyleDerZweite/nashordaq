/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      'hex-bg': '#091428',
      'hex-gold': '#C8AA6E',
      'hex-bronze': '#A09B8C',
      'hex-magic': '#0AC8B9',
      'hex-zaun': '#E84057',
    },
    fontFamily: {
      sans: ['"Playfair Display"', '"Times New Roman"', 'serif'],
      mono: ['"JetBrains Mono"', '"Space Mono"', 'monospace'],
    },
    borderRadius: {
      none: '0px',
      sm: '0px',
      DEFAULT: '0px',
      md: '0px',
      lg: '0px',
      xl: '0px',
      '2xl': '0px',
      '3xl': '0px',
      full: '0px',
    },
    borderWidth: {
      0: '0px',
      DEFAULT: '2px',
      2: '2px',
      4: '4px',
      8: '8px',
    },
    boxShadow: {
      none: 'none',
      brutal: '6px 6px 0 0 #C8AA6E',
      danger: '6px 6px 0 0 #E84057',
      magic: '6px 6px 0 0 #0AC8B9',
    },
  },
  plugins: [],
}

