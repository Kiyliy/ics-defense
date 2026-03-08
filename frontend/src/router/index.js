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
        meta: { title: '指挥面板', icon: 'Monitor' },
      },
      {
        path: 'alerts',
        name: 'Alerts',
        component: () => import('../views/AlertListView.vue'),
        meta: { title: '告警列表', icon: 'Bell' },
      },
      {
        path: 'chains',
        name: 'AttackChains',
        component: () => import('../views/AttackChainView.vue'),
        meta: { title: '攻击链', icon: 'Connection' },
      },
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('../views/ChatView.vue'),
        meta: { title: 'AI 对话', icon: 'ChatDotRound' },
      },
      {
        path: 'approval',
        name: 'Approval',
        component: () => import('../views/ApprovalView.vue'),
        meta: { title: '审批队列', icon: 'Checked' },
      },
      {
        path: 'audit',
        name: 'Audit',
        component: () => import('../views/AuditView.vue'),
        meta: { title: '审计日志', icon: 'Document' },
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
