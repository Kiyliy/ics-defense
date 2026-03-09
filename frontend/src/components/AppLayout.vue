<template>
  <el-container class="app-shell">
    <AppSidebar
      v-model:isCollapse="isCollapse"
      :menu-items="menuItems"
      :active-menu="activeMenu"
      :readiness-label="readinessLabel"
      :agent-healthy="systemHealth.agent === 'healthy'"
    />
    <el-container class="main-shell">
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAgentStatus, getBackendHealth } from '../api/index.js'
import AppSidebar from './layout/AppSidebar.vue'

const route = useRoute()
const router = useRouter()
const isCollapse = ref(false)
const systemHealth = ref({
  backend: 'checking',
  agent: 'checking',
  backendTimestamp: null,
  agentDetails: null,
})

let healthTimer = null

const activeMenu = computed(() => route.path)

const menuItems = computed(() => {
  const layoutRoute = router.options.routes.find((r) => r.path === '/')
  if (!layoutRoute || !layoutRoute.children) return []
  return layoutRoute.children
    .filter((r) => r.meta && r.meta.title)
    .map((r) => ({
      path: '/' + r.path,
      title: r.meta.title,
      icon: r.meta.icon,
      group: r.meta.group || 'overview',
    }))
})

const readinessLabel = computed(() => {
  if (systemHealth.value.backend === 'healthy' && systemHealth.value.agent === 'healthy') {
    return 'Operational'
  }
  if (systemHealth.value.backend === 'degraded' || systemHealth.value.agent === 'degraded') {
    return 'Attention Needed'
  }
  return 'Checking'
})

async function refreshHealth() {
  const [backendResult, agentResult] = await Promise.allSettled([
    getBackendHealth(),
    getAgentStatus(),
  ])

  if (backendResult.status === 'fulfilled' && backendResult.value?.status === 'ok') {
    systemHealth.value.backend = 'healthy'
    systemHealth.value.backendTimestamp = backendResult.value.timestamp || null
  } else {
    systemHealth.value.backend = 'degraded'
    systemHealth.value.backendTimestamp = null
  }

  if (agentResult.status === 'fulfilled' && agentResult.value?.status === 'ok') {
    systemHealth.value.agent = 'healthy'
    systemHealth.value.agentDetails = agentResult.value
  } else {
    systemHealth.value.agent = 'degraded'
    systemHealth.value.agentDetails = null
  }
}

onMounted(() => {
  refreshHealth()
  healthTimer = window.setInterval(refreshHealth, 30000)
})

onBeforeUnmount(() => {
  if (healthTimer) {
    window.clearInterval(healthTimer)
    healthTimer = null
  }
})
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: var(--bg-page);
}

.main-shell {
  min-width: 0;
}

.app-main {
  padding: 24px;
  overflow-y: auto;
  background: var(--bg-page);
}
</style>
