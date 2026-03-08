# ICS Defense Frontend Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the ICS Defense frontend from glass-morphism to clean white SaaS aesthetic (Vercel/Linear style), split oversized Vue files into small components (~150 lines each), add 2 new pages (Notifications, Settings), and rename Audit → Agent Logs.

**Architecture:** Component-first decomposition. Each View file becomes a thin orchestrator (~50-80 lines) that imports sub-components. Business logic extracted to composables. Global CSS redesigned with new design tokens. All existing functionality preserved.

**Tech Stack:** Vue 3 + Composition API, Element Plus, ECharts, Pinia, Axios, Vite

**Design doc:** `docs/plans/2026-03-08-frontend-redesign.md`

---

## Task 1: Redesign global.css — New Design System

**Files:**
- Modify: `src/styles/global.css`

**Step 1: Replace global.css with clean white design tokens**

Replace the entire file. Key changes:
- Remove dark/glass-morphism variables (`--app-bg: #07111f`, etc.)
- Remove body gradient backgrounds and `#app::before/::after` blur circles
- Remove `box-shadow` from cards, remove `backdrop-filter`
- Add new clean tokens matching the design doc
- Keep Element Plus overrides but update to white style

```css
:root {
  /* ── Page ── */
  --bg-page: #f8f9fa;
  --bg-primary: #ffffff;
  --bg-hover: #f3f4f6;
  --bg-active: #e5e7eb;

  /* ── Border ── */
  --border: rgba(0, 0, 0, 0.08);
  --border-strong: rgba(0, 0, 0, 0.15);

  /* ── Text ── */
  --text-primary: #0a0a0a;
  --text-secondary: #6b7280;
  --text-muted: #9ca3af;

  /* ── Accent ── */
  --accent: #3b82f6;
  --accent-bg: rgba(59, 130, 246, 0.08);

  /* ── Semantic ── */
  --success: #22c55e;
  --success-bg: rgba(34, 197, 94, 0.08);
  --warning: #f59e0b;
  --warning-bg: rgba(245, 158, 11, 0.08);
  --danger: #ef4444;
  --danger-bg: rgba(239, 68, 68, 0.08);
  --info: #6366f1;
  --info-bg: rgba(99, 102, 241, 0.08);

  /* ── Radius ── */
  --radius-lg: 12px;
  --radius-md: 8px;
  --radius-sm: 6px;
  --radius-full: 999px;

  /* ── Transition ── */
  --ease: cubic-bezier(0.4, 0, 0.2, 1);

  /* ── Font ── */
  --font-sans: 'Inter', -apple-system, system-ui, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

html, body, #app {
  min-height: 100%;
  font-family: var(--font-sans);
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
}

body {
  background: var(--bg-page);
}

a { color: inherit; text-decoration: none; }
button, input, textarea, select { font: inherit; }

/* ── Element Plus Overrides ── */
.el-card {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-lg) !important;
  background: var(--bg-primary) !important;
  box-shadow: none !important;
}

.el-card__header {
  border-bottom: 1px solid var(--border) !important;
  padding: 16px 20px !important;
}

.el-card__body { padding: 20px !important; }

.el-table {
  --el-table-border-color: var(--border);
  --el-table-header-bg-color: var(--bg-page);
  --el-table-row-hover-bg-color: var(--bg-hover);
  --el-table-current-row-bg-color: var(--bg-active);
}

.el-table th.el-table__cell {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.el-table td.el-table__cell { padding: 12px 0 !important; }

.el-button { border-radius: var(--radius-md) !important; font-weight: 600; }

.el-button--primary {
  background: var(--text-primary) !important;
  border-color: var(--text-primary) !important;
  color: #fff !important;
  box-shadow: none !important;
}

.el-button--primary:hover {
  background: #1a1a1a !important;
  border-color: #1a1a1a !important;
}

.el-button--warning {
  background: var(--warning) !important;
  border-color: var(--warning) !important;
  color: #fff !important;
  box-shadow: none !important;
}

.el-button--success {
  background: var(--success) !important;
  border-color: var(--success) !important;
  box-shadow: none !important;
}

.el-button--danger {
  background: var(--danger) !important;
  border-color: var(--danger) !important;
  box-shadow: none !important;
}

.el-input__wrapper,
.el-textarea__inner,
.el-select__wrapper {
  border-radius: var(--radius-md) !important;
  box-shadow: 0 0 0 1px var(--border-strong) inset !important;
}

.el-tag { border-radius: var(--radius-full) !important; font-weight: 600; }
.el-dialog { border-radius: var(--radius-lg) !important; overflow: hidden; }
.el-pagination { gap: 8px; }

/* ── Code blocks ── */
pre.code-block, .mono-surface {
  padding: 14px 16px;
  border-radius: var(--radius-md);
  background: #1a1a2e;
  color: #e2e8f0;
  font-size: 0.8rem;
  font-family: var(--font-mono);
  line-height: 1.7;
  overflow: auto;
}
```

