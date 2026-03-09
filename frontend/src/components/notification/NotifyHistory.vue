<template>
  <div class="notify-history">
    <el-table
      v-if="history.length > 0"
      :data="paginatedData"
      v-loading="loading"
      style="width: 100%"
      :show-header="true"
    >
      <el-table-column prop="time" label="时间" width="180">
        <template #default="{ row }">
          <span class="time-text">{{ row.time || row.created_at || '' }}</span>
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
    <div v-else-if="!loading" class="empty-state">
      <p class="empty-title">暂无发送记录</p>
      <p class="empty-desc">通知发送后将在此处显示历史记录</p>
    </div>

    <!-- Pagination -->
    <div v-if="totalCount > pageSize" class="pagination-row">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="totalCount"
        layout="prev, pager, next"
        small
        @current-change="fetchHistory"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getNotificationHistory } from '../../api'

const currentPage = ref(1)
const pageSize = 5
const history = ref([])
const totalCount = ref(0)
const loading = ref(false)

const paginatedData = computed(() => {
  // If the backend handles pagination, return all items directly
  // Otherwise, do client-side pagination as fallback
  if (totalCount.value > 0 && history.value.length <= pageSize) {
    return history.value
  }
  const start = (currentPage.value - 1) * pageSize
  return history.value.slice(start, start + pageSize)
})

async function fetchHistory() {
  loading.value = true
  try {
    const res = await getNotificationHistory({
      limit: pageSize,
      offset: (currentPage.value - 1) * pageSize,
    })
    history.value = res.history || []
    totalCount.value = res.total ?? history.value.length
  } catch (err) {
    console.error('Failed to fetch notification history:', err)
    history.value = []
    totalCount.value = 0
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchHistory()
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
