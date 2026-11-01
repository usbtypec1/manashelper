import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/admin/',
  build: { manifest: true },
  server: {
    proxy: { '/admin/api': { target: 'http://127.0.0.1:8080' } },
  },
})
