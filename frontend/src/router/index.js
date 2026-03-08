import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'

const routes = [
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/DashboardView.vue'),
        meta: { title: '仪表盘', icon: 'Monitor', group: 'overview' },
      },
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('../views/ChatView.vue'),
        meta: { title: 'AI 对话', icon: 'ChatDotRound', group: 'security' },
      },
      {
        path: 'alerts',
        name: 'Alerts',
        component: () => import('../views/AlertListView.vue'),
        meta: { title: '告警列表', icon: 'Bell', group: 'security' },
      },
      {
        path: 'chains',
        name: 'AttackChains',
        component: () => import('../views/AttackChainView.vue'),
        meta: { title: '攻击链', icon: 'Connection', group: 'security' },
      },
      {
        path: 'approval',
        name: 'Approval',
        component: () => import('../views/ApprovalView.vue'),
        meta: { title: '审批队列', icon: 'Checked', group: 'security' },
      },
      {
        path: 'agent-logs',
        name: 'AgentLogs',
        component: () => import('../views/AgentLogView.vue'),
        meta: { title: 'Agent 日志', icon: 'DataAnalysis', group: 'system' },
      },
      {
        path: 'notifications',
        name: 'Notifications',
        component: () => import('../views/NotificationView.vue'),
        meta: { title: '通知管理', icon: 'Notification', group: 'system' },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('../views/SettingsView.vue'),
        meta: { title: '设置', icon: 'Setting', group: 'system' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  document.title = to.meta.title
    ? `${to.meta.title} - ICS Security`
    : 'ICS Security'
})

export default router
