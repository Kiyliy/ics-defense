import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
  Bell,
  ChatDotRound,
  Checked,
  Connection,
  DataAnalysis,
  Document,
  Expand,
  Fold,
  Loading,
  Lock,
  MagicStick,
  Monitor,
  Notification,
  Plus,
  Promotion,
  Search,
  Setting,
  Warning,
} from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './styles/global.css'

const app = createApp(App)

const icons = {
  Bell,
  ChatDotRound,
  Checked,
  Connection,
  DataAnalysis,
  Document,
  Expand,
  Fold,
  Loading,
  Lock,
  MagicStick,
  Monitor,
  Notification,
  Plus,
  Promotion,
  Search,
  Setting,
  Warning,
}

for (const [key, component] of Object.entries(icons)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)

app.mount('#app')
