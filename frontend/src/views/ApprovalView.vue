<template>
  <div>
    <div class="page-header">
      <h2>审批队列</h2>
    </div>

    <el-card shadow="hover">
      <template #header>
        <el-tabs v-model="activeTab" @tab-change="fetchApprovals">
          <el-tab-pane label="待审批" name="pending" />
          <el-tab-pane label="全部" name="all" />
        </el-tabs>
      </template>

      <el-table :data="approvals" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="trace_id" label="Trace ID" width="200" show-overflow-tooltip />
        <el-table-column prop="tool_name" label="工具名称" width="180" />
        <el-table-column prop="tool_args" label="工具参数" min-width="250">
          <template #default="{ row }">
            <el-popover placement="top-start" :width="400" trigger="hover">
              <template #reference>
                <span style="cursor: pointer; color: #409eff">
                  {{ truncateArgs(row.tool_args) }}
                </span>
              </template>
              <pre style="white-space: pre-wrap; font-size: 12px; max-height: 300px; overflow: auto">{{ formatArgs(row.tool_args) }}</pre>
            </el-popover>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'pending' ? 'warning' : row.status === 'approved' ? 'success' : 'danger'"
              size="small"
            >
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <template v-if="row.status === 'pending'">
              <el-button type="success" size="small" @click="handleApprove(row)">
                批准
              </el-button>
              <el-button type="danger" size="small" @click="handleReject(row)">
                拒绝
              </el-button>
            </template>
            <span v-else style="color: #909399; font-size: 12px">已处理</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 拒绝原因弹窗 -->
    <el-dialog v-model="rejectDialogVisible" title="拒绝原因" width="450px">
      <el-form>
        <el-form-item label="原因">
          <el-input
            v-model="rejectReason"
            type="textarea"
            :rows="3"
            placeholder="请输入拒绝原因..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="confirmReject" :disabled="!rejectReason.trim()">
          确认拒绝
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApprovals, respondApproval } from '../api'

const activeTab = ref('pending')
const approvals = ref([])
const loading = ref(false)
const rejectDialogVisible = ref(false)
const rejectReason = ref('')
const currentRejectItem = ref(null)

function statusLabel(status) {
  const map = { pending: '待审批', approved: '已批准', rejected: '已拒绝' }
  return map[status] || status
}

function truncateArgs(args) {
  const str = typeof args === 'string' ? args : JSON.stringify(args)
  return str.length > 60 ? str.slice(0, 60) + '...' : str
}

function formatArgs(args) {
  try {
    const obj = typeof args === 'string' ? JSON.parse(args) : args
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(args)
  }
}

async function fetchApprovals() {
  loading.value = true
  try {
    const params = activeTab.value === 'pending' ? { status: 'pending' } : {}
    const res = await getApprovals(params)
    approvals.value = res.approvals || []
  } catch (err) {
    console.error('Failed to fetch approvals:', err)
  } finally {
    loading.value = false
  }
}

async function handleApprove(item) {
  try {
    await ElMessageBox.confirm(`确认批准工具「${item.tool_name}」的执行请求？`, '确认批准', {
      confirmButtonText: '批准',
      cancelButtonText: '取消',
      type: 'info',
    })
    await respondApproval(item.id, 'approved')
    ElMessage.success('已批准')
    fetchApprovals()
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

function handleReject(item) {
  currentRejectItem.value = item
  rejectReason.value = ''
  rejectDialogVisible.value = true
}

async function confirmReject() {
  try {
    await respondApproval(currentRejectItem.value.id, 'rejected', rejectReason.value)
    ElMessage.success('已拒绝')
    rejectDialogVisible.value = false
    fetchApprovals()
  } catch (err) {
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  fetchApprovals()
})
</script>
