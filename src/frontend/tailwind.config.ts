import type { Config } from 'tailwindcss'

export default {
  content: [
    './components/**/*.vue',
    './layouts/**/*.vue',
    './pages/**/*.vue',
    './composables/**/*.ts',
    './app.vue',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#2563eb',
        'primary-light': '#eff6ff',
        danger: '#dc2626',
        'danger-light': '#fef2f2',
        surface: '#fafbfc',
        'surface-card': '#ffffff',
        border: '#e5e7eb',
        'text-primary': '#111827',
        'text-secondary': '#6b7280',
        'text-muted': '#9ca3af',
      },
    },
  },
} satisfies Config
