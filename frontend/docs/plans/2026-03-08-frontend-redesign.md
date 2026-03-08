# ICS Defense Frontend Redesign

## Goal

Redesign the entire frontend from a heavy glass-morphism style to a clean, white SaaS aesthetic (Vercel/Linear/OpenAI style). Split oversized Vue files (~1000 lines) into small composable components (~150 lines each).

---

## Visual Design System

### Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--bg-primary` | `#ffffff` | Cards, panels, sidebar |
| `--bg-page` | `#f8f9fa` | Page background |
| `--bg-hover` | `#f3f4f6` | Hover states |
| `--bg-active` | `#e5e7eb` | Active/selected states |
| `--border` | `rgba(0,0,0,0.08)` | Card borders, dividers |
| `--border-strong` | `rgba(0,0,0,0.15)` | Focused inputs |
| `--text-primary` | `#0a0a0a` | Headings, primary text |
| `--text-secondary` | `#6b7280` | Labels, descriptions |
| `--text-muted` | `#9ca3af` | Timestamps, metadata |
| `--accent` | `#3b82f6` | Primary actions, links |
| `--accent-bg` | `rgba(59,130,246,0.08)` | Accent backgrounds |
| `--success` | `#22c55e` | Success states |
| `--success-bg` | `rgba(34,197,94,0.08)` | Success backgrounds |
| `--warning` | `#f59e0b` | Warning states |
| `--warning-bg` | `rgba(245,158,11,0.08)` | Warning backgrounds |
| `--danger` | `#ef4444` | Danger states |
| `--danger-bg` | `rgba(239,68,68,0.08)` | Danger backgrounds |

### Typography

- Font: `Inter, -apple-system, system-ui, sans-serif`
- Mono: `JetBrains Mono, Fira Code, monospace`
- Hero numbers: `2rem / 800 / -0.04em`
- Section titles: `1.1rem / 600`
- Body: `0.875rem / 400`
- Labels: `0.75rem / 500 / uppercase / 0.04em tracking`

### Components

- **Cards**: `background: #fff`, `border: 1px solid rgba(0,0,0,0.08)`, `border-radius: 12px`, NO shadow
- **Buttons**: `border-radius: 8px`, primary = `#0a0a0a` bg + `#fff` text, secondary = ghost with border
- **Inputs**: `border-radius: 8px`, `border: 1px solid rgba(0,0,0,0.15)`, focus = accent border
- **Tags**: pill shape, semantic color bg at 8% opacity + matching text color
- **Tables**: no borders between cells, row hover = `#f9fafb`, header = uppercase small labels
- **Sidebar**: white bg, active item = `#f3f4f6` bg + `#0a0a0a` text, inactive = `#6b7280`

### No-Go List

- No box-shadow on cards (only on dropdowns/popovers, and even then minimal)
- No gradients except on chart areas
- No glass-morphism / backdrop-filter
- No bright saturated backgrounds
- No decorative borders or dividers — use spacing

---

## Layout

```
┌──────────┬─────────────────────────────────┐
│ Sidebar  │ Header                          │
│ 240px    ├─────────────────────────────────│
│ (64px    │ Content area                    │
│ collapsed│ max-width: 1400px               │
│          │ padding: 24px                   │
└──────────┴─────────────────────────────────┘
```

### Sidebar

- **Width**: 240px expanded, 64px collapsed
- **Background**: `#ffffff` with right border
- **Top**: Logo + product name "ICS Defense"
- **Nav groups**:
  - Overview: Dashboard
  - Security Ops: AI Chat, Alerts, Attack Chains, Approval Queue
  - System: Agent Logs, Notifications, Settings
- **Bottom**: Agent online/offline status dot
- **Collapse**: toggle button at bottom

### Header

- **Left**: Page title + subtitle
- **Right**: Backend health dot + agent status badge
- **Height**: 56px, bottom border

---

## Pages

### 1. Dashboard (`/dashboard`)

4 stat cards → trend chart + severity chart → recent alerts list.

Stat cards: icon with semantic muted bg on left, number + label on right, subtle border.

### 2. AI Chat (`/chat`)

Left panel (260px, collapsible): conversation list. Right: message area + input.

User messages: right-aligned, `#f3f4f6` bg. AI messages: left-aligned, white + border. Structured AI response (risk, MITRE, recommendations) rendered as inline card sections.

### 3. Alert List (`/alerts`)

