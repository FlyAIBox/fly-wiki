<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import {
  ApiError,
  getEditableNote,
  saveEditableNote,
  type EditableNote,
} from '@/api/sources'
import { usePlatformStore } from '@/stores/platform'

const route = useRoute()
const platform = usePlatformStore()
const note = ref<EditableNote | null>(null)
const markdown = ref('')
const loading = ref(true)
const saving = ref(false)
const saved = ref(false)
const error = ref<string | null>(null)
const noteId = computed(() => String(route.params.noteId))

async function loadNote() {
  if (!platform.context) return
  loading.value = true
  error.value = null
  try {
    note.value = await getEditableNote(platform.context.workspace_id, noteId.value)
    markdown.value = note.value.current_version.markdown
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '无法加载笔记'
  } finally {
    loading.value = false
  }
}

async function saveNote() {
  if (!platform.context || !note.value || !markdown.value.trim()) return
  saving.value = true
  saved.value = false
  error.value = null
  try {
    note.value = await saveEditableNote(
      platform.context.workspace_id,
      note.value.id,
      markdown.value,
      note.value.current_version.version_number,
    )
    markdown.value = note.value.current_version.markdown
    saved.value = true
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 409) {
      error.value = '这份笔记已在别处更新，请刷新后再编辑。'
    } else {
      error.value = caught instanceof Error ? caught.message : '无法保存笔记'
    }
  } finally {
    saving.value = false
  }
}

watch(
  () => platform.context,
  (context) => {
    if (context) void loadNote()
  },
)
watch(markdown, () => {
  saved.value = false
})
onMounted(() => {
  if (!platform.context) void platform.load()
  else void loadNote()
})
</script>

<template>
  <main class="note-page">
    <div class="note-toolbar">
      <router-link class="back-link" to="/">← 返回知识收件箱</router-link>
      <div class="note-actions">
        <span v-if="saved" class="saved-message">已保存</span>
        <span v-if="note" class="version-label">版本 {{ note.current_version.version_number }}</span>
        <t-button
          theme="primary"
          :loading="saving"
          :disabled="loading || !markdown.trim()"
          @click="saveNote"
        >
          保存新版本
        </t-button>
      </div>
    </div>

    <section class="note-editor-shell">
      <header>
        <p class="eyebrow">EDITABLE NOTE</p>
        <h1>整理采集笔记</h1>
        <p>每次保存都会产生一个不可变版本，原始网页证据不会被覆盖。</p>
      </header>

      <p v-if="loading" class="loading-message">正在加载笔记…</p>
      <p v-else-if="error && !note" class="error-message" role="alert">{{ error }}</p>
      <template v-else-if="note">
        <t-textarea
          v-model="markdown"
          class="markdown-editor"
          name="markdown"
          aria-label="Markdown 笔记"
          placeholder="在这里整理采集内容…"
          :autosize="{ minRows: 18 }"
        />
        <p v-if="error" class="error-message" role="alert">{{ error }}</p>
      </template>
    </section>
  </main>
</template>
