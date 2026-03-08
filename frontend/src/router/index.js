import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'
import DashboardView from '../views/DashboardView.vue'
import AlertListView from '../views/AlertListView.vue'
import AttackChainView from '../views/AttackChainView.vue'
import ChatView from '../views/ChatView.vue'
import ApprovalView from '../views/ApprovalView.vue'
import AuditView from '../views/AuditView.vue'

const routes = [
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: DashboardView,
        meta: { title: '指挥面板', icon: 'Monitor' },
      },
      {
        path: 'alerts',
        name: 'Alerts',
        component: AlertListView,
        meta: { title: '告警列表', icon: 'Bell' },
      },
      {
        path: 'chains',
        name: 'AttackChains',
        component: AttackChainView,
        meta: { title: '攻击链', icon: 'Connection' },
      },
      {
        path: 'chat',
        name: 'Chat',
        component: ChatView,
        meta: { title: 'AI 对话', icon: 'ChatDotRound' },
      },
      {
        path: 'approval',
        name: 'Approval',
        component: ApprovalView,
        meta: { title: '审批队列', icon: 'Checked' },
      },
      {
        path: 'audit',
        name: 'Audit',
        component: AuditView,
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
