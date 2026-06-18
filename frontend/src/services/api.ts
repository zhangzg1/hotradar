const API_BASE = '/api/v1'

// ==================== Auth Token Management ====================
const TOKEN_KEY = 'hotpulse_token'
const USER_KEY = 'hotpulse_user'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function getUser(): { userId: string; username: string } | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function setUser(user: { userId: string; username: string }): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function isAuthenticated(): boolean {
  return !!getToken()
}

interface ApiResponse<T> {
  data: T
  total?: number
  page?: number
  pageSize?: number
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  })

  if (response.status === 401) {
    clearAuth()
    window.location.reload()
    throw new Error('Session expired')
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || 'Request failed')
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

// ==================== Auth API ====================
export const authApi = {
  register: (username: string, password: string) =>
    request<{ success: boolean; data?: { userId: string; username: string }; message?: string }>(
      '/auth/register',
      { method: 'POST', body: JSON.stringify({ username, password }) }
    ),

  login: (username: string, password: string) =>
    request<{ success: boolean; data?: { token: string; username: string; userId: string }; message?: string }>(
      '/auth/login',
      { method: 'POST', body: JSON.stringify({ username, password }) }
    ),
}

// Keywords API
export const keywordsApi = {
  getAll: (params?: { isActive?: boolean; page?: number; pageSize?: number }) => {
    const searchParams = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) searchParams.append(key, String(value))
      })
    }
    return request<ApiResponse<Keyword[]>>(`/keywords?${searchParams}`)
  },

  getById: (id: string) => request<Keyword>(`/keywords/${id}`),

  create: (data: { text: string; category?: string }) =>
    request<Keyword>('/keywords', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: { text?: string; category?: string }) =>
    request<Keyword>(`/keywords/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (id: string) => request<void>(`/keywords/${id}`, { method: 'DELETE' }),

  toggle: (id: string) => request<Keyword>(`/keywords/${id}/toggle`, { method: 'PATCH' }),

  getStats: () => request<{ total: number; active: number; inactive: number }>('/keywords/stats'),

  batch: (action: 'activate' | 'deactivate' | 'delete', keywordIds: string[]) =>
    request<{ affectedCount: number }>('/keywords/batch', {
      method: 'POST',
      body: JSON.stringify({ action, keywordIds }),
    }),
}

// Hotspots API
export const hotspotsApi = {
  getAll: (params?: {
    keywordIds?: string[]
    sources?: string[]
    importance?: string[]
    isReal?: boolean
    timeRange?: string
    publishedAtFrom?: string
    publishedAtTo?: string
    sortBy?: string
    sortOrder?: string
    page?: number
    pageSize?: number
  }) => {
    const searchParams = new URLSearchParams()
    if (params) {
      // 将 camelCase 参数名转换为 snake_case 以匹配后端
      const paramMap: Record<string, string> = {
        keywordIds: 'keyword_ids',
        sources: 'sources',
        importance: 'importance',
        isReal: 'is_real',
        timeRange: 'time_range',
        publishedAtFrom: 'published_at_from',
        publishedAtTo: 'published_at_to',
        sortBy: 'sort_by',
        sortOrder: 'sort_order',
        page: 'page',
        pageSize: 'page_size',
      }
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== '') {
          const backendKey = paramMap[key] || key
          if (Array.isArray(value) && value.length > 0) {
            value.forEach(v => searchParams.append(backendKey, v))
          } else if (!Array.isArray(value)) {
            searchParams.append(backendKey, String(value))
          }
        }
      })
    }
    return request<ApiResponse<Hotspot[]>>(`/hotspots?${searchParams}`)
  },

  getById: (id: string) => request<Hotspot>(`/hotspots/${id}`),

  getStats: () =>
    request<{
      total: number
      todayNew: number
      weekNew: number
      importanceDistribution: { importance: string; count: number }[]
      sourceDistribution: { source: string; count: number }[]
      realCount: number
      fakeCount: number
    }>('/hotspots/stats'),

  search: (query: string, params?: { keywordId?: string; source?: string }) =>
    request<ApiResponse<Hotspot[]>>('/hotspots/search', {
      method: 'POST',
      body: JSON.stringify({ query, ...params, limit: 50, offset: 0 }),
    }),

  delete: (id: string) => request<void>(`/hotspots/${id}`, { method: 'DELETE' }),
}

// Collection API
export const collectionApi = {
  create: (keywordIds: string[]) =>
    request<{ taskId: string; status: string; message: string }>('/collections', {
      method: 'POST',
      body: JSON.stringify({ keywordIds }),
    }),

  createWithAutoEmail: (keywordIds: string[]) =>
    request<{ taskId: string; status: string; message: string }>('/collections/auto-email', {
      method: 'POST',
      body: JSON.stringify({ keywordIds }),
    }),
}

// Email API
export const emailApi = {
  sendRecent: (timeRange: string) =>
    request<{ message: string; sentCount: number }>('/email-notifications/send-recent', {
      method: 'POST',
      body: JSON.stringify({ timeRange }),
    }),
}

// Scheduler API
export const schedulerApi = {
  getConfig: () =>
    request<SchedulerConfigResponse>('/scheduler/config'),

  updateConfig: (data: { isEnabled: boolean; intervalHours: number }) =>
    request<SchedulerConfigResponse>('/scheduler/config', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getStatus: () =>
    request<SchedulerStatusResponse>('/scheduler/status'),
}

// Fetch Quota API
export const fetchQuotaApi = {
  get: () =>
    request<FetchQuotaResponse>('/fetch-quotas'),

  update: (data: FetchQuotaResponse) =>
    request<FetchQuotaResponse>('/fetch-quotas', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
}

// Chat API
export const chatApi = {
  startChat: (hotspotId: string, message: string) =>
    request<ChatResponse>(`/hotspots/${hotspotId}/chat`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  continueChat: (hotspotId: string, sessionId: string, message: string) =>
    request<ChatResponse>(`/hotspots/${hotspotId}/chat`, {
      method: 'POST',
      body: JSON.stringify({ message, session_id: sessionId }),
    }),

  // 流式聊天
  streamChat: async (
    hotspotId: string,
    message: string,
    sessionId: string | null,
    onContent: (content: string) => void,
    onSession: (sessionId: string) => void,
    onToolCall: (count: number) => void,
    onLoadingHotspot: (hotspotId: string) => void,
    onDone: (loadedHotspots: string[]) => void,
    onError: (error: string) => void,
  ) => {
    const token = getToken()
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    const response = await fetch(`${API_BASE}/hotspots/${hotspotId}/chat/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ message, session_id: sessionId }),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }))
      onError(error.detail || 'Request failed')
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      onError('无法读取响应流')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6))

            if (data.type === 'session') {
              onSession(data.session_id)
            } else if (data.type === 'tool_call') {
              onToolCall(data.count)
            } else if (data.type === 'loading_hotspot') {
              onLoadingHotspot(data.hotspot_id)
            } else if (data.type === 'content') {
              onContent(data.content)
            } else if (data.type === 'done') {
              onDone(data.loaded_hotspots || [])
            } else if (data.error) {
              onError(data.error)
            }
          }
        }
      }
    } catch (e) {
      onError('流式读取失败')
    }
  },

  getSessions: (hotspotId: string) =>
    request<ChatSessionListResponse>(`/hotspots/${hotspotId}/sessions`),

  getSessionMessages: (hotspotId: string, sessionId: string) =>
    request<ChatMessage[]>(`/hotspots/${hotspotId}/sessions/${sessionId}`),

  deleteSession: (hotspotId: string, sessionId: string) =>
    request<{ message: string }>(`/hotspots/${hotspotId}/sessions/${sessionId}`, {
      method: 'DELETE',
    }),

  renameSession: (hotspotId: string, sessionId: string, name: string) =>
    request<ChatSession>(`/hotspots/${hotspotId}/sessions/${sessionId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),
}

// Types
export interface Keyword {
  id: string
  text: string
  category: string | null
  isActive: boolean
  createdAt: string
  updatedAt: string
  hotspotCount?: number
  recentHotspots?: { id: string; title: string; source: string; importance: string }[]
}

export interface Hotspot {
  id: string
  title: string
  content: string
  url: string
  source: string
  sourceId?: string
  isReal: boolean
  relevance: number
  relevanceReason?: string
  keywordMentioned?: boolean
  importance: 'low' | 'medium' | 'high' | 'urgent'
  summary?: string
  author?: {
    name?: string
    username?: string
    avatar?: string
    followers?: number
    verified?: boolean
  }
  engagement?: {
    viewCount?: number
    likeCount?: number
    retweetCount?: number
    replyCount?: number
    commentCount?: number
    quoteCount?: number
    danmakuCount?: number
  }
  emailSent?: boolean
  publishedAt?: string
  createdAt: string
  keywordId?: string
}

export interface ChatResponse {
  reply: string
  session_id: string
  loaded_hotspots?: string[]
}

export interface ChatSession {
  id: string
  hotspot_id: string
  name?: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface ChatSessionListResponse {
  data: ChatSession[]
  total: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'tool'
  content: string
  loaded_hotspots?: string[]
  created_at: string
}

export interface SchedulerConfigResponse {
  isEnabled: boolean
  intervalHours: number
}

export interface SchedulerStatusResponse {
  isEnabled: boolean
  intervalHours: number
  lastRunAt: string | null
  lastRunStatus: string | null
  nextRunAt: string | null
  isCollecting: boolean
}

export interface FetchQuotaResponse {
  twitter: number
  youtube: number
  bilibili: number
  douyin: number
  bing: number
  sogou: number
  twitterEnabled: boolean
  youtubeEnabled: boolean
  bilibiliEnabled: boolean
  douyinEnabled: boolean
  bingEnabled: boolean
  sogouEnabled: boolean
  douyinCookieActive: boolean
}

// Settings Types
export interface AppSettings {
  llmBaseUrl: string | null
  llmApiKey: string | null
  llmModelName: string | null
  llmTested: boolean
  notifyEmail: string | null
  twitterApiKey: string | null
  twitterTested: boolean
  twitterConfigured: boolean
}

export interface LLMTestResponse {
  success: boolean
  message: string
}

export interface TwitterTestResponse {
  success: boolean
  message: string
}

// Settings API
export const settingsApi = {
  get: () =>
    request<AppSettings>('/settings'),

  update: (data: Partial<AppSettings>) =>
    request<AppSettings>('/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  testLlm: (baseUrl: string, apiKey: string, modelName: string) =>
    request<LLMTestResponse>('/settings/test-llm', {
      method: 'POST',
      body: JSON.stringify({ baseUrl, apiKey, modelName }),
    }),

  testTwitter: (apiKey: string) =>
    request<TwitterTestResponse>('/settings/test-twitter', {
      method: 'POST',
      body: JSON.stringify({ apiKey }),
    }),
}

// Douyin Cookie Types
export interface DouyinLoginStartResponse {
  sessionId: string
  qrCodeBase64: string
  error?: string
  autoLogin?: boolean
}

export interface DouyinLoginStatusResponse {
  status: 'pending' | 'success' | 'timeout' | 'failed' | 'not_found'
  message: string
}

export interface DouyinCookieStatusResponse {
  hasCookie: boolean
  status: 'active' | 'expired' | 'none'
  expiresAt: string | null
  updatedAt: string | null
}

export interface DouyinCookieDeleteResponse {
  success: boolean
  message: string
}

// Douyin Cookie API
export const douyinCookieApi = {
  startLogin: () =>
    request<DouyinLoginStartResponse>('/douyin-cookie/login/start', {
      method: 'POST',
    }),

  getLoginStatus: (sessionId: string) =>
    request<DouyinLoginStatusResponse>(`/douyin-cookie/login/status?sessionId=${sessionId}`),

  getCookieStatus: () =>
    request<DouyinCookieStatusResponse>('/douyin-cookie/status'),

  deleteCookie: () =>
    request<DouyinCookieDeleteResponse>('/douyin-cookie', {
      method: 'DELETE',
    }),
}