**Step 2: Verify the app builds**

Run: `cd /root/kimi_dev/lunwen/ics-defense/frontend && npm run build`
Expected: Build succeeds (style changes only, no broken imports)

**Step 3: Commit**

```bash
git add src/styles/global.css
git commit -m "refactor: redesign global.css with clean white SaaS design tokens"
```

---

## Task 2: Split AppLayout into Layout + Sidebar + Header

**Files:**
- Create: `src/components/layout/AppSidebar.vue`
- Create: `src/components/layout/AppHeader.vue`
- Modify: `src/components/AppLayout.vue` (rewrite as thin shell importing sub-components)

**Step 1: Create AppSidebar.vue**

Extract sidebar from current AppLayout. Redesign with white background, grouped nav items, status dot at bottom. Props: `isCollapse`, `menuItems`, `activeMenu`, `readinessLabel`. Emits: `update:isCollapse`.

Nav groups structure:
```
Overview: Dashboard
Security Ops: AI Chat, Alerts, Attack Chains, Approval Queue
System: Agent Logs, Notifications, Settings
```

White sidebar style: `background: #fff`, right `border: 1px solid var(--border)`, active item = `#f3f4f6` bg, inactive = `var(--text-secondary)` text.

**Step 2: Create AppHeader.vue**

Extract header. Simplified: left = page title + subtitle, right = status dots. Props: `title`, `subtitle`, `systemHealth`. Height = 56px, bottom border only, white bg.

**Step 3: Rewrite AppLayout.vue**

Thin shell (~80 lines): imports AppSidebar + AppHeader, keeps health polling logic, passes props down.

**Step 4: Build and verify**

Run: `cd /root/kimi_dev/lunwen/ics-defense/frontend && npm run build`

**Step 5: Commit**

```bash
git add src/components/layout/ src/components/AppLayout.vue
git commit -m "refactor: split AppLayout into Sidebar + Header, apply white theme"
```

---

## Task 3: Update Router — Add New Routes + Nav Groups

**Files:**
- Modify: `src/router/index.js`
- Modify: `src/main.js` (register new icons: `Setting`, `Notification`, `DataAnalysis`)

**Step 1: Update router with all 8 routes**

```js
children: [
  { path: 'dashboard', name: 'Dashboard', component: () => import('../views/DashboardView.vue'), meta: { title: '仪表盘', icon: 'Monitor', group: 'overview' } },
  { path: 'chat', name: 'Chat', component: () => import('../views/ChatView.vue'), meta: { title: 'AI 对话', icon: 'ChatDotRound', group: 'security' } },
  { path: 'alerts', name: 'Alerts', component: () => import('../views/AlertListView.vue'), meta: { title: '告警列表', icon: 'Bell', group: 'security' } },
  { path: 'chains', name: 'AttackChains', component: () => import('../views/AttackChainView.vue'), meta: { title: '攻击链', icon: 'Connection', group: 'security' } },
  { path: 'approval', name: 'Approval', component: () => import('../views/ApprovalView.vue'), meta: { title: '审批队列', icon: 'Checked', group: 'security' } },
  { path: 'agent-logs', name: 'AgentLogs', component: () => import('../views/AgentLogView.vue'), meta: { title: 'Agent 日志', icon: 'DataAnalysis', group: 'system' } },
  { path: 'notifications', name: 'Notifications', component: () => import('../views/NotificationView.vue'), meta: { title: '通知管理', icon: 'Notification', group: 'system' } },
  { path: 'settings', name: 'Settings', component: () => import('../views/SettingsView.vue'), meta: { title: '设置', icon: 'Setting', group: 'system' } },
]
```

**Step 2: Register icons in main.js**

Add `Setting`, `Notification`, `DataAnalysis` to the icons object and import them.

**Step 3: Create placeholder views for new pages**

