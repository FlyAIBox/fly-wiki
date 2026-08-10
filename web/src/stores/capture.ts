import { defineStore } from 'pinia'

import {
  createCapture,
  getCapture,
  getSourceVersion,
  retryCapture,
  type CaptureJob,
} from '@/api/sources'

export const useCaptureStore = defineStore('capture', {
  state: () => ({
    job: null as CaptureJob | null,
    noteId: null as string | null,
    submitting: false,
    error: null as string | null,
  }),
  getters: {
    isPending: (state) =>
      state.job?.status === 'accepted' || state.job?.status === 'fetching',
  },
  actions: {
    async submit(workspaceId: string, knowledgeBaseId: string, url: string) {
      this.submitting = true
      this.error = null
      this.noteId = null
      try {
        this.job = await createCapture(workspaceId, knowledgeBaseId, url)
      } catch (error) {
        this.error = error instanceof Error ? error.message : '无法提交采集任务'
      } finally {
        this.submitting = false
      }
    },
    async refresh(workspaceId: string) {
      if (!this.job) return
      try {
        this.job = await getCapture(workspaceId, this.job.id)
        if (this.job.status === 'ready_for_compile' && this.job.source_version_id) {
          const sourceVersion = await getSourceVersion(
            workspaceId,
            this.job.source_version_id,
          )
          this.noteId = sourceVersion.editable_note_id
        }
      } catch (error) {
        this.error = error instanceof Error ? error.message : '无法刷新采集状态'
      }
    },
    async retry(workspaceId: string) {
      if (!this.job) return
      this.error = null
      try {
        this.job = await retryCapture(workspaceId, this.job.id)
      } catch (error) {
        this.error = error instanceof Error ? error.message : '无法重试采集任务'
      }
    },
    reset() {
      this.job = null
      this.noteId = null
      this.error = null
    },
  },
})
