import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useCaptureStore } from './capture'

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }
}

describe('capture store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('crypto', { randomUUID: () => 'request-id' })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('submits a capture and resolves its editable note', async () => {
    const acceptedJob = {
      id: 'job-1',
      workspace_id: 'workspace-1',
      knowledge_base_id: 'kb-1',
      canonical_url: 'https://example.com/',
      idempotency_key: 'web:request-id',
      status: 'accepted',
      attempts: 0,
      source_version_id: null,
      error_code: null,
      error_detail: null,
      created_at: '2026-08-08T00:00:00Z',
      updated_at: '2026-08-08T00:00:00Z',
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(acceptedJob, 202))
      .mockResolvedValueOnce(
        jsonResponse({
          ...acceptedJob,
          status: 'ready_for_compile',
          attempts: 1,
          source_version_id: 'source-version-1',
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          id: 'source-version-1',
          workspace_id: 'workspace-1',
          source_id: 'source-1',
          canonical_uri: 'https://example.com/',
          content_sha256: 'sha256',
          captured_at: '2026-08-08T00:00:00Z',
          artifacts: [],
          editable_note_id: 'note-1',
        }),
      )
    vi.stubGlobal('fetch', fetchMock)
    const store = useCaptureStore()

    await store.submit('workspace-1', 'kb-1', 'https://example.com')
    await store.refresh('workspace-1')

    expect(store.job?.status).toBe('ready_for_compile')
    expect(store.noteId).toBe('note-1')
    const requestOptions = fetchMock.mock.calls[0]![1] as RequestInit
    expect((requestOptions.headers as Headers).get('X-Workspace-ID')).toBe('workspace-1')
  })

  it('exposes API failures to the page', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'URL 不安全' }, 422)),
    )
    const store = useCaptureStore()

    await store.submit('workspace-1', 'kb-1', 'http://localhost')

    expect(store.error).toBe('URL 不安全')
    expect(store.job).toBeNull()
  })
})