Create minimal `AgentLogView.vue`, `NotificationView.vue`, `SettingsView.vue` with just a `<div>placeholder</div>` to prevent build errors. These will be fully built in later tasks.

**Step 4: Build and verify**

Run: `cd /root/kimi_dev/lunwen/ics-defense/frontend && npm run build`

**Step 5: Commit**

```bash
git add src/router/index.js src/main.js src/views/AgentLogView.vue src/views/NotificationView.vue src/views/SettingsView.vue
git commit -m "feat: add routes for Agent Logs, Notifications, Settings pages"
```

---

## Task 4: Redesign Common Components — StatCard, EmptyState, StatusDot

**Files:**
- Modify: `src/components/StatCard.vue` (remove shadow, gradient, glassmorphism)
- Create: `src/components/common/EmptyState.vue`
- Create: `src/components/common/StatusDot.vue`

**Step 1: Redesign StatCard.vue**

Remove: gradient glow, sparkline SVG, shadow, `::after` pseudo-element, glassmorphism. Keep: animated number, icon, label, description.

New style: white bg, `border: 1px solid var(--border)`, `border-radius: 12px`, icon uses muted semantic color bg (8% opacity) with matching icon color (not white on gradient). Clean, flat.

**Step 2: Create EmptyState.vue**

Props: `icon` (slot), `title`, `description`. Centered layout, muted icon in soft circle, title + description text.

**Step 3: Create StatusDot.vue**

Props: `status` ('healthy'|'degraded'|'checking'). Renders a small colored circle with optional pulse animation.

**Step 4: Build and verify**

**Step 5: Commit**

```bash
git add src/components/StatCard.vue src/components/common/
git commit -m "refactor: redesign StatCard, add EmptyState and StatusDot components"
```

---

## Task 5: Split & Redesign DashboardView

**Files:**
- Create: `src/components/dashboard/TrendChart.vue` (extract ECharts logic)
- Create: `src/components/dashboard/SeverityChart.vue` (extract severity bar)
- Create: `src/components/dashboard/RecentAlertsList.vue` (extract alert list)
- Modify: `src/views/DashboardView.vue` (thin orchestrator ~80 lines)

**Step 1: Create TrendChart.vue**

Extract all ECharts setup, renderChart(), resize handling. Props: `trendData` (array). Component handles chart lifecycle internally.

Update chart tooltip to white theme: white bg, subtle border, dark text. Remove dark tooltip styling.

**Step 2: Create SeverityChart.vue**

Extract severity bar + legend. Props: `segments` (array of {label, count, color, pct}).

**Step 3: Create RecentAlertsList.vue**

Extract alert list rendering. Props: `alerts` (array). Emits: `viewAll`.

Remove: page-header dark banner. Replace with simple `<h1>` + subtitle.

Update all card styles: white bg, subtle border, no shadow, no glassmorphism.

**Step 4: Rewrite DashboardView.vue as thin orchestrator**

```vue
<template>
  <div>
    <h1 class="page-title">仪表盘</h1>
    <p class="page-desc">聚合风险告警、处置待办、攻击链与趋势分析</p>
    <div class="stats-grid">
      <StatCard v-for="card in statCards" :key="card.label" v-bind="card" />
    </div>
    <div class="charts-grid">
      <TrendChart :trend-data="trendData" />
      <SeverityChart :segments="severitySegments" />
    </div>
    <RecentAlertsList :alerts="recentAlerts" @view-all="$router.push('/alerts')" />
  </div>
</template>
```

Keep data fetching logic in the view (onMounted, computed for statCards/severitySegments).

**Step 5: Build and verify**

**Step 6: Commit**

```bash
git add src/components/dashboard/ src/views/DashboardView.vue
git commit -m "refactor: split DashboardView into TrendChart, SeverityChart, RecentAlertsList"
```

---

## Task 6: Split & Redesign ChatView

**Files:**
- Create: `src/components/chat/ConversationList.vue`
- Create: `src/components/chat/MessageBubble.vue`
- Create: `src/components/chat/StructuredResponse.vue`
- Create: `src/components/chat/ChatInput.vue`
- Create: `src/composables/useChat.js` (extract all chat state & logic)
- Modify: `src/views/ChatView.vue` (thin orchestrator)

**Step 1: Create useChat.js composable**

