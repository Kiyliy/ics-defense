<template>
  <div class="notification-view">
    <PageBanner title="通知管理" subtitle="配置告警通知渠道与推送规则，确保关键安全事件第一时间触达值守人员。">
      <template #right>
        <span>Notification Center</span>
      </template>
    </PageBanner>

    <!-- Section: Channels -->
    <section class="content-section">
      <h2 class="section-head">通知渠道</h2>
      <ChannelConfig />
    </section>

    <!-- Section: Rules -->
    <section class="content-section">
      <h2 class="section-head">通知规则</h2>
      <NotifyRules />
    </section>

    <!-- Section: History -->
    <section class="content-section">
      <h2 class="section-head">发送历史</h2>
      <NotifyHistory />
    </section>
  </div>
</template>

<script setup>
import PageBanner from '../components/layout/PageBanner.vue'
import ChannelConfig from '../components/notification/ChannelConfig.vue'
import NotifyRules from '../components/notification/NotifyRules.vue'
import NotifyHistory from '../components/notification/NotifyHistory.vue'
</script>

<style scoped>
.notification-view {
  display: flex;
  flex-direction: column;
}

.content-section {
  margin-bottom: 28px;
  padding: 24px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-primary);
}

.section-head {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}
</style>
