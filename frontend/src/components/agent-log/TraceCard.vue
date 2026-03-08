<template>
  <div class="trace-card" :class="{ expanded }">
    <div class="trace-card-header" @click="$emit('toggle')">
      <div class="trace-indicator">
        <div class="trace-dot" :class="statusClass"></div>
        <div class="trace-line"></div>
      </div>
      <div class="trace-info">
        <div class="trace-title-row">
          <span class="trace-id-badge">{{ shortId }}</span>
          <div class="trace-meta-chips">
            <span class="meta-chip events">{{ group.events.length }} 事件</span>
            <span class="meta-chip tokens" v-if="group.totalTokens">{{ fmtNum(group.totalTokens) }} tokens</span>
          </div>
        </div>
        <div class="trace-event-preview">
          <span
            v-for="t in group.eventTypes"
            :key="t"
            class="event-type-dot"
            :class="'dot-' + eventTypeCategory(t)"
            :title="t"
          ></span>
        </div>
        <div class="trace-time-row">
          <span class="trace-time">{{ formatTime(group.earliest) }}</span>
          <span class="trace-duration" v-if="group.duration">{{ group.duration }}</span>
        </div>
      </div>
      <div class="trace-expand-icon" :class="{ rotated: expanded }">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </div>
    </div>

    <Transition name="slide-down">
      <div v-if="expanded" class="trace-events">
        <EventNode
          v-for="(evt, idx) in group.events"
          :key="idx"
          :event="evt"
          :is-last="idx === group.events.length - 1"
          :expanded="isEventExpanded(group.trace_id, idx)"
          :category="eventTypeCategory(evt.event_type)"
          :max-tokens="group.maxTokens || 1"
          @toggle-detail="onToggleEventDetail(group.trace_id, idx)"
        />
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  shortTraceId,
  traceStatusClass,
  eventTypeCategory,
  formatTime,
  formatNumber,
} from '../../composables/useAgentLogs.js'
import EventNode from './EventNode.vue'

const props = defineProps({
  group: { type: Object, required: true },
  expanded: { type: Boolean, default: false },
  expandedEvents: { type: Set, default: () => new Set() },
})

const emit = defineEmits(['toggle', 'toggle-event-detail'])

const fmtNum = formatNumber
const shortId = computed(() => shortTraceId(props.group.trace_id))
const statusClass = computed(() => traceStatusClass(props.group))

function isEventExpanded(traceId, idx) {
  return props.expandedEvents.has(`${traceId}:${idx}`)
}

function onToggleEventDetail(traceId, idx) {
  emit('toggle-event-detail', traceId, idx)
}
</script>

<style scoped>
.trace-card {
  border: 1px solid var(--border, rgba(0, 0, 0, 0.08));
  border-radius: var(--radius-lg, 12px);
  background: var(--bg-primary, #fff);
  overflow: hidden;
  transition: border-color 0.25s var(--ease);
}

.trace-card:hover {
  border-color: var(--border-strong, rgba(0, 0, 0, 0.15));
}

.trace-card.expanded {
  border-color: var(--accent, #3b82f6);
}

.trace-card-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 22px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;
}

.trace-card-header:hover {
  background: var(--bg-hover, #f3f4f6);
}

.trace-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.trace-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 3px solid;
}

.trace-dot.dot-active {
  border-color: var(--accent, #3b82f6);
  background: rgba(59, 130, 246, 0.15);
}

.trace-dot.dot-success {
  border-color: #22c55e;
  background: rgba(34, 197, 94, 0.15);
}

.trace-dot.dot-error {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.15);
}

.trace-line {
  width: 2px;
  height: 12px;
  background: var(--border, rgba(0, 0, 0, 0.08));
  border-radius: 1px;
}

.trace-info {
  flex: 1;
  min-width: 0;
}

.trace-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.trace-id-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: var(--radius-md, 8px);
  background: var(--bg-page, #f8f9fa);
  color: var(--text-primary, #0a0a0a);
  font-size: 0.78rem;
  font-weight: 600;
  font-family: var(--font-mono, monospace);
  letter-spacing: 0.02em;
}

.trace-meta-chips {
  display: flex;
  gap: 8px;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: var(--radius-full, 999px);
  font-size: 0.75rem;
  font-weight: 600;
}

.meta-chip.events {
  background: rgba(99, 102, 241, 0.08);
  color: #6366f1;
}

.meta-chip.tokens {
  background: rgba(245, 158, 11, 0.08);
  color: #d97706;
}

.trace-event-preview {
  display: flex;
  gap: 4px;
  margin: 8px 0 4px;
}

.event-type-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  transition: transform 0.2s;
}

.event-type-dot:hover {
  transform: scale(1.5);
}

.dot-llm { background: #6366f1; }
.dot-tool { background: #f59e0b; }
.dot-decision { background: #22c55e; }
.dot-error { background: #ef4444; }
.dot-default { background: #9ca3af; }

.trace-time-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.trace-time {
  font-size: 0.78rem;
  color: var(--text-muted, #9ca3af);
}

.trace-duration {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 6px;
  background: rgba(59, 130, 246, 0.08);
  color: var(--accent, #3b82f6);
  font-size: 0.72rem;
  font-weight: 700;
}

.trace-expand-icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md, 8px);
  color: var(--text-muted, #9ca3af);
  transition: all 0.3s;
}

.trace-expand-icon.rotated {
  transform: rotate(180deg);
  color: var(--accent, #3b82f6);
}

.trace-events {
  padding: 0 22px 22px 22px;
  margin-left: 28px;
  border-top: 1px solid var(--border, rgba(0, 0, 0, 0.08));
}

/* Transitions */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  max-height: 0;
}

.slide-down-enter-to,
.slide-down-leave-from {
  opacity: 1;
  max-height: 2000px;
}

@media (max-width: 768px) {
  .trace-card-header {
    padding: 14px 16px;
  }
  .trace-events {
    margin-left: 12px;
    padding: 0 16px 16px;
  }
  .trace-meta-chips {
    display: none;
  }
}
</style>
