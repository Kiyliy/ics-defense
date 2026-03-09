<template>
  <div class="mcp-view">
    <PageBanner title="MCP 管理" subtitle="查看与管理 Model Context Protocol 服务器及工具注册状态">
      <template #right>
        <span>{{ connectedCount }}/{{ servers.length }} Connected</span>
      </template>
    </PageBanner>

    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="6" animated />
    </div>

    <div v-else-if="error" class="error-state">
      <p>Agent 服务不可用，无法获取 MCP 信息</p>
      <el-button size="small" @click="fetchData">重试</el-button>
    </div>

    <template v-else>
      <div class="server-grid">
        <div
          v-for="server in servers"
          :key="server.name"
          class="server-card"
          :class="{ 'server-card--offline': !server.connected }"
        >
          <div class="server-header">
            <div class="server-status-row">
              <span class="status-dot" :class="server.connected ? 'status-dot--on' : 'status-dot--off'" />
              <h3 class="server-name">{{ server.name }}</h3>
            </div>
            <span class="server-badge">{{ server.tools.length }} tools</span>
          </div>

          <div class="server-meta">
            <code class="server-cmd">{{ server.command }} {{ server.args.join(' ') }}</code>
          </div>

          <div v-if="server.tools.length" class="tool-list">
            <div
              v-for="tool in server.tools"
              :key="tool.name"
              class="tool-item"
              :class="{ 'tool-item--expanded': expandedTool === tool.name }"
              @click="toggleTool(tool.name)"
            >
              <div class="tool-header">
                <span class="tool-name">{{ tool.name }}</span>
                <span class="policy-tag" :class="'policy-tag--' + tool.policy">{{ tool.policy }}</span>
              </div>
              <p class="tool-desc">{{ tool.description }}</p>

              <transition name="expand">
                <div v-if="expandedTool === tool.name && tool.input_schema" class="tool-schema">
                  <div class="schema-title">参数</div>
                  <div
                    v-for="(prop, propName) in (tool.input_schema.properties || {})"
                    :key="propName"
                    class="schema-row"
                  >
                    <code class="prop-name">{{ propName }}</code>
                    <span class="prop-type">{{ prop.type || 'any' }}</span>
                    <span
                      v-if="(tool.input_schema.required || []).includes(propName)"
                      class="prop-required"
                    >required</span>
                    <span v-if="prop.description" class="prop-desc">{{ prop.description }}</span>
                  </div>
                </div>
              </transition>
            </div>
          </div>

          <div v-else class="no-tools">暂无注册工具</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import PageBanner from '../components/layout/PageBanner.vue'
import { getMcpServers } from '../api/index.js'

const servers = ref([])
const loading = ref(true)
const error = ref(false)
const expandedTool = ref(null)

const connectedCount = computed(() => servers.value.filter(s => s.connected).length)

function toggleTool(name) {
  expandedTool.value = expandedTool.value === name ? null : name
}

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const res = await getMcpServers()
    servers.value = res.servers || []
  } catch {
    error.value = true
    servers.value = []
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.mcp-view {
  display: flex;
  flex-direction: column;
}

.loading-state,
.error-state {
  padding: 40px;
  text-align: center;
  color: var(--text-muted, #9ca3af);
}

.error-state p {
  margin-bottom: 12px;
}

.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 16px;
}

.server-card {
  background: var(--bg-primary, #fff);
  border: 1px solid var(--border, rgba(0, 0, 0, 0.08));
  border-radius: var(--radius-md, 8px);
  padding: 20px;
  transition: border-color 0.2s;
}

.server-card:hover {
  border-color: var(--border-strong, rgba(0, 0, 0, 0.15));
}

.server-card--offline {
  opacity: 0.55;
}

.server-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.server-status-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot--on {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.4);
}

.status-dot--off {
  background: #ef4444;
}

.server-name {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary, #0a0a0a);
  margin: 0;
}

.server-badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: var(--radius-full, 999px);
  background: rgba(59, 130, 246, 0.08);
  color: var(--accent, #3b82f6);
}

.server-meta {
  margin-bottom: 14px;
}

.server-cmd {
  font-size: 0.75rem;
  color: var(--text-muted, #9ca3af);
  background: var(--bg-hover, #f3f4f6);
  padding: 3px 8px;
  border-radius: 4px;
  word-break: break-all;
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tool-item {
  padding: 10px 12px;
  border-radius: var(--radius-sm, 6px);
  background: var(--bg-page, #f8f9fa);
  cursor: pointer;
  transition: background 0.15s;
}

.tool-item:hover {
  background: var(--bg-hover, #f3f4f6);
}

.tool-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.tool-name {
  font-family: var(--font-mono, monospace);
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
}

.policy-tag {
  font-size: 0.68rem;
  font-weight: 700;
  padding: 1px 8px;
  border-radius: var(--radius-full, 999px);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.policy-tag--auto {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.policy-tag--notify {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.policy-tag--approve {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.tool-desc {
  font-size: 0.78rem;
  color: var(--text-secondary, #6b7280);
  margin: 4px 0 0;
  line-height: 1.4;
}

.tool-schema {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border, rgba(0, 0, 0, 0.06));
}

.schema-title {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-muted, #9ca3af);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 6px;
}

.schema-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 3px 0;
  flex-wrap: wrap;
}

.prop-name {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--accent, #3b82f6);
}

.prop-type {
  font-size: 0.72rem;
  color: var(--text-muted, #9ca3af);
  font-family: var(--font-mono, monospace);
}

.prop-required {
  font-size: 0.68rem;
  color: #dc2626;
  font-weight: 600;
}

.prop-desc {
  font-size: 0.72rem;
  color: var(--text-secondary, #6b7280);
  flex-basis: 100%;
}

.no-tools {
  font-size: 0.82rem;
  color: var(--text-muted, #9ca3af);
  text-align: center;
  padding: 12px;
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 500px;
}

@media (max-width: 900px) {
  .server-grid {
    grid-template-columns: 1fr;
  }
}
</style>
