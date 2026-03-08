<template>
  <Transition name="float-bar">
    <div class="floating-toolbar" v-if="count > 0">
      <div class="floating-toolbar-inner">
        <div class="floating-count">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
          已选择 <strong>{{ count }}</strong> 条告警
        </div>
        <el-button type="warning" @click="$emit('analyze')" class="analyze-btn">
          <el-icon><MagicStick /></el-icon>
          AI 分析 ({{ count }})
        </el-button>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { MagicStick } from '@element-plus/icons-vue'

defineProps({
  count: { type: Number, default: 0 }
})

defineEmits(['analyze'])
</script>

<style scoped>
.floating-toolbar {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
}

.floating-toolbar-inner {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 12px 12px 12px 20px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.92);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(148, 163, 184, 0.15);
  color: #e2e8f0;
}

.floating-count {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.88rem;
  white-space: nowrap;
}

.floating-count strong {
  color: #93c5fd;
  font-size: 1rem;
}

.analyze-btn {
  white-space: nowrap;
}

.float-bar-enter-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.float-bar-leave-active {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.float-bar-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(24px);
}

.float-bar-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(16px);
}

@media (max-width: 768px) {
  .floating-toolbar-inner {
    flex-direction: column;
    gap: 12px;
  }
}
</style>
