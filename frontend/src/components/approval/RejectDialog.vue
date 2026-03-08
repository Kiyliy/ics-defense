<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="拒绝确认"
    width="480px"
    class="reject-dialog"
    :append-to-body="true"
  >
    <div class="reject-dialog-content">
      <div class="reject-warning-banner">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        <div>
          <strong>确认拒绝此工具调用</strong>
          <p v-if="item">工具「{{ item.tool_name }}」的执行请求将被拒绝。</p>
        </div>
      </div>

      <div class="reject-form-group">
        <label class="reject-form-label">拒绝原因</label>
        <el-input
          v-model="reason"
          type="textarea"
          :rows="3"
          placeholder="请输入拒绝原因，以便后续审计追溯..."
        />
      </div>
    </div>
    <template #footer>
      <div class="reject-dialog-footer">
        <el-button @click="$emit('update:visible', false)">取消</el-button>
        <el-button type="danger" :disabled="!reason.trim()" @click="$emit('confirm', reason)">
          确认拒绝
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  item: { type: Object, default: null }
})

defineEmits(['update:visible', 'confirm'])

const reason = ref('')

watch(() => props.visible, (v) => {
  if (v) reason.value = ''
})
</script>

<style scoped>
.reject-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.reject-warning-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  border-radius: var(--radius-lg, 12px);
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.12);
  color: #dc2626;
}

.reject-warning-banner svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.reject-warning-banner strong {
  display: block;
  font-size: 0.92rem;
  color: #b91c1c;
  margin-bottom: 4px;
}

.reject-warning-banner p {
  font-size: 0.84rem;
  color: #991b1b;
  line-height: 1.5;
  margin: 0;
}

.reject-form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.reject-form-label {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-secondary, #6b7280);
}

.reject-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
