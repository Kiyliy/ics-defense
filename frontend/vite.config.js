import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const frontendPort = Number(process.env.FRONTEND_PORT || 5173)
const backendTarget = process.env.VITE_API_TARGET || 'http://localhost:3000'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: frontendPort,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
})
