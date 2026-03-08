<template>
  <el-container class="app-shell">
    <el-aside :width="isCollapse ? '84px' : '280px'" class="app-sidebar">
      <div class="brand-panel">
        <div class="brand-mark">
          <el-icon :size="20"><Warning /></el-icon>
        </div>
        <div v-show="!isCollapse" class="brand-copy">
          <strong>ICS Security</strong>
          <span>Industrial Defense Console</span>
        </div>
      </div>

      <div v-show="!isCollapse" class="brand-summary">
        <div>
          <span class="brand-summary-label">当前模块</span>
          <strong>{{ currentSection.title }}</strong>
        </div>
        <small>{{ currentSection.subtitle }}</small>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        router
        class="sidebar-menu"
      >
        <el-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :index="item.path"
          class="sidebar-menu-item"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>

      <div v-show="!isCollapse" class="sidebar-footer">
        <span>Cyber Defense Readiness</span>
        <strong>{{ readinessLabel }}</strong>
      </div>
    </el-aside>

    <el-container class="main-shell">
      <el-header class="app-header">
        <div class="header-left">
          <el-button class="collapse-btn" circle @click="isCollapse = !isCollapse">
            <el-icon :size="18">
              <Fold v-if="!isCollapse" />
              <Expand v-else />
            </el-icon>
          </el-button>
          <div>
            <div class="header-title">工控安全指挥决策平台</div>
            <div class="header-subtitle">标准化、可解释、具备现代化审美的防御运营工作台</div>
          </div>
        </div>

        <div class="header-right">
          <div class="status-cluster">
            <el-tooltip :content="backendStatusText" placement="bottom">
              <div class="status-pill">
                <span class="status-dot" :class="systemHealth.backend"></span>
                <span>Backend {{ statusLabel(systemHealth.backend) }}</span>
              </div>
            </el-tooltip>
            <el-tooltip :content="agentStatusText" placement="bottom">
              <div class="status-pill">
                <span class="status-dot" :class="systemHealth.agent"></span>
                <span>Agent {{ statusLabel(systemHealth.agent) }}</span>
              </div>
            </el-tooltip>
          </div>
        </div>
      </el-header>

      <el-main class="app-main page-shell">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAgentStatus, getBackendHealth } from '../api/index.js'

const route = useRoute()
const router = useRouter()
const isCollapse = ref(false)
const systemHealth = ref({
  backend: 'checking',
  agent: 'checking',
  backendTimestamp: null,
  agentDetails: null,
})

const routeDescriptions = {
  '/dashboard': '整合威胁态势、趋势与处置优先级。',
  '/alerts': '统一筛选、研判与联动处置高风险告警。',
  '/chains': '串联证据、决策与攻击链上下文。',
  '/chat': '结合 AI 助手进行安全问答与推演。',
  '/approval': '对高风险工具调用与决策执行进行双人审批。',
  '/audit': '回溯 trace、工具调用与模型行为链路。',
}

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
    }))
})

const currentSection = computed(() => ({
  title: route.meta?.title || '工控防御',
  subtitle: routeDescriptions[route.path] || '聚焦关键资产、防御链路与决策闭环。',
}))

const readinessLabel = computed(() => {
  if (systemHealth.value.backend === 'healthy' && systemHealth.value.agent === 'healthy') {
    return 'Operational'
  }
  if (systemHealth.value.backend === 'degraded' || systemHealth.value.agent === 'degraded') {
    return 'Attention Needed'
  }
  return 'Checking'
})

const backendStatusText = computed(() => {
  if (systemHealth.value.backend === 'healthy' && systemHealth.value.backendTimestamp) {
    return `后端健康检查成功，时间：${systemHealth.value.backendTimestamp}`
  }
  if (systemHealth.value.backend === 'degraded') {
    return '后端健康检查失败，请检查 Backend API 服务。'
  }
  return '正在检查后端状态...'
})

