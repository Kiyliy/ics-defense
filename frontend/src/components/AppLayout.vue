<template>
  <el-container style="height: 100vh">
    <el-aside :width="isCollapse ? '64px' : '220px'" style="transition: width 0.3s">
      <div class="logo-area">
        <el-icon :size="24" color="#409eff"><Warning /></el-icon>
        <span v-show="!isCollapse" class="logo-text">ICS Security</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        router
        background-color="#001529"
        text-color="#ffffffb3"
        active-text-color="#409eff"
        class="sidebar-menu"
      >
        <el-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :index="item.path"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <el-icon
          class="collapse-btn"
          :size="20"
          @click="isCollapse = !isCollapse"
        >
          <Fold v-if="!isCollapse" />
          <Expand v-else />
        </el-icon>
        <span class="header-title">工控安全指挥决策平台</span>
        <div class="header-right">
          <el-space size="small" alignment="center">
            <el-tooltip :content="backendStatusText" placement="bottom">
              <el-tag :type="statusTagType(systemHealth.backend)" size="small">
                后端 {{ statusLabel(systemHealth.backend) }}
              </el-tag>
            </el-tooltip>
            <el-tooltip :content="agentStatusText" placement="bottom">
              <el-tag :type="statusTagType(systemHealth.agent)" size="small">
                Agent {{ statusLabel(systemHealth.agent) }}
              </el-tag>
            </el-tooltip>
          </el-space>
        </div>
      </el-header>

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
    }))
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

function statusTagType(status) {
  if (status === 'healthy') return 'success'
  if (status === 'degraded') return 'danger'
  return 'info'
}

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
.el-aside {
  background-color: #001529;
  overflow: hidden;
}

.logo-area {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-bottom: 1px solid #ffffff1a;
}

.logo-text {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.sidebar-menu {
  border-right: none;
}

.app-header {
  background: #fff;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  z-index: 10;
}

.collapse-btn {
  cursor: pointer;
  color: #606266;
}

.collapse-btn:hover {
  color: #409eff;
}

.header-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.header-right {
  margin-left: auto;
}

.app-main {
  background: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}
</style>
