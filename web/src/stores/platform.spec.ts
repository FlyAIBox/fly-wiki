import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { usePlatformStore } from './platform'

describe('platform store', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.unstubAllGlobals())

  it('loads the bootstrap context and degraded component report', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          owner_id: 'owner',
          owner_email: 'owner@flywiki.local',
          workspace_id: 'workspace',
          workspace_slug: 'personal',
          workspace_name: 'Personal Workspace',
          knowledge_base_id: 'knowledge-base',
          knowledge_base_slug: 'inbox',
          knowledge_base_name: 'Inbox',
        }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: async () => ({ status: 'degraded', components: {} }),
      })
    vi.stubGlobal('fetch', fetchMock)
    const store = usePlatformStore()

    await store.load()

    expect(store.context?.workspace_name).toBe('Personal Workspace')
    expect(store.health?.status).toBe('degraded')
    expect(store.error).toBeNull()
  })
})