Extract: `conversations`, `currentConvIndex`, `inputText`, `sending`, `currentMessages`, `parseAIResponse`, `newConversation`, `switchConversation`, `handleSend`, `scrollToBottom` from ChatView.

**Step 2: Create ConversationList.vue**

Props: `conversations`, `currentIndex`. Emits: `select`, `new`.

Redesign: white sidebar panel, subtle border, no shadow. Active item = `#f3f4f6` bg. "New conversation" button = outlined/ghost style (no gradient).

**Step 3: Create MessageBubble.vue**

Props: `message` ({role, content, _parsed}).

Redesign: User bubble = `#f3f4f6` bg (not blue gradient), dark text, right-aligned. AI bubble = white + subtle border, left-aligned. No shadows on bubbles.

**Step 4: Create StructuredResponse.vue**

Props: `parsed` (object with analysis, risk_level, mitre_*, recommendation, etc.)

Keep the structured card layout but update to white style: cards use border instead of colored backgrounds.

**Step 5: Create ChatInput.vue**

Props: `modelValue`, `sending`, `maxChars`. Emits: `update:modelValue`, `send`.

Redesign: remove gradient send button → use `#0a0a0a` bg button. Input border = `var(--border-strong)`, focus = `var(--accent)` border.

**Step 6: Rewrite ChatView.vue**

Thin orchestrator importing all sub-components + useChat composable.

**Step 7: Build and verify**

**Step 8: Commit**

```bash
git add src/components/chat/ src/composables/useChat.js src/views/ChatView.vue
git commit -m "refactor: split ChatView into composable + 4 sub-components"
```

---

## Task 7: Split & Redesign AlertListView

**Files:**
- Create: `src/components/alerts/AlertFilters.vue`
- Create: `src/components/alerts/AlertTable.vue`
- Create: `src/components/alerts/AlertDetailDrawer.vue`
- Create: `src/components/alerts/SelectionToolbar.vue`
- Modify: `src/views/AlertListView.vue` (thin orchestrator)

**Step 1: Create AlertFilters.vue**

Extract filter panel. Props: `filters` (reactive). Emits: `search`, `reset`.

Redesign: white bg, subtle border, no shadow/glassmorphism. Labels above inputs, uppercase small.

**Step 2: Create AlertTable.vue**

Extract table + pagination. Props: `alerts`, `loading`, `total`, `filters`. Emits: `selection-change`, `show-detail`, `page-change`, `size-change`.

Redesign: remove glassmorphism card wrapper → white bg + border. Severity dots keep semantic colors. Table header bg = `var(--bg-page)`.

**Step 3: Create AlertDetailDrawer.vue**

Extract detail dialog. Props: `visible`, `detail`. Emits: `update:visible`.

Code block redesign: keep dark code block (this is fine for contrast).

**Step 4: Create SelectionToolbar.vue**

Extract floating toolbar. Props: `count`. Emits: `analyze`.

