<script setup lang="ts">
import { computed, onMounted } from 'vue'

import { usePlatformStore } from '@/stores/platform'

const platform = usePlatformStore()
const components = computed(() => Object.values(platform.health?.components ?? {}))

onMounted(() => platform.load())
</script>

<template>
  <main class="home-grid">
    <section class="hero-panel">
      <p class="eyebrow">KNOWLEDGE INBOX</p>
      <h1>把进入的资料，变成可以追溯的知识。</h1>
      <p class="hero-copy">
        当前正在搭建 M0 平台骨架。采集、OpenKB 编译、证据图和微信 Channel 将沿同一 Workspace 边界接入。
      </p>
      <div v-if="platform.context" class="context-row">
        <div>
          <span class="field-label">Workspace</span>
          <strong>{{ platform.context.workspace_name }}</strong>
        </div>
        <div>
          <span class="field-label">Knowledge Base</span>
          <strong>{{ platform.context.knowledge_base_name }}</strong>
        </div>
      </div>
      <p v-else-if="platform.error" class="error-message" role="alert">{{ platform.error }}</p>
      <p v-else class="loading-message">正在连接自托管服务…</p>
    </section>

    <t-card class="status-card" :bordered="false">
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
  </main>
</template>

