<script setup lang="ts">
import { useIntervalFn, useWebSocket } from '@vueuse/core'
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const statusText = ref('--')
const velocityText = ref('--')
const programName = ref('--')
const isError = ref(false)

const lastReceivedAt = ref<number>(Date.now())

const { data } = useWebSocket('/ws', {
  autoReconnect: true,
})

watch(data, (rawMsg) => {
  lastReceivedAt.value = Date.now()
  try {
    const msg = JSON.parse(rawMsg)

    switch (msg.type) {
      case 'tcp_velocity':{
        const unit = msg.unit || 'mm/s'
        const velocity = typeof msg.velocity === 'number' ? msg.velocity.toFixed(3) : String(msg.velocity)
        velocityText.value = `${velocity} ${unit}`
        statusText.value = velocity > 0 ? t('runningStatus.statusRunning') : t('runningStatus.statusStopped')
        break
      }
      case 'running_program': {
        programName.value = msg.program_name || '--'
        break
      }
    }
  }
  catch {}
})

useIntervalFn(() => {
  // 一段时间没收到消息，显示错误
  isError.value = Date.now() - lastReceivedAt.value > 3000
}, 500)
</script>

<template>
  <div class="flex items-center justify-center p-6">
    <div class="w-full max-w-3xl rounded-xl border border-gray-100 bg-white p-6 shadow-md">
      <div
        v-if="isError"
        class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600"
      >
        {{ t('runningStatus.connectError') }}
      </div>

      <div class="mb-4 flex items-center">
        <span class="mr-2 h-4 w-1 rounded bg-red-500" />
        <span class="text-base font-semibold text-gray-800">{{ t('runningStatus.title') }}</span>
      </div>

      <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between md:gap-6">
        <div class="flex flex-wrap items-baseline text-sm text-gray-500">
          <span class="mr-2">{{ t('runningStatus.status') }}</span>
          <span class="text-base font-semibold text-gray-900">{{ statusText }}</span>
        </div>
        <div class="flex flex-wrap items-baseline text-sm text-gray-500">
          <span class="mr-2">{{ t('runningStatus.velocity') }}</span>
          <span class="text-base font-semibold text-gray-800">{{ velocityText }}</span>
        </div>
        <div class="flex flex-wrap items-baseline text-sm text-gray-500">
          <span class="mr-2">{{ t('runningStatus.programName') }}</span>
          <span class="text-base font-semibold text-gray-800">{{ programName }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
