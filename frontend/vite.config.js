import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

const frontendPort = Number(process.env.FRONTEND_PORT || 5173)
const backendTarget = process.env.VITE_API_TARGET || 'http://localhost:3002'

export default defineConfig({
  plugins: [
    vue(),
    ...(process.env.VITEST
      ? []
      : [
          AutoImport({
            resolvers: [ElementPlusResolver()],
          }),
          Components({
            resolvers: [ElementPlusResolver({ importStyle: 'css' })],
          }),
        ]),
  ],
  test: {
    environment: 'jsdom',
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('echarts')) return 'echarts'
          if (id.includes('element-plus/es/components')) {
            const match = id.match(/element-plus\/es\/components\/([^/]+)/)
            return match ? `ep-${match[1]}` : 'element-plus'
          }
          if (id.includes('element-plus')) return 'element-plus-core'
          if (id.includes('@element-plus/icons-vue')) return 'element-plus-icons'
          if (id.includes('vue') || id.includes('pinia') || id.includes('vue-router')) {
            return 'vue-vendor'
          }
        },
      },
    },
  },
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