Redesign: keep dark floating bar (it's a popover-like element, acceptable).

**Step 5: Rewrite AlertListView.vue**

Thin orchestrator, Pinia store stays in view.

**Step 6: Build and verify**

**Step 7: Commit**

```bash
git add src/components/alerts/ src/views/AlertListView.vue
git commit -m "refactor: split AlertListView into Filters, Table, Detail, Toolbar"
```

---

## Task 8: Split & Redesign AttackChainView

**Files:**
- Create: `src/components/chains/ChainCard.vue`
- Create: `src/components/chains/ChainTimeline.vue`
- Create: `src/components/chains/ChainEvidence.vue`
- Create: `src/components/chains/ChainActions.vue`
- Create: `src/composables/useChains.js`
- Modify: `src/views/AttackChainView.vue`

**Step 1: Create useChains.js**

Extract: `chains`, `loading`, `expandedId`, `fetchChains`, `handleDecision`, `toggleExpand`.

**Step 2: Create ChainCard.vue**

Props: `chain`, `expanded`. Emits: `toggle`.

Redesign: white bg, subtle border, no shadow. Risk badge keep semantic colors. Confidence bar → simple progress with muted track.

**Step 3: Create ChainTimeline.vue, ChainEvidence.vue, ChainActions.vue**

Extract expanded detail sections into separate components.

**Step 4: Rewrite AttackChainView.vue**

Thin orchestrator importing composable + sub-components.

**Step 5: Build and verify**

**Step 6: Commit**

```bash
git add src/components/chains/ src/composables/useChains.js src/views/AttackChainView.vue
git commit -m "refactor: split AttackChainView into ChainCard + sub-components"
```

---

## Task 9: Split & Redesign ApprovalView

**Files:**
- Create: `src/components/approval/ApprovalCard.vue`
- Create: `src/components/approval/ApprovalArgs.vue`
- Create: `src/components/approval/RejectDialog.vue`
- Create: `src/composables/useApproval.js`
- Modify: `src/views/ApprovalView.vue`

**Step 1: Create useApproval.js**

Extract: `approvals`, `loading`, `activeTab`, `pendingCount`, `allCount`, `expandedArgs`, `fetchApprovals`, `handleApprove`, `handleReject`, `confirmReject`, helper functions.

**Step 2: Create ApprovalCard.vue**

Props: `item`, `expandedArgs`. Emits: `approve`, `reject`, `toggle-args`.

Redesign: white card, subtle border, status left bar keeps semantic colors. Approve button → `#0a0a0a` bg. Reject button → ghost danger style (no gradient).

**Step 3: Create ApprovalArgs.vue + RejectDialog.vue**

Extract args expand/collapse section and rejection dialog.

**Step 4: Rewrite ApprovalView.vue**

Tab bar redesign: clean pill-style tabs, no shadow.

**Step 5: Build and verify**

**Step 6: Commit**

```bash
git add src/components/approval/ src/composables/useApproval.js src/views/ApprovalView.vue
git commit -m "refactor: split ApprovalView into ApprovalCard + sub-components"
```

---

## Task 10: Build AgentLogView (renamed from AuditView)

**Files:**
- Create: `src/components/agent-log/LogStatsRow.vue`
- Create: `src/components/agent-log/LogFilters.vue`
- Create: `src/components/agent-log/TraceCard.vue`
- Create: `src/components/agent-log/EventNode.vue`
- Create: `src/composables/useAgentLogs.js`
- Modify: `src/views/AgentLogView.vue` (full implementation replacing placeholder)
- Delete: `src/views/AuditView.vue` (after moving all logic)

**Step 1: Create useAgentLogs.js**

Extract ALL logic from current AuditView: `logs`, `auditStats`, `filters`, `loading`, `expandedTraces`, `expandedEvents`, `groupedLogs`, `totalTokens`, `totalLogCount`, ALL helper functions (formatNumber, parseTokens, eventTypeCategory, etc.).

Add new stats: `dataProcessed` computed (count of tool_call events as proxy for data processed).

**Step 2: Create LogStatsRow.vue**

4 stat cards: Analysis Count, Token Consumption (IN/OUT detail), Data Processed, Log Count.

Uses StatCard component. Clean white style.

**Step 3: Create LogFilters.vue**

Trace ID input + time range select + buttons. White bg, border, no shadow.

**Step 4: Create TraceCard.vue**

Single trace card with expandable event list. Props: `group`, `expanded`. Emits: `toggle`.

Redesign: white bg, subtle border. Trace ID badge = small mono text (not dark bg). Event type dots keep semantic colors.

**Step 5: Create EventNode.vue**

Single event in the timeline rail. Props: `event`, `isLast`, `expanded`, `category`. Emits: `toggle-detail`.

Keep: colored rail dots, token progress bars, expandable data preview.

**Step 6: Implement AgentLogView.vue**

Orchestrator: imports composable + sub-components. Watches route.query.

**Step 7: Remove old AuditView.vue**

Only after verifying the new page works.

**Step 8: Build and verify**

**Step 9: Commit**

```bash
git add src/components/agent-log/ src/composables/useAgentLogs.js src/views/AgentLogView.vue
git rm src/views/AuditView.vue
git commit -m "refactor: rename Audit to AgentLog, split into composable + sub-components"
```

---

## Task 11: Build NotificationView (new page)

**Files:**
- Create: `src/components/notification/ChannelConfig.vue`
- Create: `src/components/notification/NotifyRules.vue`
- Create: `src/components/notification/NotifyHistory.vue`
- Modify: `src/views/NotificationView.vue` (replace placeholder)
- Modify: `src/api/index.js` (add notification endpoints)

**Step 1: Add API endpoints**

```js
// Notifications
export const getNotificationChannels = () => request(http.get('/notifications/channels'))
export const saveNotificationChannel = (data) => request(http.post('/notifications/channels', data))
export const testNotificationChannel = (id) => request(http.post(`/notifications/channels/${id}/test`))
export const deleteNotificationChannel = (id) => request(http.delete(`/notifications/channels/${id}`))
export const getNotificationRules = () => request(http.get('/notifications/rules'))
export const saveNotificationRule = (data) => request(http.put('/notifications/rules', data))
export const getNotificationHistory = (params) => request(http.get('/notifications/history', { params }))
```

**Step 2: Create ChannelConfig.vue**

Displays configured channels (webhook URL masked, type label). Edit/Delete/Test buttons. Add channel form with type select + URL input.

Stub with local mock data for now (backend may not have these endpoints yet). Show empty state if no channels.

**Step 3: Create NotifyRules.vue**

Table/list of rules: Event type → Channel mapping with toggle switch. E.g.:
- 高危告警 → 飞书 [启用]
- 审批请求 → 飞书 [启用]
- 分析完成 → 飞书 [禁用]

**Step 4: Create NotifyHistory.vue**

Simple table: Time, Event, Channel, Status (success/failed).

**Step 5: Implement NotificationView.vue**

Three sections stacked vertically with `<h2>` section titles.

**Step 6: Build and verify**

**Step 7: Commit**

```bash
git add src/components/notification/ src/views/NotificationView.vue src/api/index.js
git commit -m "feat: add Notification management page with channel config, rules, history"
```

---

## Task 12: Build SettingsView (new page)

**Files:**
- Create: `src/components/settings/AgentConfig.vue`
- Create: `src/components/settings/SystemConfig.vue`
- Modify: `src/views/SettingsView.vue` (replace placeholder)
- Modify: `src/api/index.js` (add settings endpoints)

**Step 1: Add API endpoints**

```js
// Settings
export const getSettings = () => request(http.get('/settings'))
export const updateSettings = (data) => request(http.put('/settings', data))
```

**Step 2: Create AgentConfig.vue**

Form fields:
- Model selection (dropdown: gpt-4, claude-3, etc.)
- Temperature (slider 0-1)
- Max tokens (number input)
- MCP servers list (readonly display from agent status, or editable list)

**Step 3: Create SystemConfig.vue**

Form fields:
- Alert severity threshold for auto-escalation (dropdown)
- Auto-approval rules (toggle + conditions)
- Data source configuration (readonly display)

**Step 4: Implement SettingsView.vue**

Left tab navigation (vertical el-tabs): Agent Config | System Config.

**Step 5: Build and verify**

**Step 6: Commit**

```bash
git add src/components/settings/ src/views/SettingsView.vue src/api/index.js
git commit -m "feat: add Settings page with Agent and System configuration"
```

---

## Task 13: Update Tests

**Files:**
- Modify: `src/components/__tests__/AppLayout.test.js`
- Modify: `src/views/__tests__/*.test.js`

**Step 1: Update AppLayout tests**

Update selectors to match new component structure (AppSidebar, AppHeader imports).

**Step 2: Update view tests**

Update any tests that reference old class names or component structure. Ensure all existing test assertions still work with new component hierarchy.

**Step 3: Run all tests**

Run: `cd /root/kimi_dev/lunwen/ics-defense/frontend && npm test`
Expected: All tests pass

**Step 4: Commit**

```bash
git add -A
git commit -m "test: update tests for new component structure"
```

---

## Task 14: Final Cleanup & Visual Polish

**Files:**
- Remove: any unused old component files
- Review: all scoped styles for consistency with design system

**Step 1: Remove old AuditView test file if exists**

**Step 2: Verify all pages visually**

Run: `cd /root/kimi_dev/lunwen/ics-defense/frontend && npm run dev`

Check each page:
- Dashboard: white cards, no shadow, subtle borders
- Chat: white bubbles (user = gray bg, AI = white + border), no gradient buttons
- Alerts: clean table, white filter bar
- Attack Chains: white cards, colored risk badges
- Approval: white cards, clean tab bar
- Agent Logs: stat cards + timeline, white theme
- Notifications: three sections
- Settings: tabbed form

**Step 3: Fix any visual inconsistencies**

**Step 4: Final build check**

Run: `cd /root/kimi_dev/lunwen/ics-defense/frontend && npm run build`
Expected: No errors, no warnings

**Step 5: Commit**

```bash
git add -A
git commit -m "chore: final cleanup and visual polish for redesign"
```
