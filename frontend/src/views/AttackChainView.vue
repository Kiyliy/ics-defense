<template>
  <div>
    <div class="page-header">
      <h2>攻击链分析</h2>
    </div>

    <el-card shadow="hover">
      <el-table
        :data="chains"
        v-loading="loading"
        stripe
        style="width: 100%"
        row-key="id"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div style="padding: 16px 24px">
              <!-- 关联告警 -->
              <h4 style="margin-bottom: 8px; color: #606266">关联告警</h4>
              <el-table
                :data="row.alerts || []"
                size="small"
                border
                style="margin-bottom: 16px"
              >
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
                <el-table-column prop="severity" label="等级" width="100">
                  <template #default="{ row: alert }">
                    <el-tag :type="severityType(alert.severity)" size="small">
                      {{ alert.severity }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="src_ip" label="源IP" width="140" />
              </el-table>

              <!-- 证据 -->
              <h4 style="margin-bottom: 8px; color: #606266">证据 (Evidence)</h4>
              <el-card shadow="never" style="margin-bottom: 16px; background: #fafafa">
                <pre style="white-space: pre-wrap; font-size: 13px; line-height: 1.6">{{ typeof row.evidence === 'string' ? row.evidence : JSON.stringify(row.evidence, null, 2) }}</pre>
              </el-card>

              <!-- 决策 -->
              <h4 style="margin-bottom: 8px; color: #606266">决策 (Decisions)</h4>
              <el-table :data="row.decisions || []" size="small" border>
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="action" label="动作" min-width="200" show-overflow-tooltip />
                <el-table-column prop="status" label="状态" width="120">
                  <template #default="{ row: dec }">
                    <el-tag
                      :type="dec.status === 'approved' ? 'success' : dec.status === 'rejected' ? 'danger' : 'warning'"
                      size="small"
                    >
                      {{ dec.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="200">
                  <template #default="{ row: dec }">
                    <template v-if="dec.status === 'pending'">
                      <el-button
                        type="success"
                        size="small"
                        @click="handleDecision(dec.id, 'approved')"
                      >
                        批准
                      </el-button>
                      <el-button
                        type="danger"
                        size="small"
                        @click="handleDecision(dec.id, 'rejected')"
                      >
                        拒绝
                      </el-button>
                    </template>
                    <span v-else style="color: #909399; font-size: 12px">已处理</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="攻击链名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="risk_level" label="风险等级" width="120">
          <template #default="{ row }">
            <el-tag :type="riskType(row.risk_level)" size="small">
              {{ row.risk_level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="alert_count" label="告警数" width="100" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getAttackChains, updateDecision } from '../api'

const chains = ref([])
const loading = ref(false)

function severityType(severity) {
  const map = { critical: 'danger', high: 'warning', medium: '', low: 'info' }
  return map[severity] || 'info'
}

function riskType(level) {
  const map = { critical: 'danger', high: 'danger', medium: 'warning', low: 'success' }
  return map[level] || 'info'
}

async function fetchChains() {
  loading.value = true
  try {
    const res = await getAttackChains()
    chains.value = res.chains || []
  } catch (err) {
    console.error('Failed to fetch chains:', err)
  } finally {
    loading.value = false
  }
}

async function handleDecision(decisionId, status) {
  try {
    await updateDecision(decisionId, status)
    ElMessage.success('决策已更新')
    fetchChains()
  } catch (err) {
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  fetchChains()
})
</script>
