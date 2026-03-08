<template>
  <el-container style="height: 100vh">
    <el-aside :width="isCollapse ? '64px' : '220px'" style="transition: width 0.3s">
      <div class="logo-area">
        <el-icon :size="24" color="#409eff"><Shield /></el-icon>
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
          <el-tag type="success" size="small">系统运行中</el-tag>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const isCollapse = ref(false)

const activeMenu = computed(() => route.path)

const menuItems = [
  { path: '/dashboard', title: '指挥面板', icon: 'Monitor' },
  { path: '/alerts', title: '告警列表', icon: 'Bell' },
  { path: '/chains', title: '攻击链', icon: 'Connection' },
  { path: '/chat', title: 'AI 对话', icon: 'ChatDotRound' },
  { path: '/approval', title: '审批队列', icon: 'Checked' },
  { path: '/audit', title: '审计日志', icon: 'Document' },
]
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
