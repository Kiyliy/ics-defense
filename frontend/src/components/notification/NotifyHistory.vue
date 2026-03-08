<template>
  <div class="notify-history">
    <el-table
      v-if="history.length > 0"
      :data="paginatedData"
      style="width: 100%"
      :show-header="true"
    >
      <el-table-column prop="time" label="时间" width="180">
        <template #default="{ row }">
          <span class="time-text">{{ row.time }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="event" label="事件">
        <template #default="{ row }">
          <span class="event-text">{{ row.event }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="channel" label="渠道" width="120">
        <template #default="{ row }">
          <span class="channel-pill">{{ row.channel }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <span :class="['status-badge', row.status]">
            {{ row.status === 'success' ? '成功' : '失败' }}
          </span>
        </template>
      </el-table-column>
    </el-table>

    <!-- Empty State -->
    <div v-else class="empty-state">
      <p class="empty-title">暂无发送记录</p>
      <p class="empty-desc">通知发送后将在此处显示历史记录</p>
    </div>

    <!-- Pagination -->
    <div v-if="history.length > pageSize" class="pagination-row">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="history.length"
        layout="prev, pager, next"
        small
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const currentPage = ref(1)
const pageSize = 5

const history = ref([
  { id: 1, time: '2026-03-08 10:23:15', event: '高危告警：异常 Modbus 写入', channel: '飞书', status: 'success' },
  { id: 2, time: '2026-03-08 09:45:02', event: '审批请求：隔离 PLC-07', channel: '飞书', status: 'success' },
  { id: 3, time: '2026-03-07 18:30:44', event: '攻击链更新：CHAIN-0042', channel: '飞书', status: 'failed' },
  { id: 4, time: '2026-03-07 14:12:08', event: '分析完成：告警 #1024', channel: '飞书', status: 'success' },
  { id: 5, time: '2026-03-06 22:05:33', event: '高危告警：未授权固件更新', channel: '飞书', status: 'success' },
  { id: 6, time: '2026-03-06 16:40:11', event: '审批请求：阻断网络段 C', channel: '飞书', status: 'success' },
])

const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return history.value.slice(start, start + pageSize)
})
</script>

<style scoped>
.time-text {
  font-size: 0.84rem;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.event-text {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-primary);
}

.channel-pill {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  background: var(--accent-bg);
  color: var(--accent);
  font-size: 0.8rem;
  font-weight: 600;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: 0.78rem;
  font-weight: 700;
}

.status-badge.success {
  background: var(--success-bg);
  color: var(--success);
}

.status-badge.failed {
  background: var(--danger-bg);
  color: var(--danger);
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 24px;
  text-align: center;
}

.empty-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.empty-desc {
  font-size: 0.85rem;
  color: var(--text-muted);
}
</style>
