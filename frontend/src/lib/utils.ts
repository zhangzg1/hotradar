import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDateTime(date: string | Date): string {
  const d = new Date(date)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function relativeTime(date: string | Date): string {
  const now = new Date()
  const past = new Date(date)
  const diffMs = now.getTime() - past.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffSec < 60) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  if (diffHour < 24) return `${diffHour} 小时前`
  if (diffDay < 7) return `${diffDay} 天前`
  if (diffDay < 30) return `${Math.floor(diffDay / 7)} 周前`
  return formatDateTime(date)
}

export function calcHeatScore(h: Hotspot): number {
  const likes = h.likeCount ?? 0
  const retweets = h.retweetCount ?? 0
  const replies = h.replyCount ?? 0
  const comments = h.commentCount ?? 0
  const quotes = h.quoteCount ?? 0
  const views = h.viewCount ?? 0
  const raw = likes * 2 + retweets * 3 + replies * 1.5 + comments * 1.5 + quotes * 2 + views / 100
  if (raw <= 0) return 0
  return Math.min(100, Math.round(Math.log10(raw + 1) * 25))
}

export function getSignalLevel(score: number): { bars: number; label: string } {
  if (score >= 80) return { bars: 5, label: '爆' }
  if (score >= 60) return { bars: 4, label: '热' }
  if (score >= 40) return { bars: 3, label: '温' }
  if (score >= 20) return { bars: 2, label: '中' }
  return { bars: 1, label: '弱' }
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
}

export interface Hotspot {
  id: string
  title: string
  content: string
  url: string
  source: string
  isReal: boolean
  relevance: number
  relevanceReason?: string
  importance: 'low' | 'medium' | 'high' | 'urgent'
  summary?: string
  authorName?: string
  authorUsername?: string
  authorAvatar?: string
  authorVerified?: boolean
  authorFollowers?: number
  viewCount?: number
  likeCount?: number
  retweetCount?: number
  replyCount?: number
  commentCount?: number
  quoteCount?: number
  danmakuCount?: number
  publishedAt?: string
  createdAt: string
  keywordId?: string
  keyword?: { id: string; text: string }
}

export interface Stats {
  total: number
  todayNew: number
  importanceDistribution: { importance: string; count: number }[]
  sourceDistribution: { source: string; count: number }[]
  realCount: number
  fakeCount: number
}

export interface CollectionResult {
  taskId: string
  keywordId: string
  keyword: string
  hotspots: Hotspot[]
}