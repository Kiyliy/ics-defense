<template>
  <div>
    <div class="page-header">
      <div class="page-header-copy">
        <h2>攻击链分析</h2>
        <p class="page-subtitle">
          将关联告警、证据与处置决策聚合到同一链路中，帮助分析人员在更强上下文里理解威胁演进与响应路径。
        </p>
      </div>
      <div class="page-header-meta">
        <span>Evidence Driven</span>
        <span>{{ chains.length }} Chains</span>
      </div>
    </div>

    <el-card shadow="hover">
      <template #header>
        <div class="section-title">
          <span>攻击链总览</span>
          <small>Chain Correlation</small>
        </div>
      </template>

      <el-table
        :data="chains"
        v-loading="loading"
        stripe
        row-key="id"
        class="data-table"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="chain-detail">
              <div class="chain-section">
                <h4>关联告警</h4>
                <el-table :data="row.alerts || []" size="small" border>
                  <el-table-column prop="id" label="ID" width="80" />
                  <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
                  <el-table-column prop="severity" label="等级" width="100">
                    <template #default="{ row: alert }">
                      <el-tag :type="getSeverityTagType(alert.severity)" size="small">
                        {{ alert.severity }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="src_ip" label="源IP" width="140" />
                </el-table>
              </div>

              <div class="chain-section">
                <h4>证据 (Evidence)</h4>
                <pre class="detail-pre">{{ typeof row.evidence === 'string' ? row.evidence : JSON.stringify(row.evidence, null, 2) }}</pre>
              </div>

              <div class="chain-section">
                <h4>决策 (Decisions)</h4>
                <el-table :data="row.decisions || []" size="small" border>
                  <el-table-column prop="id" label="ID" width="80" />
                  <el-table-column label="动作/建议" min-width="220" show-overflow-tooltip>
                    <template #default="{ row: dec }">
                      {{ dec.recommendation || dec.action_type || '-' }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="status" label="状态" width="120">
                    <template #default="{ row: dec }">
                      <el-tag :type="getStatusTagType(dec.status)" size="small">
                        {{ dec.status }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="200">
                    <template #default="{ row: dec }">
                      <template v-if="dec.status === 'pending'">
                        <el-button type="success" size="small" @click="handleDecision(dec.id, 'accepted')">
                          批准
                        </el-button>
                        <el-button type="danger" size="small" @click="handleDecision(dec.id, 'rejected')">
                          拒绝
                        </el-button>
                      </template>
                      <span v-else class="muted-text">已处理</span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="攻击链名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="risk_level" label="风险等级" width="120">
          <template #default="{ row }">
            <el-tag :type="getRiskTagType(row.risk_level)" size="small">
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
import { normalizeAttackChain } from '../api/view-models.js'
import { getSeverityTagType, getRiskTagType, getStatusTagType } from '../utils/ui.js'

const chains = ref([])
const loading = ref(false)

async function fetchChains() {
  loading.value = true
  try {
    const res = await getAttackChains()
    chains.value = (res.chains || []).map(normalizeAttackChain)
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
    await fetchChains()
  } catch (err) {
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  fetchChains()
})
</script>

<style scoped>
.chain-detail {
  display: grid;
  gap: 18px;
  padding: 20px 8px 8px;
}

.chain-section h4 {
  margin-bottom: 10px;
  font-size: 0.92rem;
  color: #334155;
}

.muted-text {
  color: #94a3b8;
  font-size: 0.8rem;
}
</style>