Top: horizontal filter bar (severity, source, status). Body: clean table with severity color dot. Bottom: floating selection toolbar.

### 4. Attack Chains (`/chains`)

Card list, each card: risk color left bar + title + confidence + stage count. Expand to show vertical timeline + evidence + approve/reject actions.

### 5. Approval Queue (`/approval`)

Tabs: Pending / All. Card list with tool name, status tag, expandable args. Floating batch toolbar.

### 6. Agent Logs (`/agent-logs`)

Top: 4 stat cards (analysis count, token consumption, data processed, log count). Filter bar: trace ID + time range. Body: trace timeline with colored event nodes (LLM/Tool/Decision/Error), token progress bars.

### 7. Notifications (`/notifications`)

Three sections: Channel config (webhook URLs + test button), Notification rules (event → channel mapping with toggles), Send history (table).

### 8. Settings (`/settings`)

Left tab nav: Agent Config / System Config. Form layout with section dividers. Agent: model, temperature, MCP servers. System: alert thresholds, auto-approval rules, data sources.

---

## File Structure

```
src/
├── components/
│   ├── layout/
│   │   ├── AppLayout.vue              (~100 lines)
│   │   ├── AppSidebar.vue             (~150 lines)
│   │   └── AppHeader.vue              (~80 lines)
│   ├── common/
│   │   ├── StatCard.vue               (~120 lines)
│   │   ├── FilterBar.vue              (~100 lines)
│   │   ├── StatusDot.vue              (~30 lines)
│   │   ├── EmptyState.vue             (~50 lines)
│   │   └── TimelineNode.vue           (~80 lines)
│   ├── dashboard/
│   │   ├── StatsRow.vue
│   │   ├── TrendChart.vue
│   │   ├── SeverityChart.vue
│   │   └── RecentAlertsList.vue
│   ├── chat/
│   │   ├── ConversationList.vue
│   │   ├── MessageList.vue
│   │   ├── MessageBubble.vue
│   │   ├── StructuredResponse.vue
│   │   └── ChatInput.vue
│   ├── alerts/
│   │   ├── AlertFilters.vue
│   │   ├── AlertTable.vue
│   │   ├── AlertDetailDrawer.vue
│   │   └── SelectionToolbar.vue
│   ├── chains/
│   │   ├── ChainCard.vue
│   │   ├── ChainTimeline.vue
│   │   ├── ChainEvidence.vue
│   │   └── ChainActions.vue
│   ├── approval/
│   │   ├── ApprovalCard.vue
│   │   ├── ApprovalArgs.vue
│   │   └── RejectDialog.vue
│   ├── agent-log/
│   │   ├── LogStatsRow.vue
│   │   ├── LogFilters.vue
│   │   ├── TraceTimeline.vue
│   │   ├── TraceCard.vue
│   │   └── EventNode.vue
│   ├── notification/
│   │   ├── ChannelConfig.vue
│   │   ├── NotifyRules.vue
│   │   └── NotifyHistory.vue
│   └── settings/
│       ├── AgentConfig.vue
│       └── SystemConfig.vue
├── composables/
│   ├── useChat.js                     (chat state & logic)
│   ├── useAlerts.js                   (wraps Pinia store)
│   ├── useChains.js                   (chain data fetching)
│   ├── useApproval.js                 (approval actions)
│   └── useAgentLogs.js                (log fetching & filtering)
├── views/
│   ├── DashboardView.vue              (~60 lines, composition only)
│   ├── ChatView.vue                   (~60 lines)
│   ├── AlertListView.vue              (~50 lines)
│   ├── AttackChainView.vue            (~50 lines)
│   ├── ApprovalView.vue               (~50 lines)
│   ├── AgentLogView.vue               (~50 lines)
│   ├── NotificationView.vue           (~50 lines)
│   └── SettingsView.vue               (~50 lines)
├── styles/
│   └── global.css                     (redesigned design tokens)
├── router/
│   └── index.js                       (add new routes)
├── stores/
│   └── alert.js                       (keep, minor updates)
└── api/
    └── index.js                       (add notification/settings endpoints)
```

## Key Constraints

- Preserve ALL existing functionality — this is a visual + structural refactor only
- No new dependencies (use Element Plus + ECharts already installed)
- Every component uses `<script setup>` + Composition API
- All styles scoped — no global CSS pollution
- Existing tests must continue to pass (update selectors as needed)