const agentStatusText = computed(() => {
  if (systemHealth.value.agent === 'healthy') {
    const details = systemHealth.value.agentDetails
    const serverCount = details?.mcp_servers?.length ?? 0
    return `Agent 可用，MCP 工具 ${serverCount} 个，运行中任务 ${details?.running_tasks ?? 0} 个`
  }
  if (systemHealth.value.agent === 'degraded') {
    return 'Agent 状态不可用，可能是服务未启动、跨域不可访问，或接口异常。'
  }
  return '正在检查 Agent 状态...'
})

function statusLabel(status) {
  if (status === 'healthy') return '正常'
  if (status === 'degraded') return '异常'
  return '检查中'
}

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
  background: transparent;
}

.app-sidebar {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px 18px;
  background:
    linear-gradient(180deg, rgba(4, 15, 28, 0.98), rgba(7, 17, 31, 0.96)),
    radial-gradient(circle at top left, rgba(79, 140, 255, 0.18), transparent 30%);
  border-right: 1px solid rgba(148, 163, 184, 0.12);
  box-shadow: inset -1px 0 0 rgba(255, 255, 255, 0.02);
  overflow: hidden;
}

.brand-panel {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px 10px;
}

.brand-mark {
  width: 46px;
  height: 46px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #2563eb, #38bdf8);
  color: #eff6ff;
  box-shadow: 0 16px 34px rgba(37, 99, 235, 0.35);
}

.brand-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.brand-copy strong {
  color: #f8fafc;
  font-size: 1.15rem;
  letter-spacing: -0.02em;
}

.brand-copy span {
  color: rgba(148, 163, 184, 0.92);
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.brand-summary {
  padding: 16px;
  border-radius: 20px;
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.14);
  color: #cbd5e1;
}

.brand-summary-label {
  display: block;
  margin-bottom: 8px;
  font-size: 0.76rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(148, 163, 184, 0.78);
}

.brand-summary strong {
  display: block;
  margin-bottom: 8px;
  font-size: 1rem;
  color: #f8fafc;
}

.brand-summary small {
  line-height: 1.6;
  color: rgba(203, 213, 225, 0.74);
}

.sidebar-menu {
  flex: 1;
  border: none;
  background: transparent;
}

:deep(.el-menu) {
  border-right: none;
  background: transparent;
}

:deep(.el-menu-item) {
  height: 52px;
  margin-bottom: 8px;
  border-radius: 16px;
  color: rgba(226, 232, 240, 0.72);
}

:deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
}

:deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.26), rgba(14, 165, 233, 0.18));
  color: #fff;
  box-shadow: inset 0 0 0 1px rgba(96, 165, 250, 0.24);
}

.sidebar-footer {
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(203, 213, 225, 0.74);
}

.sidebar-footer span {
  display: block;
  margin-bottom: 6px;
  font-size: 0.78rem;
}

.sidebar-footer strong {
  font-size: 1rem;
  color: #f8fafc;
}

.main-shell {
  min-width: 0;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 84px;
  padding: 18px 28px;
  background: rgba(255, 255, 255, 0.64);
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  backdrop-filter: blur(16px);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.collapse-btn {
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.8);
}

.header-title {
  margin-bottom: 4px;
  font-size: 1.2rem;
  font-weight: 700;
  color: #0f172a;
}

.header-subtitle {
  font-size: 0.84rem;
  color: #64748b;
}

.status-cluster {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.14);
  color: #0f172a;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #94a3b8;
  box-shadow: 0 0 0 6px rgba(148, 163, 184, 0.15);
}

.status-dot.healthy {
  background: #22c55e;
  box-shadow: 0 0 0 6px rgba(34, 197, 94, 0.16);
}

.status-dot.degraded {
  background: #ef4444;
  box-shadow: 0 0 0 6px rgba(239, 68, 68, 0.14);
}

.app-main {
  padding: 28px;
  overflow-y: auto;
  background: transparent;
}

@media (max-width: 1024px) {
  .app-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .header-right {
    width: 100%;
  }

  .status-cluster {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .app-main,
  .app-header,
  .app-sidebar {
    padding: 18px;
  }
}
</style>
