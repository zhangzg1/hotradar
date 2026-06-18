/**
 * WebSocket 服务模块
 * 使用原生 WebSocket API 与后端 FastAPI WebSocket 对接
 */
import type { Hotspot } from './api'
import { getToken } from './api'

// WebSocket 配置
const WS_BASE_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`

let socket: WebSocket | null = null
let currentTaskId: string | null = null
let reconnectAttempts = 0
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_DELAY = 1000

// 回调类型定义
type HotspotCallback = (hotspot: Hotspot) => void
type StatusCallback = (status: { taskId: string; status: string; keyword?: string; totalKeywords?: number; hotspotsCount?: number; totalHotspots?: number }) => void
type ErrorCallback = (error: { taskId: string; error: string }) => void
type BatchHotspotCallback = (data: { taskId: string; keywordId: string; keyword: string; hotspots: Hotspot[]; stats: { total: number } }) => void
type DouyinCookieCallback = (data: { type: string; status: string; message: string }) => void

// 回调集合
const hotspotCallbacks: Set<HotspotCallback> = new Set()
const statusCallbacks: Set<StatusCallback> = new Set()
const errorCallbacks: Set<ErrorCallback> = new Set()
const batchHotspotCallbacks: Set<BatchHotspotCallback> = new Set()
const douyinCookieCallbacks: Set<DouyinCookieCallback> = new Set()

/**
 * 建立 WebSocket 连接
 */
export function connectWebSocket(): void {
  // 不在这里建立连接，等待订阅任务时再连接
  console.log('[WS] WebSocket 服务已初始化')
}

/**
 * 订阅特定任务
 * 建立到任务专属 WebSocket 端点的连接
 */
export function subscribeToTask(taskId: string): void {
  currentTaskId = taskId

  // 关闭现有连接
  if (socket) {
    socket.close()
    socket = null
  }

  // 建立新连接到任务专属端点
  const token = getToken()
  const wsUrl = `${WS_BASE_URL}/ws/tasks/${taskId}${token ? `?token=${token}` : ''}`
  console.log('[WS] 正在连接:', wsUrl)

  socket = new WebSocket(wsUrl)

  socket.onopen = () => {
    console.log('[WS] 已连接到任务:', taskId)
    reconnectAttempts = 0
    // 发送心跳 ping
    socket?.send('ping')
  }

  socket.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data)
      console.log('[WS] 收到消息:', message)

      // 根据消息类型分发到对应回调
      switch (message.type) {
        case 'pong':
          // 心跳响应，忽略
          break

        case 'collection_status':
          // 采集状态更新
          statusCallbacks.forEach(cb => cb(message.data))
          break

        case 'hotspot_batch':
          // 批量热点推送
          const batchData = message.data
          batchHotspotCallbacks.forEach(cb => cb(batchData))
          // 同时触发单个热点回调（兼容旧逻辑）
          if (batchData.hotspots) {
            batchData.hotspots.forEach((h: Hotspot) => hotspotCallbacks.forEach(cb => cb(h)))
          }
          break

        case 'collection_error':
          // 错误消息
          errorCallbacks.forEach(cb => cb(message.data))
          break

        case 'douyin_cookie_updated':
        case 'douyin_cookie_expired':
          // 抖音 Cookie 状态变更
          douyinCookieCallbacks.forEach(cb => cb(message))
          break

        default:
          console.log('[WS] 未处理的消息类型:', message.type)
      }
    } catch (e) {
      console.error('[WS] 解析消息失败:', e)
    }
  }

  socket.onerror = (error) => {
    console.error('[WS] 连接错误:', error)
  }

  socket.onclose = (event) => {
    console.log('[WS] 连接关闭:', event.code, event.reason)

    // 如果任务仍在进行中，尝试重连
    if (currentTaskId && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
      reconnectAttempts++
      console.log(`[WS] 尝试重连 (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`)
      setTimeout(() => {
        if (currentTaskId) {
          subscribeToTask(currentTaskId)
        }
      }, RECONNECT_DELAY * reconnectAttempts)
    }
  }
}

/**
 * 取消任务订阅
 */
export function unsubscribeTask(): void {
  currentTaskId = null
  if (socket) {
    socket.close()
    socket = null
  }
  console.log('[WS] 已取消订阅')
}

/**
 * 断开 WebSocket 连接
 */
export function disconnectWebSocket(): void {
  unsubscribeTask()
}

/**
 * 注册新热点回调
 */
export function onNewHotspot(callback: HotspotCallback): () => void {
  hotspotCallbacks.add(callback)
  return () => hotspotCallbacks.delete(callback)
}

/**
 * 注册批量热点回调
 */
export function onBatchHotspot(callback: BatchHotspotCallback): () => void {
  batchHotspotCallbacks.add(callback)
  return () => batchHotspotCallbacks.delete(callback)
}

/**
 * 注册状态变化回调
 */
export function onStatusChange(callback: StatusCallback): () => void {
  statusCallbacks.add(callback)
  return () => statusCallbacks.delete(callback)
}

/**
 * 注册错误回调
 */
export function onError(callback: ErrorCallback): () => void {
  errorCallbacks.add(callback)
  return () => errorCallbacks.delete(callback)
}

/**
 * 注册抖音 Cookie 状态变更回调
 */
export function onDouyinCookieChange(callback: DouyinCookieCallback): () => void {
  douyinCookieCallbacks.add(callback)
  return () => douyinCookieCallbacks.delete(callback)
}

/**
 * 检查连接状态
 */
export function isConnected(): boolean {
  return socket?.readyState === WebSocket.OPEN
}

/**
 * 获取连接 ID（使用 taskId 作为标识）
 */
export function getConnectionId(): string | null {
  return currentTaskId
}