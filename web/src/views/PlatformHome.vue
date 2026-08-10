<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { useCaptureStore } from '@/stores/capture'
import { usePlatformStore } from '@/stores/platform'

const platform = usePlatformStore()
const capture = useCaptureStore()
const url = ref('')
const components = computed(() => Object.values(platform.health?.components ?? {}))
const statusLabels = {
  accepted: '等待处理',
  fetching: '正在采集',
  ready_for_compile: '采集完成',
  failed: '采集失败',
}
let pollTimer: ReturnType<typeof setInterval> | undefined

async function submitCapture() {
  if (!platform.context || !url.value.trim()) return
  await capture.submit(
    platform.context.workspace_id,
    platform.context.knowledge_base_id,
    url.value.trim(),
  )
}

function startPolling() {
  stopPolling()
  if (!platform.context) return
  const workspaceId = platform.context.workspace_id
  pollTimer = setInterval(() => void capture.refresh(workspaceId), 1500)
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = undefined
}

watch(
  () => capture.isPending,
  (pending) => (pending ? startPolling() : stopPolling()),
)

onMounted(() => platform.load())
onBeforeUnmount(stopPolling)
</script>

<template>
  <main class="home-grid">
    <section class="hero-panel">
      <p class="eyebrow">KNOWLEDGE INBOX</p>
      <h1>把进入的资料，变成可以追溯的知识。</h1>
      <p class="hero-copy">
        粘贴公开网页地址，FlyWiki 会保留原始证据并生成一份可继续整理的 Markdown 笔记。
      </p>

      <form v-if="platform.context" class="capture-panel" @submit.prevent="submitCapture">
        <label class="capture-label" for="capture-url">网页地址</label>
        <div class="capture-row">
          <t-input
            id="capture-url"
            v-model="url"
            type="url"
            size="large"
            placeholder="https://example.com/article"
            :disabled="capture.submitting || capture.isPending"
            clearable
          />
          <t-button
            theme="primary"
            size="large"
            type="submit"
            :loading="capture.submitting"
            :disabled="!url.trim() || capture.isPending"
          >
            开始采集
          </t-button>
        </div>

        <div v-if="capture.job" class="capture-result" aria-live="polite">
          <div class="capture-result-head">
            <span class="capture-status" :class="capture.job.status">
              {{ statusLabels[capture.job.status] }}
            </span>
            <small>尝试 {{ capture.job.attempts }} 次</small>
          </div>
          <strong>{{ capture.job.canonical_url }}</strong>
          <p v-if="capture.job.status === 'accepted'">任务已进入队列，等待采集服务处理。</p>
          <p v-else-if="capture.job.status === 'fetching'">正在下载网页并提取正文与证据定位信息…</p>
          <p v-else-if="capture.job.status === 'failed'" class="error-message">
            {{ capture.job.error_code || 'processing_failed' }}
          </p>
          <div class="capture-actions">
            <router-link
              v-if="capture.noteId"
              class="primary-link"
              :to="{ name: 'note', params: { noteId: capture.noteId } }"
            >
              打开笔记
            </router-link>
            <t-button
              v-if="capture.job.status === 'failed' && capture.job.attempts < 3"
              variant="outline"
              @click="platform.context && capture.retry(platform.context.workspace_id)"
            >
              重试
            </t-button>
            <button v-if="!capture.isPending" class="text-button" type="button" @click="capture.reset">
              采集另一个网页
            </button>
          </div>
        </div>
        <p v-if="capture.error" class="error-message" role="alert">{{ capture.error }}</p>
      </form>
      <p v-else-if="platform.error" class="error-message" role="alert">{{ platform.error }}</p>
      <p v-else class="loading-message">正在连接自托管服务…</p>
    </section>

    <aside>
      <t-card class="status-card" :bordered="false">
        <template #title>当前空间</template>
        <div v-if="platform.context" class="workspace-summary">
          <span class="field-label">Workspace</span>
          <strong>{{ platform.context.workspace_name }}</strong>
          <span class="field-label">Knowledge Base</span>
          <strong>{{ platform.context.knowledge_base_name }}</strong>
        </div>
      </t-card>

      <t-card class="status-card compact" :bordered="false">
        <template #title>运行状态</template>
        <template #actions>
          <t-tag :theme="platform.health?.status === 'ready' ? 'success' : 'warning'" variant="light">
            {{ platform.health?.status ?? 'checking' }}
          </t-tag>
        </template>
        <ul class="status-list" aria-label="基础设施状态">
          <li v-for="component in components" :key="component.name">
            <span class="status-dot" :class="{ healthy: component.healthy }" aria-hidden="true" />
            <span>{{ component.name }}</span>
            <small>{{ component.detail }}</small>
          </li>
        </ul>
      </t-card>
    </aside>
  </main>
</template>

