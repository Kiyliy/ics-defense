export const iconStubs = {
  Search: { template: '<i />' },
  MagicStick: { template: '<i />' },
  Loading: { template: '<i />' },
  Plus: { template: '<i />' },
  Promotion: { template: '<i />' },
  Warning: { template: '<i />' },
  Fold: { template: '<i />' },
  Expand: { template: '<i />' },
  Bell: { template: '<i />' },
  ChatDotRound: { template: '<i />' },
  Checked: { template: '<i />' },
  Connection: { template: '<i />' },
  Document: { template: '<i />' },
  Monitor: { template: '<i />' },
}

export const elementPlusStubs = {
  'el-card': { template: '<section><slot name="header" /><slot /></section>' },
  'el-table': { template: '<div><slot /></div>' },
  'el-table-column': {
    props: ['label', 'prop', 'type'],
    data() {
      return {
        rowFallback: {
          data: '',
          alerts: [],
          decisions: [],
          severity: '',
          status: '',
          risk_level: '',
        },
      }
    },
    template: '<div><slot :row="rowFallback" /><slot name="default" :row="rowFallback" /></div>',
  },
  'el-form': { template: '<form><slot /></form>' },
  'el-form-item': { template: '<div><slot /></div>' },
  'el-select': { template: '<div><slot /></div>' },
  'el-option': { template: '<option><slot /></option>' },
  'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
  'el-pagination': { template: '<nav><slot /></nav>' },
  'el-dialog': { template: '<div><slot name="header" /><slot /></div>' },
  'el-descriptions': { template: '<dl><slot /></dl>' },
  'el-descriptions-item': { template: '<div><slot /></div>' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-icon': { template: '<span><slot /></span>' },
  'el-row': { template: '<div><slot /></div>' },
  'el-col': { template: '<div><slot /></div>' },
  'el-tabs': { template: '<div><slot /></div>' },
  'el-tab-pane': { template: '<div><slot /></div>' },
  'el-popover': { template: '<div><slot /><slot name="reference" /></div>' },
  'el-collapse': { template: '<div><slot /></div>' },
  'el-collapse-item': { template: '<div><slot /><slot name="title" /></div>' },
  'el-empty': { template: '<div><slot /></div>' },
  'el-alert': { template: '<div><slot /></div>' },
  'el-input': {
    props: ['modelValue'],
    emits: ['update:modelValue', 'keydown.enter.ctrl', 'keydown.enter.meta'],
    template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
}

export const noopLoadingDirective = {
  mounted() {},
  updated() {},
}

export function withUiGlobal(options = {}) {
  const global = options.global ?? {}
  return {
    ...options,
    global: {
      ...global,
      stubs: {
        ...elementPlusStubs,
        ...iconStubs,
        ...(global.stubs ?? {}),
      },
      directives: {
        loading: noopLoadingDirective,
        ...(global.directives ?? {}),
      },
    },
  }
}
