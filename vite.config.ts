import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'robots.txt'],
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,webp}'],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/images\.unsplash\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'unsplash-images',
              expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
        ],
      },
      manifest: {
        name: 'Neemuch Blink',
        short_name: 'NB Blink',
        description: 'Neemuch fastest grocery delivery — fresh produce in 10-20 minutes',
        theme_color: '#FFD400',
        background_color: '#101010',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        icons: [
          {
            src: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192"><rect width="192" height="192" rx="40" fill="%23FFD400"/><text x="50%" y="58%" dominant-baseline="middle" text-anchor="middle" font-family="Inter,sans-serif" font-weight="900" font-size="80" fill="%23101010">NB</text></svg>',
            sizes: '192x192',
            type: 'image/svg+xml',
          },
          {
            src: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" rx="100" fill="%23FFD400"/><text x="50%" y="58%" dominant-baseline="middle" text-anchor="middle" font-family="Inter,sans-serif" font-weight="900" font-size="220" fill="%23101010">NB</text></svg>',
            sizes: '512x512',
            type: 'image/svg+xml',
            purpose: 'any maskable',
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: { '@': '/src' },
  },
})
