const API_BASE = '/api'

interface UploadPayload {
  content?: string
  url?: string
  owner: string
  category?: string
  language?: string
  title?: string
}

interface SearchPayload {
  query: string
  top_k?: number
  category?: string
  language?: string
  owner?: string
}

interface RAGPayload {
  query: string
  top_k?: number
  category?: string
  provider?: string
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  upload: (data: UploadPayload) =>
    request('/upload', { method: 'POST', body: JSON.stringify(data) }),

  uploadPrepare: (data: UploadPayload) =>
    request('/upload/prepare', { method: 'POST', body: JSON.stringify(data) }),

  uploadFinalize: (data: { content_hash: string; record_id: number; tx_hash?: string }) =>
    request('/upload/finalize', { method: 'POST', body: JSON.stringify(data) }),

  search: (data: SearchPayload) =>
    request('/search', { method: 'POST', body: JSON.stringify(data) }),

  rag: (data: RAGPayload) =>
    request('/rag', { method: 'POST', body: JSON.stringify(data) }),

  embed: (text: string) =>
    request('/embed', { method: 'POST', body: JSON.stringify({ text }) }),

  fetchUrl: (url: string) =>
    request('/fetch-url', { method: 'POST', body: JSON.stringify({ url }) }),

  render: () => request('/render'),

  providers: () => request('/providers'),

  graph: () => request('/graph'),

  rebuildGraph: () =>
    request('/graph/rebuild', { method: 'POST' }),

  health: () => request('/health'),

  paidSearch: (data: { query: string; payer: string; top_k?: number }) =>
    request('/search/paid', { method: 'POST', body: JSON.stringify(data) }),

  account: (publicKey: string) => request(`/account/${publicKey}`),
}
