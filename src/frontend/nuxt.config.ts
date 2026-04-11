export default defineNuxtConfig({
  modules: ['@nuxtjs/tailwindcss', '@pinia/nuxt'],
  devtools: { enabled: false },
  ssr: false,
  runtimeConfig: {
    public: {
      apiUrl: 'http://localhost:5000/api',
    },
  },
  app: {
    head: {
      title: 'Briefer',
      meta: [
        { name: 'description', content: 'AI-powered news intelligence platform' },
      ],
    },
  },
})
