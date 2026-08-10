export type CaptureStatus = 'accepted' | 'fetching' | 'ready_for_compile' | 'failed'

export interface CaptureJob {
  id: string
  workspace_id: string
  knowledge_base_id: string
  canonical_url: string
  idempotency_key: string
  status: CaptureStatus
  attempts: number
  source_version_id: string | null
  error_code: string | null
  error_detail: string | null
  created_at: string
  updated_at: string
}

export interface SourceArtifact {
  id: string
  role: 'raw_html' | 'markdown' | 'metadata' | 'locator_map' | 'attachment'
  name: string
  content_type: string
  content_sha256: string
  size_bytes: number
}

export interface SourceVersion {
  id: string
  workspace_id: string
  source_id: string
  canonical_uri: string
  content_sha256: string
  captured_at: string
  artifacts: SourceArtifact[]
  editable_note_id: string | null
}

export interface NoteVersion {
  id: string
  version_number: number
  markdown: string
  created_at: string
}

export interface EditableNote {
  id: string
  workspace_id: string
  source_version_id: string
  current_version: NoteVersion
  history: NoteVersion[]
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(
  path: string,
  workspaceId: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('X-Workspace-ID', workspaceId)
  if (init.body) headers.set('Content-Type', 'application/json')

  const response = await fetch(path, { ...init, headers })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: string | { message?: string } }
      | null
    const detail = body?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : detail?.message || `请求失败（HTTP ${response.status}）`
    throw new ApiError(response.status, message)
  }
  return (await response.json()) as T
}

export function createCapture(
  workspaceId: string,
  knowledgeBaseId: string,
  url: string,
): Promise<CaptureJob> {
  return request(
    `/api/workspaces/${workspaceId}/knowledge-bases/${knowledgeBaseId}/captures`,
    workspaceId,
    {
      method: 'POST',
      body: JSON.stringify({
        url,
        idempotency_key: `web:${crypto.randomUUID()}`,
      }),
    },
  )
}

export function getCapture(workspaceId: string, jobId: string): Promise<CaptureJob> {
  return request(`/api/workspaces/${workspaceId}/captures/${jobId}`, workspaceId)
}

export function retryCapture(workspaceId: string, jobId: string): Promise<CaptureJob> {
  return request(`/api/workspaces/${workspaceId}/captures/${jobId}/retry`, workspaceId, {
    method: 'POST',
  })
}

export function getSourceVersion(
  workspaceId: string,
  sourceVersionId: string,
): Promise<SourceVersion> {
  return request(
    `/api/workspaces/${workspaceId}/source-versions/${sourceVersionId}`,
    workspaceId,
  )
}

export function getEditableNote(workspaceId: string, noteId: string): Promise<EditableNote> {
  return request(`/api/workspaces/${workspaceId}/editable-notes/${noteId}`, workspaceId)
}

export function saveEditableNote(
  workspaceId: string,
  noteId: string,
  markdown: string,
  baseVersionNumber: number,
): Promise<EditableNote> {
  return request(`/api/workspaces/${workspaceId}/editable-notes/${noteId}`, workspaceId, {
    method: 'PUT',
    body: JSON.stringify({
      markdown,
      base_version_number: baseVersionNumber,
    }),
  })
}
