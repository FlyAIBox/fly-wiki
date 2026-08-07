import { defineStore } from 'pinia'

export interface ComponentHealth {
  name: string
  healthy: boolean
  detail: string
}

export interface HealthReport {
  status: 'ready' | 'degraded'
  components: Record<string, ComponentHealth>
}

export interface BootstrapContext {
  owner_id: string
  owner_email: string
  workspace_id: string
  workspace_slug: string
  workspace_name: string
  knowledge_base_id: string
  knowledge_base_slug: string
  knowledge_base_name: string
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok && response.status !== 503) {
    throw new Error(`${path} returned ${response.status}`)
  }
  return (await response.json()) as T
}

export const usePlatformStore = defineStore('platform', {
  state: () => ({
    context: null as BootstrapContext | null,
    health: null as HealthReport | null,
    loading: false,
    error: null as string | null,
  }),
  actions: {
    async load() {
      this.loading = true
      this.error = null
      try {
        const [context, health] = await Promise.all([
          getJson<BootstrapContext>('/api/context'),
          getJson<HealthReport>('/health/ready'),
        ])
        this.context = context
        this.health = health
      } catch (error) {
        this.error = error instanceof Error ? error.message : '无法连接 FlyWiki'
      } finally {
        this.loading = false
      }
    },
  },
})

